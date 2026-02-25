#!/usr/bin/env python3
"""Take a screenshot of the OpenRCT2 web game using Playwright.

Starts a local COOP/COEP server, launches headless Chromium, waits for
the game canvas to appear and loading to finish, then captures a screenshot.

Usage:
    python3 screenshot_game.py --serve-dir build/www --output screenshot.png
    python3 screenshot_game.py --serve-dir build/www --output screenshot.png --port 9000 --wait-seconds 15
"""

import argparse
import os
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class COOPCOEPHandler(SimpleHTTPRequestHandler):
    """HTTP handler that adds Cross-Origin Isolation headers."""

    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        super().end_headers()

    def log_message(self, format, *args):
        """Suppress request logging to keep output clean."""
        pass


def start_server(directory, host="127.0.0.1", port=8000):
    """Start a COOP/COEP HTTP server in a background thread.

    Returns (server, thread) so the caller can shut it down.
    """
    handler = partial(COOPCOEPHandler, directory=directory)
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def take_screenshot(port=8000, output_path="screenshot.png", wait_seconds=10):
    """Launch headless Chromium and screenshot the OpenRCT2 game.

    Requires playwright to be installed with Chromium browser.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-features=SharedArrayBuffer"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        url = f"http://127.0.0.1:{port}/index.html"
        page.goto(url, wait_until="domcontentloaded")

        # Wait for the canvas to become visible
        page.wait_for_selector(
            "canvas#canvas",
            state="visible",
            timeout=wait_seconds * 1000,
        )

        # Wait for loading to finish — #loadingWebassembly is removed when done
        try:
            page.wait_for_selector(
                "#loadingWebassembly",
                state="detached",
                timeout=wait_seconds * 1000,
            )
        except Exception:
            # If the element never existed or was already gone, that's fine
            pass

        # Give the game a moment to render a frame
        time.sleep(2)

        page.screenshot(path=output_path, full_page=False)
        print(f"Screenshot saved to {output_path}")

        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Take a screenshot of the OpenRCT2 web game"
    )
    parser.add_argument(
        "--serve-dir", required=True,
        help="Directory containing the built wasm output (index.html etc.)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path for the screenshot PNG"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for the local server (default: 8000)"
    )
    parser.add_argument(
        "--wait-seconds", type=int, default=10,
        help="Max seconds to wait for game to load (default: 10)"
    )
    args = parser.parse_args()

    # Validate serve dir exists
    if not os.path.isdir(args.serve_dir):
        print(f"ERROR: serve directory does not exist: {args.serve_dir}")
        sys.exit(1)

    # Start server
    server, thread = start_server(args.serve_dir, port=args.port)
    print(f"Server started on http://127.0.0.1:{args.port}")

    try:
        take_screenshot(
            port=args.port,
            output_path=args.output,
            wait_seconds=args.wait_seconds,
        )
    finally:
        server.shutdown()
        print("Server stopped.")


if __name__ == "__main__":
    main()
