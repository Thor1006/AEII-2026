"""Kit key tests: python -m unittest discover -s tests (from pi-bridge/). auth.py needs no extra packages."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from truerehab_bridge.auth import Handshake, RateLimiter, clean_key, generate_key, hmac_hex, load_key  # noqa: E402

# Computed with Node's crypto (independent of both our implementations). frontend/scripts/check-hmac.ts uses the same numbers.
KEY = bytes(range(32))
NONCE, CNONCE, KIT = "aa" * 16, "bb" * 16, "KIT-01"
CLIENT_PROOF = "d812712172cffd3cea59f19e23fd739c26ee34f8cab9d71f41cca09bbfd39888"
SERVER_PROOF = "a7abde7e8cbcd0666486c15a5f565a0e48104b28c18a4338b748dedcfdbd5e1d"
SESSION_KEY = "d847b4a94ef32663f751f2326d377edc98f66e05c8d5189776a7cca0e3a3201a"
PAYLOAD = '{"name":"marker","args":{"label":"hi"}}'
MAC_CTR1 = "553023090ff90a7497d4f37817c6ee70bf323b45d1410a03500c85e09dfbfdd8"


def passed_handshake() -> Handshake:
    hs = Handshake(KEY, KIT, nonce=NONCE)
    assert hs.check_auth({"type": "auth", "cnonce": CNONCE, "proof": CLIENT_PROOF})
    return hs


class Vectors(unittest.TestCase):
    def test_proofs_match_node(self) -> None:
        self.assertEqual(hmac_hex(KEY, "trf-client", NONCE, CNONCE, KIT), CLIENT_PROOF)
        self.assertEqual(hmac_hex(KEY, "trf-server", NONCE, CNONCE, KIT), SERVER_PROOF)

    def test_session_key_matches_node(self) -> None:
        self.assertEqual(passed_handshake().session_key.hex(), SESSION_KEY)  # type: ignore[union-attr]

    def test_command_mac_matches_node(self) -> None:
        self.assertEqual(hmac_hex(bytes.fromhex(SESSION_KEY), 1, PAYLOAD), MAC_CTR1)


class HandshakeTests(unittest.TestCase):
    def test_right_proof_gives_server_proof(self) -> None:
        hs = Handshake(KEY, KIT, nonce=NONCE)
        self.assertEqual(hs.check_auth({"type": "auth", "cnonce": CNONCE, "proof": CLIENT_PROOF}), SERVER_PROOF)

    def test_wrong_proofs_refused(self) -> None:
        bad = [
            {"type": "auth", "cnonce": CNONCE, "proof": "0" * 64},
            {"type": "auth", "cnonce": "cc" * 16, "proof": CLIENT_PROOF},  # proof was for another cnonce
            {"type": "auth", "cnonce": CNONCE},
            {"type": "auth", "proof": CLIENT_PROOF},
            {"type": "auth", "cnonce": 5, "proof": CLIENT_PROOF},
            {"type": "auth", "cnonce": "", "proof": CLIENT_PROOF},
            {"type": "ping", "cnonce": CNONCE, "proof": CLIENT_PROOF},
            {},
        ]
        for msg in bad:
            self.assertIsNone(Handshake(KEY, KIT, nonce=NONCE).check_auth(msg), msg)

    def test_other_kits_key_refused(self) -> None:
        hs = Handshake(bytes(reversed(range(32))), KIT, nonce=NONCE)
        self.assertIsNone(hs.check_auth({"type": "auth", "cnonce": CNONCE, "proof": CLIENT_PROOF}))

    def test_kit_id_is_part_of_the_proof(self) -> None:
        hs = Handshake(KEY, "KIT-02", nonce=NONCE)
        self.assertIsNone(hs.check_auth({"type": "auth", "cnonce": CNONCE, "proof": CLIENT_PROOF}))

    def test_nonce_is_fresh(self) -> None:
        self.assertNotEqual(Handshake(KEY, KIT).nonce, Handshake(KEY, KIT).nonce)
        self.assertEqual(len(Handshake(KEY, KIT).nonce), 32)

    def test_no_commands_before_handshake(self) -> None:
        hs = Handshake(KEY, KIT, nonce=NONCE)
        self.assertIsNone(hs.read_command({"ctr": 1, "payload": PAYLOAD, "mac": MAC_CTR1}))


class SignedCommands(unittest.TestCase):
    def msg(self, ctr: int = 1, payload: str = PAYLOAD, mac: str | None = None) -> dict:
        sk = bytes.fromhex(SESSION_KEY)
        return {"type": "command", "id": 1, "ctr": ctr, "payload": payload, "mac": mac or hmac_hex(sk, ctr, payload)}

    def test_good_command(self) -> None:
        self.assertEqual(passed_handshake().read_command(self.msg(mac=MAC_CTR1)), ("marker", {"label": "hi"}))

    def test_replay_refused(self) -> None:
        hs = passed_handshake()
        self.assertIsNotNone(hs.read_command(self.msg(1)))
        self.assertIsNone(hs.read_command(self.msg(1)))

    def test_old_counter_refused_even_if_valid(self) -> None:
        hs = passed_handshake()
        self.assertIsNotNone(hs.read_command(self.msg(5)))
        self.assertIsNone(hs.read_command(self.msg(3)))

    def test_counter_may_skip_ahead(self) -> None:
        hs = passed_handshake()
        self.assertIsNotNone(hs.read_command(self.msg(1)))
        self.assertIsNotNone(hs.read_command(self.msg(7)))

    def test_edited_payload_refused(self) -> None:
        self.assertIsNone(passed_handshake().read_command(self.msg(mac=MAC_CTR1, payload=PAYLOAD.replace("hi", "ho"))))

    def test_wrong_mac_refused(self) -> None:
        self.assertIsNone(passed_handshake().read_command(self.msg(mac="0" * 64)))

    def test_bad_shapes_refused(self) -> None:
        sk = bytes.fromhex(SESSION_KEY)
        for m in (
            {"ctr": "1", "payload": PAYLOAD, "mac": MAC_CTR1},
            {"ctr": True, "payload": PAYLOAD, "mac": hmac_hex(sk, True, PAYLOAD)},
            {"ctr": 1, "payload": 5, "mac": MAC_CTR1},
            {"ctr": 1, "payload": PAYLOAD},
            {"ctr": 1, "mac": MAC_CTR1},
            {"id": 1, "name": "marker", "args": {}},  # the old unsigned shape
        ):
            self.assertIsNone(passed_handshake().read_command(m), m)

    def test_signed_garbage_payload_refused(self) -> None:
        sk = bytes.fromhex(SESSION_KEY)
        for payload in ("not json", "[]", '{"name":5}', '{"name":"x","args":[1]}'):
            self.assertIsNone(passed_handshake().read_command({"ctr": 1, "payload": payload, "mac": hmac_hex(sk, 1, payload)}), payload)


class RateLimiterTests(unittest.TestCase):
    def test_locks_after_five_and_frees_after_window(self) -> None:
        rl = RateLimiter(max_failures=5, window_s=60)
        for i in range(4):
            rl.fail("1.2.3.4", now=100 + i)
        self.assertFalse(rl.locked("1.2.3.4", now=104))
        rl.fail("1.2.3.4", now=104)
        self.assertTrue(rl.locked("1.2.3.4", now=105))
        self.assertFalse(rl.locked("5.6.7.8", now=105))  # other addresses unaffected
        self.assertFalse(rl.locked("1.2.3.4", now=170))  # window passed


class KeyHandling(unittest.TestCase):
    def test_generated_keys_look_right_and_differ(self) -> None:
        a, b = generate_key(), generate_key()
        self.assertEqual(len(a), 64)
        self.assertNotEqual(a, b)
        self.assertEqual(clean_key(a), a)

    def test_clean_key(self) -> None:
        self.assertEqual(clean_key(" AB-" + "0" * 62 + " "), "ab" + "0" * 62)
        for bad in ("", "abc", "g" * 64, "0" * 63, "0" * 65):
            self.assertIsNone(clean_key(bad), bad)

    def test_load_key_variants(self) -> None:
        self.assertIsNone(load_key("", ""))
        k = generate_key()
        self.assertEqual(load_key(k), k)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "trh-key.txt"
            f.write_text(k + "\n")
            self.assertEqual(load_key("", f), k)
        with self.assertRaises(ValueError):
            load_key("tooshort")
        with self.assertRaises(ValueError):
            load_key("", "/no/such/file")


# These need the packages from requirements.txt (websockets, numpy); skipped if they aren't installed.
try:
    from truerehab_bridge.config import BridgeConfig
    from truerehab_bridge.providers import SyntheticProvider
    from truerehab_bridge.server import Bridge

    HAVE_BRIDGE = True
except ImportError:
    HAVE_BRIDGE = False


@unittest.skipUnless(HAVE_BRIDGE, "websockets/numpy not installed")
class BridgeCommands(unittest.TestCase):
    def bridge(self, key: str = "") -> Bridge:
        return Bridge(BridgeConfig(kit_id=KIT, key=key), [SyntheticProvider()])

    def test_open_kit_still_takes_plain_commands_and_says_so(self) -> None:
        b = self.bridge()
        self.assertEqual(b.hello()["auth"], "none")
        reply = b._on_text(json.dumps({"type": "command", "id": 1, "name": "marker", "args": {"label": "x"}}))
        self.assertTrue(reply and reply["ok"])

    def test_protected_kit_refuses_unsigned_commands(self) -> None:
        b = self.bridge(KEY.hex())
        self.assertEqual(b.hello()["auth"], "hmac-sha256")
        hs = passed_handshake()
        for raw in (
            {"type": "command", "id": 1, "name": "marker", "args": {"label": "x"}},
            {"type": "command", "id": 2, "ctr": 1, "payload": PAYLOAD, "mac": "0" * 64},
        ):
            reply = b._on_text(json.dumps(raw), hs)
            self.assertEqual(reply and reply["ok"], False, raw)
        self.assertIsNone(b._on_text(json.dumps({"type": "command", "id": 3, "name": "marker"}), None) and None)

    def test_protected_kit_runs_signed_commands_once(self) -> None:
        b = self.bridge(KEY.hex())
        hs = passed_handshake()
        raw = json.dumps({"type": "command", "id": 5, "ctr": 1, "payload": PAYLOAD, "mac": MAC_CTR1})
        first = b._on_text(raw, hs)
        self.assertTrue(first and first["ok"], first)
        again = b._on_text(raw, hs)
        self.assertTrue(again and not again["ok"] and "signed" in again["error"], again)

    def test_wrong_key_config_fails_at_startup(self) -> None:
        with self.assertRaises(ValueError):
            self.bridge("nothex")


if __name__ == "__main__":
    unittest.main()
