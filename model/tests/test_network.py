import tempfile
import unittest
from pathlib import Path

import torch

from _util import InputContract, default_contract, small_contract
from trnet.network import HEADS, TrueRehabNet, count_params, fake_batch

torch.manual_seed(0)


class ContractTest(unittest.TestCase):
    def test_default_contract_matches_the_recorded_profile(self):
        c = default_contract()
        self.assertEqual(c.fps, 60.0)
        self.assertEqual(c.az_cols, (0, 2, 7, 9, 3, 5, 10, 12))
        self.assertIn(round(c.range_res_m, 4), (0.0594, 0.0388))      # the recorder's profile, or the finer one
        self.assertEqual(c.doppler_bins, 16)
        self.assertEqual(c.shapes()["H"], (128, 4, 64, 32))           # magnitude, phase, point height, presence
        self.assertEqual(c.version, "v1")

    def test_the_finer_profile(self):
        from trnet import paths
        from radarlab import cfg as radar_cfg
        lines = radar_cfg.read_lines(paths.RADAR_LAB / "configs" / "fullmap_fine_awr2x44p.cfg", period_ms=1000 / 60)
        c = InputContract.from_radar_cfg(lines)
        self.assertAlmostEqual(c.range_res_m * 100, 3.88, places=2)    # was 5.94 cm
        self.assertAlmostEqual(c.range_res_m * c.range_bins, 2.48, places=2)
        self.assertAlmostEqual(c.vel_res_ms, 0.1375, places=3)          # speed steps and 60 fps unchanged
        self.assertEqual((c.fps, c.doppler_bins, c.az_cols), (60.0, 16, (0, 2, 7, 9, 3, 5, 10, 12)))

    def test_contracts_saved_before_v1_load_without_points(self):
        old = {k: v for k, v in default_contract().to_dict().items()
               if k not in ("use_points", "points_window", "height_scale_m", "presence_full", "points_az_sign")}
        old.update(version="v0-draft", angle_bins=16)
        c = InputContract.from_dict(old)
        self.assertFalse(c.use_points)
        self.assertEqual(c.shapes()["H"], (128, 2, 64, 16))

    def test_round_trip_and_differences(self):
        c = default_contract()
        self.assertEqual(InputContract.from_dict(c.to_dict()), c)
        self.assertEqual(c.differences(InputContract.from_dict(c.to_dict())), [])
        other = default_contract(use_phase=False)
        self.assertTrue(any("use_phase" in d for d in c.differences(other)))
        self.assertNotEqual(c.key(), other.key())
        with self.assertRaises(ValueError):
            InputContract.from_dict({**c.to_dict(), "made_up": 1})


