# Plan: Kit pairing key (challenge-and-response) + signed commands

**Status:** approved — built, page side and mock verified; Python bridge untested until a Pi is really being set up (user: don't install its packages yet, ask again then)
**Date:** 2026-10-12

## Why
The page talks to the Pi over plain `ws://` with no check on who connects. Anyone on the same Wi-Fi can watch a patient's data and send start/stop commands, and a laptop can't tell a real kit from a fake one. We keep `ws://` (it works offline on the Pi) and add a shared secret key that proves **who** is connecting, without ever sending the key. See the chat discussion of 2026-10-12.

## Approach (protocol 1.2)
**Key:** 32 random bytes as hex, made once per kit. Stored on the Pi in `config.toml` (`key`) or a file (`key_file`, e.g. on the SD card's boot partition so it can be read from any computer). Printed on the kit's sticker as a link/QR.

**Handshake, before any data is sent**
1. Pi sends `challenge { nonce }` (16 random bytes, new each connection).
2. Browser replies `auth { cnonce, proof }`, where `proof = HMAC-SHA256(key, "trf-client" | nonce | cnonce | kitId)`.
3. Pi checks the proof (constant-time compare). Wrong or missing: close with code 4401 and a short delay.
4. Pi replies `authok { proof }` with `HMAC(key, "trf-server" | nonce | cnonce | kitId)`. The browser checks it, so a fake Pi on the same Wi-Fi is caught ("This isn't the kit you paired with").
5. Only then does the Pi send `hello` and the data stream.
6. Both sides derive `sessionKey = HMAC(key, "trf-session" | nonce | cnonce)`.

**Signed commands:** every `command` carries `ctr` (starts at 1, must increase) and `mac = HMAC(sessionKey, ctr | payload)`, where `payload` is the exact JSON string `{"name":…,"args":…}` that was sent (signing the raw string avoids JSON-formatting mismatches between JavaScript and Python). The Pi rejects bad MACs and repeated counters with `ack { ok:false, error }`. Radar frames and scores are **not** signed (CPU cost at 20 fps).

**Open mode stays possible:** a kit with no key behaves as today and says so in `hello` (`auth: "none"`). The dashboard then shows a warning banner: "This kit isn't protected with a key."

**Getting the key into the laptop:** the sticker link is `http://<kit>.local:8080/#/app?key=<hex>`. The part after `#` is never sent to a server. The page saves the key in the browser (per kit) and removes it from the address bar at once. If no key is saved, the connect screen asks for it ("Enter the kit key from the sticker").

**Rate limiting on the Pi:** after 5 wrong proofs in a minute from one address, refuse that address for a few minutes.

## Files touched
Frontend (`frontend/`)
- `src/lib/hmac.ts` — new: small pure-TypeScript SHA-256 + HMAC (browsers block built-in crypto on plain `http://` pages, so we can't use it). No new package.
- `src/lib/keystore.ts` — new: read `?key=` from the link, store per kit in `localStorage`, strip it from the URL.
- `src/sensor/protocol.ts` — version 1.2; new `challenge`, `auth`, `authok` types; `ctr`/`mac` on `command`; `auth` field in `hello`.
- `src/sensor/sources/WebSocketSource.ts` — run the handshake before accepting `hello`, verify the server proof, sign commands, map failures to friendly errors.
- `src/shell/SourceForm.tsx` / `StartScreen.tsx`, `shell/Banners.tsx` — key field, "wrong key" and "not protected" messages.
- `src/Root.tsx` — accept `#/app?key=…`.
- `mock-server/server.ts` — optional key so the whole flow can be tested without a Pi.
- `scripts/check-hmac.ts` — new: RFC 4231 test vectors for `hmac.ts`.

Pi bridge (`pi-bridge/`)
- `truerehab_bridge/auth.py` — new: nonce, HMAC, verify, session key, command MAC check, rate limiter.
- `truerehab_bridge/server.py` — handshake in `handler` before the viewer is registered; verify command MACs in `_on_text`.
- `truerehab_bridge/config.py`, `config.example.toml` — `key`, `key_file`.
- `truerehab_bridge/__main__.py` — `--new-key` (prints key + pairing link, warns if none set); `web.py` / `truerehab-bridge.json` must never expose the key.
- `tests/test_auth.py` — new; `check_bridge.py` — `--key` plus `BREAK=` modes (wrong key, unsigned command, fake server) that must fail.
- `README.md` — "Pairing a kit" section.

Docs
- `CLAUDE/DECISIONS.md` entry after it's built.

## Risks / needs OK
- **Still not encrypted.** Data stays readable on the Wi-Fi, and someone who actively relays traffic can read it. The key proves who, not privacy. To be written in the README.
- **Anyone with the sticker or SD card has the key.** Fine for a prototype; owner binding is a later step.
- **Running the Python side needs the pi-bridge packages installed** (still paused from 2026-10-11). I will ask before running `pip install`.
- **Optional QR:** printing a QR code in the terminal needs the `qrcode` package. I will not install it unless you say so; by default `--new-key` prints the link and you make the QR elsewhere.
- Two sides written in two languages must agree byte for byte; the test vectors and a cross-check script cover this.

## How we'll verify
- `scripts/check-hmac.ts` passes the RFC test vectors; `npm run typecheck` and `npm run build` pass.
- Mock server with a key, in the browser pane: right key connects and start/stop works; wrong key shows the friendly error; a mock with a different key is rejected as "not your kit"; link with `?key=` is saved and stripped from the address bar; a kit without a key shows the warning banner.
- Replay and tamper checks by script: reused counter, changed args and a missing `mac` are all refused.
- Python (after you OK the install): `pytest`, then `check_bridge.py --key …` passes and each `BREAK=` mode fails as it should.
- Update `CLAUDE/CONTEXT.md` and run `/wrap-up` at the end.
