#!/usr/bin/env python3
"""Take a screenshot of OpenRCT2 running in headless Chromium.

Starts a local COOP/COEP-enabled HTTP server, launches Playwright
Chromium, waits for the game canvas to become visible, captures a
screenshot and writes it to *--output*.

Usage::

    python3 screenshot_game.py --serve-dir build/www --output screenshot.png
    python3 screenshot_game.py --serve-dir build/www --output shot.png --port 9000 --wait-seconds 15
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Embedded COOP/COEP server (mirrors serve-emscripten.py pattern)
# ---------------------------------------------------------------------------


class COOPCOEPHandler(SimpleHTTPRequestHandler):
    """HTTP handler that injects SharedArrayBuffer-enabling headers."""

    def end_headers(self) -> None:
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        super().end_headers()

    # Suppress per-request log lines during automated runs.
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def start_server(
    directory: str,
    host: str = "127.0.0.1",
    port: int = 0,
) -> tuple[ThreadingHTTPServer, int]:
    """Start a COOP/COEP HTTP server in a daemon thread.

    Parameters
    ----------
    directory:
        Filesystem path to serve.
    host:
        Bind address.
    port:
        Bind port.  Use ``0`` to let the OS pick a free port.

    Returns
    -------
    (server, actual_port)
        The running server instance and the port it actually bound to.
    """
    handler = partial(COOPCOEPHandler, directory=directory)
    server = ThreadingHTTPServer((host, port), handler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port


def stop_server(server: ThreadingHTTPServer) -> None:
    """Shut down a running server."""
    server.shutdown()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_serve_dir(serve_dir: str) -> Optional[str]:
    """Return an error string if *serve_dir* is not usable, else ``None``."""
    p = Path(serve_dir)
    if not p.is_dir():
        return f"--serve-dir does not exist or is not a directory: {serve_dir}"
    if not (p / "index.html").is_file():
        return f"--serve-dir does not contain index.html: {serve_dir}"
    return None


# ---------------------------------------------------------------------------
# Screenshot logic
# ---------------------------------------------------------------------------


def take_screenshot(
    serve_dir: str,
    output: str,
    port: int = 0,
    wait_seconds: int = 10,
) -> None:
    """Launch the game in headless Chromium and save a screenshot.

    Parameters
    ----------
    serve_dir:
        Directory containing the built wasm output (must have index.html).
    output:
        Filesystem path for the PNG screenshot.
    port:
        Port for the embedded HTTP server (0 = auto).
    wait_seconds:
        Max seconds to wait for the game canvas to become visible and
        for the loading element to be removed.
    """
    from playwright.sync_api import sync_playwright

    error = validate_serve_dir(serve_dir)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    server: Optional[ThreadingHTTPServer] = None
    try:
        server, actual_port = start_server(serve_dir, port=port)
        url = f"http://127.0.0.1:{actual_port}/index.html"
        print(f"Serving {serve_dir} at {url}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--enable-features=SharedArrayBuffer"],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")

            # Wait for canvas to appear and become visible.
            # In the game flow, canvas#canvas starts with display:none and
            # gets display="" once loading completes.
            page.wait_for_selector(
                "canvas#canvas",
                state="visible",
                timeout=wait_seconds * 1000,
            )

            # Wait for #loadingWebassembly to be removed from the DOM.
            try:
                page.wait_for_selector(
                    "#loadingWebassembly",
                    state="detached",
                    timeout=wait_seconds * 1000,
                )
            except Exception:
                # Element may already have been removed; that's fine.
                pass

            # Give the game a moment to render after loading completes.
            time.sleep(2)

            page.screenshot(path=output, full_page=False)
            print(f"Screenshot saved to {output}")

            browser.close()
    finally:
        if server is not None:
            stop_server(server)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Take a screenshot of OpenRCT2 running in headless Chromium.",
    )
    parser.add_argument(
        "--serve-dir",
        required=True,
        help="Directory containing the built wasm output (must contain index.html).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for the PNG screenshot.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the embedded HTTP server (default: 8000).",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=10,
        help="Seconds to wait for the game to load (default: 10).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    error = validate_serve_dir(args.serve_dir)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    take_screenshot(
        serve_dir=args.serve_dir,
        output=args.output,
        port=args.port,
        wait_seconds=args.wait_seconds,
    )


if __name__ == "__main__":
    main()