class NetworkTest(unittest.TestCase):
    def setUp(self):
        self.c = small_contract()
        self.net = TrueRehabNet(self.c).eval()

    def test_shapes_at_every_stage(self):
        n = 5
        H, D = torch.rand(n, self.c.heatmap_channels, 64, self.c.angle_bins), torch.rand(n, 1, 64, 16)
        a, b = self.net.stem_a(H), self.net.stem_b(D)
        self.assertEqual(tuple(a.shape), (n, 16, 32, 8))
        self.assertEqual(tuple(b.shape), (n, 16, 32, 8))
        self.assertEqual(tuple(self.net.encode_frames(H, D).shape), (n, 128))
        batch = fake_batch(self.c, B=2, R=4)
        v = self.net.encode_reps(batch["H"], batch["D"], batch["fmask"], batch["feats"])
        self.assertEqual(tuple(v.shape), (2, 4, 64))
        out = self.net(batch)
        for h in HEADS:
            self.assertEqual(tuple(out[h].shape), (2, 4))
        self.assertEqual(tuple(out["aux"].shape), (2, 4, 4))
        self.assertTrue(all(torch.isfinite(out[h]).all() for h in out))

    def test_parameter_count(self):
        n = count_params(self.net)
        self.assertEqual(n, 239_803)
        no_phase = count_params(TrueRehabNet(small_contract(use_phase=False)))
        self.assertEqual(n - no_phase, 16 * 9)  # one input channel less in Stem A's first conv
        v0 = count_params(TrueRehabNet(small_contract(angle_bins=16, use_points=False)))
        self.assertEqual(n - v0, 2 * 16 * 9)    # the two point layers; the finer angle grid adds no weights

    def test_every_supported_angle_grid(self):
        for a in (16, 32, 64):
            c = small_contract(angle_bins=a)
            net = TrueRehabNet(c).eval()
            out = net.encode_frames(torch.rand(3, c.heatmap_channels, 64, a), torch.rand(3, 1, 64, 16))
            self.assertEqual(tuple(out.shape), (3, 128))
        with self.assertRaises(ValueError):
            TrueRehabNet(small_contract(angle_bins=24))

    def test_causal_over_reps(self):
        batch = fake_batch(self.c, B=1, R=5)
        ref = self.net(batch)
        changed = {k: v.clone() for k, v in batch.items()}
        changed["H"][:, 3] = torch.rand_like(changed["H"][:, 3])
        changed["feats"][:, 3] += 5
        out = self.net(changed)
        for h in HEADS:
            torch.testing.assert_close(out[h][:, :3], ref[h][:, :3])
            self.assertFalse(torch.allclose(out[h][:, 3], ref[h][:, 3]))

    def test_masked_frames_and_padded_reps_change_nothing(self):
        batch = fake_batch(self.c, B=1, R=3)
        batch["fmask"][0, 1, 20:] = 0          # rep 2 is shorter: its last frames are padding
        ref = self.net(batch)
        junk = {k: v.clone() for k, v in batch.items()}
        junk["H"][0, 1, 20:] = 99.0            # whatever is in padded frames must not matter
        junk["D"][0, 1, 20:] = -5.0
        out = self.net(junk)
        for h in HEADS:
            torch.testing.assert_close(out[h], ref[h])
        longer = fake_batch(self.c, B=1, R=5, seed=3)   # two extra padded reps at the end
        for k in ("H", "D", "fmask", "feats", "rmask"):
            longer[k][:, :3] = batch[k]
        for k in batch:
            if k.startswith("base_"):
                longer[k] = batch[k]
        longer["fmask"][:, 3:] = 0
        longer["rmask"][:, 3:] = 0
        out = self.net(longer)
        for h in HEADS:
            torch.testing.assert_close(out[h][:, :3], ref[h])

    def test_baseline_is_subtracted(self):
        batch = fake_batch(self.c, B=1, R=2)
        seen = {}

        def grab(module, inputs, output):
            seen["x"] = inputs[0].detach()  # returns None, so the GRU output is left alone
        hook = self.net.gru.register_forward_hook(grab)
        self.net(batch)
        hook.remove()
        v = self.net.encode_reps(batch["H"], batch["D"], batch["fmask"], batch["feats"])
        vb = self.net.encode_reps(batch["base_H"], batch["base_D"], batch["base_fmask"], batch["base_feats"])
        expect = torch.cat([v, v - vb.mean(1, keepdim=True)], -1)
        torch.testing.assert_close(seen["x"], expect)

    def test_save_load_refuses_other_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "net.pt"
            self.net.save(p)
            again = TrueRehabNet.load(p, expected_contract=self.c).eval()
            batch = fake_batch(self.c, B=1, R=2)
            torch.testing.assert_close(again(batch)["fatigue"], self.net(batch)["fatigue"])
            with self.assertRaises(ValueError):
                TrueRehabNet.load(p, expected_contract=small_contract(angle_bins=16, db_span=30.0))

    def test_gradients_reach_every_parameter(self):
        net = TrueRehabNet(self.c).train()
        out = net(fake_batch(self.c, B=2, R=3))
        sum(o.pow(2).mean() for o in out.values()).backward()
        missing = [n for n, p in net.named_parameters() if p.grad is None or not p.grad.abs().sum()]
        self.assertEqual(missing, [])

    def test_chunked_frames_match(self):
        batch = fake_batch(self.c, B=1, R=2)
        ref = self.net(batch)["quality"]
        self.net.frame_chunk = 7
        torch.testing.assert_close(self.net(batch)["quality"], ref)


if __name__ == "__main__":
    unittest.main()
