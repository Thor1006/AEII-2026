import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from _util import small_contract
from trnet import calibrate as CB
from trnet import dataset as DS
from trnet import synth
from trnet import training as TRN
from trnet.network import HEADS, TrueRehabNet

STATS = CB.load_stats()


class DatasetTrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.c = small_contract()
        cls.folders = synth.make_dataset(cls.tmp / "fake", n_people=4, stats=STATS,
                                         plan=synth.Plan(sets=2, reps_per_set=5, set_rest_s=10))
        cls.sessions = [DS.build(f, cls.c, cache_dir=cls.tmp / "cache", log=lambda *a: None) for f in cls.folders]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_every_fake_session_is_used(self):
        self.assertTrue(all(s is not None for s in self.sessions))
        self.assertEqual(sorted(s.subject for s in self.sessions), ["F01", "F02", "F03", "F04"])
        for s in self.sessions:
            self.assertEqual(s.H.shape[1:], self.c.shapes()["H"])        # (32, 4, 64, 32): T=32 in these tests
            self.assertEqual(len(s.set_id), 10)

    def test_cache_round_trip(self):
        again = DS.build(self.folders[0], self.c, cache_dir=self.tmp / "cache")
        np.testing.assert_array_equal(again.H, self.sessions[0].H)
        np.testing.assert_array_equal(again.ymask, self.sessions[0].ymask)
        self.assertEqual(again.subject, "F01")

    def test_samples_are_sets_with_the_session_baseline(self):
        ds = DS.SetDataset(self.sessions, self.c)
        self.assertEqual(len(ds), 8)                       # 4 people x 2 sets
        item = ds[1]                                       # second set of the first session
        s = ds.sessions[0]
        torch.testing.assert_close(item["base_H"], torch.from_numpy(s.H[:3].astype(np.float32)))
        self.assertEqual(tuple(item["H"].shape), (5,) + self.c.shapes()["H"])
        b = DS.collate([ds[0], ds[1]])
        self.assertEqual(tuple(b["y"].shape), (2, 5, len(HEADS)))

    def test_leave_one_subject_out_never_leaks(self):
        subj = ["F01", "F02", "F03", "F04", "F05"]
        splits = DS.loso_splits(subj)
        self.assertEqual(sorted(t for t, _, _ in splits), subj)
        for test, val, train in splits:
            self.assertNotIn(test, train)
            self.assertNotIn(val, train)
            self.assertNotEqual(test, val)
            self.assertEqual(sorted(train + [test, val]), subj)
        with self.assertRaises(ValueError):
            DS.loso_splits(["F01", "F02"])

    def test_augmentation_hides_frames_and_keeps_ranges(self):
        ds = DS.SetDataset(self.sessions, self.c, augment=True, seed=1)
        item = ds[0]
        hidden = ~item["fmask"]
        self.assertTrue(0.03 < float(hidden.float().mean()) < 0.2)
        self.assertEqual(float(item["H"][hidden].abs().sum()), 0.0)
        self.assertTrue(float(item["H"][:, :, 0].min()) >= 0 and float(item["H"][:, :, 0].max()) <= 1)
        self.assertTrue(float(item["H"][:, :, 1].abs().max()) <= 1)

    def test_masked_labels_are_ignored(self):
        net = TrueRehabNet(self.c).eval()
        b = DS.collate([DS.SetDataset(self.sessions, self.c)[0]])
        out = net(b)
        loss, _ = TRN.loss_fn(out, b, {})
        b2 = {k: (v.clone() if torch.is_tensor(v) else v) for k, v in b.items()}
        b2["y"][~b2["ymask"]] = 7.0                                   # change only labels that are masked out
        self.assertAlmostEqual(float(TRN.loss_fn(out, b2, {})[0].detach()), float(loss.detach()), places=6)
        b2["ymask"][:] = False
        b2["aux_mask"][:] = False
        self.assertEqual(float(TRN.loss_fn(out, b2, {})[0].detach()), 0.0)

    def test_overfits_a_tiny_batch(self):
        """The network can learn 2 sets by heart: within 150 steps the loss falls below 30 % of its start and stays
        there for 10 steps in a row. It gets there at step ~6 (measured 2026-11-09), so the loop stops early:
        a few seconds instead of 49 s for all 150 steps."""
        torch.manual_seed(0)
        net = TrueRehabNet(self.c)
        net.drop.p = 0.0
        ds = DS.SetDataset(self.sessions[:1], self.c)
        b = DS.collate([ds[0], ds[1]])
        b["y"][..., 0] = torch.linspace(0, 1, b["y"].shape[1])        # something to learn
        opt = torch.optim.Adam(net.parameters(), lr=3e-3)
        first, value, below = None, None, 0
        for _ in range(150):
            loss, _ = TRN.loss_fn(net(b), b, {})
            value = float(loss.detach())
            first = first if first is not None else value
            below = below + 1 if value < 0.3 * first else 0
            if below == 10:
                break
            opt.zero_grad()
            loss.backward()
            opt.step()
        self.assertEqual(below, 10, f"loss {value:.4f} after 150 steps, start {first:.4f}")

    def test_short_loso_run(self):
        res = TRN.run_loso(self.sessions, self.c, torch.device("cpu"), epochs=4, patience=10, max_folds=2,
                           log=lambda *a: None)
        self.assertEqual(len(res), 2)
        for r in res:
            h = r["history"]
            self.assertLess(h[-1]["train_loss"], h[0]["train_loss"])
            self.assertIn("mae", r["metrics"]["quality"])
        s = TRN.summarize(res)
        self.assertIn("baseline_mae", s["fatigue"])


if __name__ == "__main__":
    unittest.main()
