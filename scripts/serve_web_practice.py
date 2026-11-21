"""Serve only the practice assets and write a fixed, local training receipt."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "web-practice"
RECEIPT = ROOT / "runs" / "web-practice-complete.json"
PIZZA_RECEIPT = ROOT / "runs" / "pizza-complete.json"
KSEB_RECEIPT = ROOT / "runs" / "kseb-complete.json"
WORKSPACE_KEY = hashlib.sha256(os.fsencode(ROOT)).hexdigest().encode("ascii")
ASSETS = {
    "/": ("index.html", "text/html"),
    "/practice.css": ("practice.css", "text/css"),
    "/practice.js": ("practice.js", "text/javascript"),
    "/pizza": ("pizza.html", "text/html"),
    "/pizza.css": ("pizza.css", "text/css"),
    "/pizza.js": ("pizza.js", "text/javascript"),
    "/kseb-quickpay": ("kseb-quickpay.html", "text/html"),
    "/kseb.css": ("kseb.css", "text/css"),
    "/kseb.js": ("kseb.js", "text/javascript"),
}
# Generated images for the KSEB practice copy: a fixed placeholder "captcha" and a refresh arrow.
GENERATED = {
    "/kseb-captcha.svg": b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60" viewBox="0 0 200 60">'
        b'<rect width="200" height="60" fill="#eee"/><path d="M0 40 C50 10 150 70 200 20" stroke="#999" fill="none"/>'
        b'<text x="100" y="40" font-family="monospace" font-size="28" text-anchor="middle" fill="#333">PRACTICE</text></svg>',
    "/kseb-refresh.svg": b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
        b'<path d="M12 4a8 8 0 1 0 8 8h-2a6 6 0 1 1-6-6v3l4-4-4-4z" fill="#1b5e8c"/></svg>',
}
# POST route -> (receipt file, task name). Receipts hold no form data.
RECEIPTS = {"/receipt": (RECEIPT, "web_practice"), "/pizza-receipt": (PIZZA_RECEIPT, "pizza_practice"),
            "/kseb-receipt": (KSEB_RECEIPT, "kseb_practice")}


def write_receipt(path: Path = RECEIPT, task: str = "web_practice") -> None:
    path.parent.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete_on_close=False) as file:
        json.dump({"task": task, "synthetic": True,
                   "completed_at": datetime.now(timezone.utc).isoformat()}, file)
        file.close()
        os.replace(file.name, path)


class PracticeHandler(BaseHTTPRequestHandler):
    @property
    def host(self) -> str:
        return f"127.0.0.1:{self.server.server_port}"

    def respond(self, data: bytes, media_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", f"{media_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.headers.get("Host") != self.host:
            self.send_error(403)
        elif self.path == "/health":
            self.respond(WORKSPACE_KEY, "text/plain")
        elif self.path in GENERATED:
            self.respond(GENERATED[self.path], "image/svg+xml")
        elif self.path in ASSETS:
            filename, media_type = ASSETS[self.path]
            self.respond((APP / filename).read_bytes(), media_type)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in RECEIPTS:
            self.send_error(404)
        elif self.headers.get("Host") != self.host or self.headers.get("Origin") != f"http://{self.host}":
            self.send_error(403)
        elif self.headers.get("Content-Length", "0") != "0" or self.headers.get("Transfer-Encoding"):
            self.send_error(400, "Practice receipts must not contain form data")
        else:
            try:
                write_receipt(*RECEIPTS[self.path])
            except OSError:
                self.send_error(500, "Could not save the local receipt")
            else:
                self.respond(b'{"saved": true}', "application/json")

    def log_message(self, format: str, *args) -> None:
        pass


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("CONDUCTOR_PORT") or "8765")), PracticeHandler) as server:
        print(f"Web practice listening on http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()
