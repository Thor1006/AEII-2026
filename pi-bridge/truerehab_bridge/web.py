"""
Serves the built dashboard (frontend/dist) over plain HTTP, plus /truerehab-bridge.json
so the page knows it was served by a bridge and connects by itself.
Runs in a background thread with the standard library's HTTP server.
"""
from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MISSING_BUILD = """<!doctype html><meta charset="utf-8"><title>TrueRehab bridge</title>
<body style="font-family:system-ui;max-width:40em;margin:3em auto;line-height:1.5">
<h1>The bridge is running</h1>
<p>But the dashboard isn't built yet, so there's nothing to show here.</p>
<p>On a computer with Node.js, in the <code>frontend/</code> folder, run <code>npm run build</code>,
then copy <code>frontend/dist</code> to the Pi (path set by <code>web_root</code> in the config).</p>
<p>WebSocket data is available on port {ws_port}.</p>"""


class _Handler(SimpleHTTPRequestHandler):
    bridge_info: dict[str, Any] = {}
    web_root: Path = Path(".")

    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        path = self.path.split("?", 1)[0]
        if path.endswith("/truerehab-bridge.json"):
            self._send(200, "application/json", json.dumps(self.bridge_info).encode())
            return
        if not (self.web_root / "index.html").exists():
            self._send(200, "text/html; charset=utf-8", MISSING_BUILD.format(ws_port=self.bridge_info.get("wsPort")).encode())
            return
        super().do_GET()

    def end_headers(self) -> None:
        # index.html must not be cached, or phones keep an old dashboard after an update.
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # quiet
        pass


def start_web_server(host: str, port: int, web_root: Path, bridge_info: dict[str, Any]) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"bridge_info": bridge_info, "web_root": web_root})
    server = ThreadingHTTPServer((host, port), partial(handler, directory=str(web_root)))
    threading.Thread(target=server.serve_forever, name="web", daemon=True).start()
    return server
