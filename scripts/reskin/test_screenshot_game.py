"""Tests for screenshot_game.py (server and error handling only).

Does NOT test the full Playwright flow — that requires a wasm build.
"""

import os
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screenshot_game import start_server


def test_server_starts_and_stops():
    """Verify the COOP/COEP server can start, serve, and stop cleanly."""
    with tempfile.TemporaryDirectory() as d:
        # Create a minimal index.html to serve
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write("<html><body>test</body></html>")

        server, thread = start_server(d, host="127.0.0.1", port=18765)
        try:
            # Give server a moment to start
            time.sleep(0.2)

            # Fetch the page
            resp = urllib.request.urlopen("http://127.0.0.1:18765/index.html")
            body = resp.read().decode()
            assert "test" in body

            # Verify COOP/COEP headers
            coop = resp.headers.get("Cross-Origin-Opener-Policy")
            coep = resp.headers.get("Cross-Origin-Embedder-Policy")
            assert coop == "same-origin"
            assert coep == "require-corp"
        finally:
            server.shutdown()


def test_missing_serve_dir():
    """Verify graceful error when serve directory doesn't exist."""
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "screenshot_game.py"),
         "--serve-dir", "/nonexistent/path/abc123",
         "--output", "/tmp/test.png"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr or "does not exist" in result.stdout
