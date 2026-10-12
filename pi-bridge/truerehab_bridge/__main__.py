"""
Start the bridge:
    python -m truerehab_bridge                     # synthetic demo data, defaults
    python -m truerehab_bridge --config config.toml
    python -m truerehab_bridge --new-key             # make a kit key and its sticker link
    python -m truerehab_bridge -c config.toml --show-link   # print the sticker link for the key in the config
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .auth import generate_key
from .config import load_config
from .server import Bridge, build_providers
from .system import lan_ip, mdns_name
from .web import start_web_server


def main() -> int:
    ap = argparse.ArgumentParser(prog="truerehab_bridge", description="Send TrueRehab sensor data to the web dashboard.")
    ap.add_argument("--config", "-c", help="TOML config file (see config.example.toml)")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--new-key", action="store_true", help="Make a new kit key, print it with its sticker link, and exit")
    ap.add_argument("--write", metavar="FILE", help="With --new-key: save the key to this file (never overwrites; owner-only)")
    ap.add_argument("--show-link", action="store_true", help="Print the sticker link for the key in --config, and exit")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    if args.new_key:
        return _new_key(args.config, args.write)

    try:
        cfg = load_config(args.config)
        if args.show_link:
            return _show_link(cfg)
        providers = build_providers(cfg)
    except (OSError, ValueError) as exc:
        print(f"Config problem: {exc}", file=sys.stderr)
        return 2

    bridge = Bridge(cfg, providers)
    key = cfg.resolved_key()
    host_names = [mdns_name(), *([ip] if (ip := lan_ip()) else [])]

    if cfg.http_port:
        info = {"ws": f"ws://{cfg.host}:{cfg.ws_port}", "wsPort": cfg.ws_port, "name": cfg.name, "kitId": cfg.kit_id, "auth": bool(key)}
        try:
            start_web_server(cfg.host, cfg.http_port, cfg.web_root, info)
        except OSError as exc:
            print(f"Can't serve the dashboard on port {cfg.http_port}: {exc}", file=sys.stderr)
            return 2

    print(f"\nTrueRehab bridge {__version__} · {cfg.name} ({cfg.kit_id})")
    if cfg.http_port:
        print("  Open on a phone or laptop on the same Wi-Fi:")
        for h in host_names:
            print(f"     http://{h}:{cfg.http_port}")
        if not (cfg.web_root / "index.html").exists():
            print(f"  ! Dashboard not built: {cfg.web_root} has no index.html (run `npm run build` in frontend/)")
    print(f"  WebSocket: ws://{host_names[-1]}:{cfg.ws_port}")
    if key:
        print(f"  Kit key: ON (ends …{key[-4:]}). Viewers must prove they know it. Sticker link: --show-link")
    else:
        print("  ! No kit key: anyone on this Wi-Fi can see the data and start sessions. Make one: python -m truerehab_bridge --new-key")
    for p in providers:
        print(f"  Provider: {p.name}{'  (SYNTHETIC DATA)' if p.synthetic else ''}")
    print("  Stop with Ctrl+C\n")

    try:
        asyncio.run(bridge.serve_forever())
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"Can't open the WebSocket port {cfg.ws_port}: {exc}", file=sys.stderr)
        return 2
    return 0


def _links(key: str, http_port: int) -> list[str]:
    names = [mdns_name(), *([ip] if (ip := lan_ip()) else [])]
    port = http_port or 8080
    return [f"http://{h}:{port}/#/app?key={key}" for h in names]


def _new_key(config: str | None, write: str | None) -> int:
    http_port = 8080
    if config:
        try:
            http_port = load_config(config).http_port
        except (OSError, ValueError):
            pass
    key = generate_key()
    if write:
        path = Path(write)
        if path.exists():
            print(f"Not overwriting {path}. Delete it first if you really want a new key.", file=sys.stderr)
            return 2
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key + "\n")
        print(f"Saved the key to {path}. Point key_file at it in config.toml.")
    print("\nNew kit key (keep it secret; print it on the kit's sticker):\n")
    print(f"  {key}\n")
    if not write:
        print('Put it in config.toml under [bridge]:   key_file = "/boot/firmware/trh-key.txt"   (a file holding the key)')
        print("or, simpler for testing:               key = \"<the key above>\"\n")
    print("Sticker link (make a QR code from it; the key after # is never sent to a server):")
    for link in _links(key, http_port):
        print(f"  {link}")
    print("\nThe page saves the key in the browser and removes it from the address bar.")
    return 0


def _show_link(cfg) -> int:  # type: ignore[no-untyped-def]
    key = cfg.resolved_key()
    if not key:
        print("This config has no key. Make one with: python -m truerehab_bridge --new-key", file=sys.stderr)
        return 2
    for link in _links(key, cfg.http_port):
        print(link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
