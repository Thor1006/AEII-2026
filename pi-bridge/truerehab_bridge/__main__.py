"""
Start the bridge:
    python -m truerehab_bridge                     # synthetic demo data, defaults
    python -m truerehab_bridge --config config.toml
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import __version__
from .config import load_config
from .server import Bridge, build_providers
from .system import lan_ip, mdns_name
from .web import start_web_server


def main() -> int:
    ap = argparse.ArgumentParser(prog="truerehab_bridge", description="Send TrueRehab sensor data to the web dashboard.")
    ap.add_argument("--config", "-c", help="TOML config file (see config.example.toml)")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    try:
        cfg = load_config(args.config)
        providers = build_providers(cfg)
    except (OSError, ValueError) as exc:
        print(f"Config problem: {exc}", file=sys.stderr)
        return 2

    bridge = Bridge(cfg, providers)
    host_names = [mdns_name(), *([ip] if (ip := lan_ip()) else [])]

    if cfg.http_port:
        info = {"ws": f"ws://{cfg.host}:{cfg.ws_port}", "wsPort": cfg.ws_port, "name": cfg.name, "kitId": cfg.kit_id}
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


if __name__ == "__main__":
    sys.exit(main())
