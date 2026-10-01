"""Loopback-only, read-only bridge from WSL to Windows AnkiConnect.

Windows AnkiConnect stays bound to Windows 127.0.0.1:8765. The Korean adapter
continues using the configured WSL 127.0.0.1:18765 endpoint. This process never
accepts Anki write actions or listens on the LAN.
"""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess

from lute_korean_parser.anki.adapter import READ_ACTIONS


MAX_REQUEST_BYTES = 16_384
POWERSHELL = "powershell.exe"


def forward_read(payload):
    """Forward one validated AnkiConnect read operation to Windows loopback."""
    if not isinstance(payload, dict) or set(payload) != {"action", "version", "params"}:
        raise ValueError("Invalid AnkiConnect request envelope")
    if payload["action"] not in READ_ACTIONS or payload["version"] != 6:
        raise ValueError("The WSL bridge permits only AnkiConnect API v6 read actions")
    if not isinstance(payload["params"], dict):
        raise ValueError("AnkiConnect params must be an object")

    body = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf8")
    ).decode("ascii")
    command = (
        "$ProgressPreference='SilentlyContinue'; "
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$body=[System.Text.Encoding]::UTF8.GetString("
        f"[Convert]::FromBase64String('{body}')); "
        "try { $response=Invoke-WebRequest -UseBasicParsing "
        "-Uri 'http://127.0.0.1:8765' -Method Post "
        "-ContentType 'application/json' "
        "-Body ([System.Text.Encoding]::UTF8.GetBytes($body)) "
        "-TimeoutSec 120 -MaximumRedirection 0; "
        "[Console]::Write($response.Content) } "
        "catch { [Console]::Write($_.Exception.Message); exit 1 }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        timeout=130,
        check=False,
    )
    if result.returncode:
        detail = result.stdout.decode("utf-8-sig", errors="replace")[:240]
        raise RuntimeError("Windows AnkiConnect request failed: " + detail)
    response = json.loads(result.stdout.decode("utf-8-sig"))
    if not isinstance(response, dict) or set(response) != {"result", "error"}:
        raise ValueError("Windows AnkiConnect returned an invalid response")
    return response


class Handler(BaseHTTPRequestHandler):
    """Accept only bounded, schema-valid read calls on WSL loopback."""

    def log_message(self, *_args):
        pass  # Note content must not be logged by the bridge.

    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("Invalid or excessive AnkiConnect request size")
            payload = json.loads(self.rfile.read(length))
            response = forward_read(payload)
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            response = {"result": None, "error": str(exc)}
        data = json.dumps(response, ensure_ascii=False).encode("utf8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 18765), Handler) as server:
        server.daemon_threads = True
        print(
            "Read-only WSL Anki bridge: 127.0.0.1:18765 -> Windows 127.0.0.1:8765",
            flush=True,
        )
        server.serve_forever()
