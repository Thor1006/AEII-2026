"""
Kit key: proves who is connecting, without sending the key (protocol 1.2).

Handshake, before any data is sent:
  Pi    -> challenge {nonce}                              nonce: 16 random bytes, hex, new every connection
  web   -> auth {cnonce, proof}                           proof = HMAC(key, "trf-client|nonce|cnonce|kitId")
  Pi    -> authok {proof}                                 proof = HMAC(key, "trf-server|nonce|cnonce|kitId")
Both sides then derive  session_key = HMAC(key, "trf-session|nonce|cnonce")  and the web side signs every command:
  command {id, ctr, payload, mac}                          mac = HMAC(session_key, "<ctr>|<payload>"); ctr increases

This proves who, not privacy: the data itself is still plain text on the Wi-Fi.
Mirrors frontend/src/lib/hmac.ts and frontend/mock-server/server.ts. Standard library only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KEY_RE = re.compile(r"^[0-9a-f]{64}$")
#: After this many wrong keys from one address in WINDOW_S, that address is refused until the window passes.
MAX_FAILURES = 5
WINDOW_S = 60.0


def generate_key() -> str:
    return secrets.token_hex(32)


def clean_key(text: str) -> str | None:
    """Lower-case, drop spaces and dashes, check it looks like a key. None if not."""
    k = re.sub(r"[\s-]", "", text).lower()
    return k if KEY_RE.match(k) else None


def load_key(key: str = "", key_file: str | Path = "") -> str | None:
    """The configured key, or None for an open kit. Raises ValueError if one is set but malformed."""
    raw = key
    if not raw and key_file:
        try:
            raw = Path(key_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Can't read key_file {key_file}: {exc}") from exc
    if not raw.strip():
        return None
    cleaned = clean_key(raw)
    if cleaned is None:
        raise ValueError("The kit key must be 64 letters and numbers (0-9, a-f). Make one with: python -m truerehab_bridge --new-key")
    return cleaned


def hmac_hex(key: bytes, *parts: Any) -> str:
    return hmac.new(key, "|".join(str(p) for p in parts).encode("utf-8"), hashlib.sha256).hexdigest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@dataclass
class Handshake:
    """One connection's handshake and, once passed, its command signing state."""

    key: bytes
    kit_id: str
    nonce: str = field(default_factory=lambda: secrets.token_hex(16))
    session_key: bytes | None = None
    last_ctr: int = 0

    def challenge(self) -> dict[str, Any]:
        return {"type": "challenge", "nonce": self.nonce, "kitId": self.kit_id}

    def check_auth(self, msg: dict[str, Any]) -> str | None:
        """Verify the viewer's `auth` message. Returns our `authok` proof, or None if it's wrong."""
        cnonce, proof = msg.get("cnonce"), msg.get("proof")
        if msg.get("type") != "auth" or not isinstance(cnonce, str) or not isinstance(proof, str) or not 0 < len(cnonce) <= 64:
            return None
        if not same(proof, hmac_hex(self.key, "trf-client", self.nonce, cnonce, self.kit_id)):
            return None
        self.session_key = hmac.new(self.key, f"trf-session|{self.nonce}|{cnonce}".encode(), hashlib.sha256).digest()
        return hmac_hex(self.key, "trf-server", self.nonce, cnonce, self.kit_id)

    def read_command(self, msg: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        """For a signed `command`: (name, args) if the counter and MAC are right, else None."""
        if self.session_key is None:
            return None
        ctr, payload, mac = msg.get("ctr"), msg.get("payload"), msg.get("mac")
        if not isinstance(ctr, int) or isinstance(ctr, bool) or not isinstance(payload, str) or not isinstance(mac, str):
            return None
        if ctr <= self.last_ctr:  # a copy of an old command
            return None
        if not same(mac, hmac_hex(self.session_key, ctr, payload)):
            return None
        self.last_ctr = ctr
        try:
            body = json.loads(payload)
        except ValueError:
            return None
        if not isinstance(body, dict):
            return None
        name, args = body.get("name"), body.get("args") or {}
        if not isinstance(name, str) or not isinstance(args, dict):
            return None
        return name, args


class RateLimiter:
    """Counts wrong keys per address."""

    def __init__(self, max_failures: int = MAX_FAILURES, window_s: float = WINDOW_S) -> None:
        self.max = max_failures
        self.window = window_s
        self._fails: dict[str, list[float]] = {}

    def _recent(self, who: str, now: float) -> list[float]:
        recent = [t for t in self._fails.get(who, []) if now - t < self.window]
        if recent:
            self._fails[who] = recent
        else:
            self._fails.pop(who, None)
        return recent

    def locked(self, who: str, now: float | None = None) -> bool:
        return len(self._recent(who, time.monotonic() if now is None else now)) >= self.max

    def fail(self, who: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._recent(who, now)
        self._fails.setdefault(who, []).append(now)
