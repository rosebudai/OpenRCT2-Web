"""Tests for screenshot_game.py -- server and validation helpers only.

Does NOT test the full Playwright flow (that requires a real wasm build).
"""

import os
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screenshot_game import start_server, stop_server, validate_serve_dir


def test_server_starts_and_stops():
    """Start the COOP/COEP server on a temp dir, make an HTTP request,
    verify COOP/COEP headers are present, then stop the server."""
    with tempfile.TemporaryDirectory() as d:
        # Create a minimal index.html to serve
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write("<html><body>hello</body></html>")

        # Port 0 = OS picks a free port, avoiding conflicts
        server, port = start_server(d, host="127.0.0.1", port=0)
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html")
            body = resp.read().decode()
            assert "hello" in body

            # Verify required cross-origin isolation headers
            coop = resp.headers.get("Cross-Origin-Opener-Policy")
            coep = resp.headers.get("Cross-Origin-Embedder-Policy")
            corp = resp.headers.get("Cross-Origin-Resource-Policy")
            assert coop == "same-origin", f"Expected same-origin, got {coop}"
            assert coep == "require-corp", f"Expected require-corp, got {coep}"
            assert corp == "cross-origin", f"Expected cross-origin, got {corp}"
        finally:
            stop_server(server)


def test_missing_serve_dir():
    """validate_serve_dir returns an error when the directory doesn't exist."""
    error = validate_serve_dir("/nonexistent/path/abc123")
    assert error is not None
    assert "does not exist" in error


def test_missing_index_html():
    """validate_serve_dir returns an error when index.html is absent."""
    with tempfile.TemporaryDirectory() as d:
        error = validate_serve_dir(d)
        assert error is not None
        assert "index.html" in error


def test_valid_serve_dir():
    """validate_serve_dir returns None for a valid directory."""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write("<html></html>")
        error = validate_serve_dir(d)
        assert error is None
