#!/usr/bin/env python3
"""Verify restyled sprites render correctly using Playwright.

Creates a comparison HTML page showing original vs restyled sprites side by side,
serves it, takes a screenshot with Playwright, and optionally judges the result
with Gemini CLI.

Usage:
    python3 verify_sprites.py --originals ./sprites_original --restyled ./sprites_restyled
    python3 verify_sprites.py --originals ./sprites_original --restyled ./sprites_restyled --judge
"""

import os
import sys
import json
import argparse
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


COMPARISON_HTML = """<!DOCTYPE html>
<html>
<head>
<title>Sprite Reskin Verification</title>
<style>
  body {{
    background: #1a1a2e; color: #eee; font-family: monospace;
    margin: 20px; font-size: 14px;
  }}
  h1 {{ color: #e94560; margin-bottom: 5px; }}
  .info {{ color: #888; margin-bottom: 20px; }}
  table {{ border-collapse: collapse; }}
  th {{ padding: 8px 16px; text-align: center; color: #e94560; font-size: 16px; }}
  td {{
    padding: 8px 16px; text-align: center; vertical-align: middle;
    border: 1px solid #333;
  }}
  td.sprite {{
    background: repeating-conic-gradient(#2a2a3e 0% 25%, #1a1a2e 0% 50%) 50% / 16px 16px;
    min-width: 80px; min-height: 60px;
  }}
  img {{
    image-rendering: pixelated;
    display: block; margin: 0 auto;
  }}
  .filename {{ color: #888; font-size: 11px; }}
  .zoom-4x td.sprite {{
    padding: 40px 48px;
    overflow: hidden;
  }}
  .zoom-4x img {{ transform: scale(4); }}
  #status {{
    position: fixed; bottom: 10px; right: 10px;
    background: #16213e; padding: 8px 12px; border-radius: 4px;
    border: 1px solid #e94560;
  }}
</style>
</head>
<body>
<h1>Sprite Reskin Verification</h1>
<div class="info">{sprite_count} sprites &bull; {timestamp}</div>

<h2>1x (Original Size)</h2>
<table>
<tr><th>File</th><th>Original</th><th>Restyled</th></tr>
{rows_1x}
</table>

<h2>4x (Zoomed)</h2>
<table class="zoom-4x">
<tr><th>File</th><th>Original</th><th>Restyled</th></tr>
{rows_4x}
</table>

<div id="status">Rendered OK</div>
</body>
</html>
"""


def build_comparison_page(originals_dir, restyled_dir, output_dir):
    """Build an HTML comparison page with original vs restyled sprites.

    Copies sprites into output_dir and generates index.html.
    Returns path to index.html.
    """
    os.makedirs(os.path.join(output_dir, "orig"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "restyled"), exist_ok=True)

    # Find matching files
    orig_files = set(f for f in os.listdir(originals_dir) if f.lower().endswith(".png"))
    rest_files = set(f for f in os.listdir(restyled_dir) if f.lower().endswith(".png"))
    common = sorted(orig_files & rest_files)

    if not common:
        print(f"ERROR: No matching PNG files between {originals_dir} and {restyled_dir}")
        return None

    # Copy sprites
    for f in common:
        shutil.copy2(os.path.join(originals_dir, f), os.path.join(output_dir, "orig", f))
        shutil.copy2(os.path.join(restyled_dir, f), os.path.join(output_dir, "restyled", f))

    # Build table rows
    rows_1x = []
    rows_4x = []
    for f in common:
        rows_1x.append(
            f'<tr>'
            f'<td class="filename">{f}</td>'
            f'<td class="sprite"><img src="orig/{f}"></td>'
            f'<td class="sprite"><img src="restyled/{f}"></td>'
            f'</tr>'
        )
        rows_4x.append(
            f'<tr>'
            f'<td class="filename">{f}</td>'
            f'<td class="sprite"><img src="orig/{f}"></td>'
            f'<td class="sprite"><img src="restyled/{f}"></td>'
            f'</tr>'
        )

    from datetime import datetime
    html = COMPARISON_HTML.format(
        sprite_count=len(common),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        rows_1x="\n".join(rows_1x),
        rows_4x="\n".join(rows_4x),
    )

    html_path = os.path.join(output_dir, "index.html")
    with open(html_path, "w") as f:
        f.write(html)

    print(f"Comparison page: {html_path} ({len(common)} sprites)")
    return html_path


def screenshot_comparison(html_dir, output_path, port=0):
    """Use Playwright to screenshot the comparison page."""
    from screenshot_game import start_server, stop_server

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright")
        return False

    server, actual_port = start_server(html_dir, port=port)
    url = f"http://127.0.0.1:{actual_port}/index.html"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 2048})
            page.goto(url, wait_until="networkidle")

            # Wait for the status indicator
            page.wait_for_selector("#status", timeout=5000)

            # Take full-page screenshot
            page.screenshot(path=output_path, full_page=True)
            browser.close()

        print(f"Screenshot saved: {output_path}")
        return True
    except Exception as e:
        print(f"Playwright error: {e}")
        return False
    finally:
        stop_server(server)


def judge_comparison(screenshot_path):
    """Use Gemini to judge the comparison screenshot."""
    from judge_screenshot import invoke_gemini, parse_rating

    prompt = (
        "This screenshot shows a sprite reskin verification page. "
        "It displays original game sprites on the left and AI-restyled versions on the right, "
        "at 1x and 4x zoom.\n\n"
        "Evaluate:\n"
        "1. Are the restyled sprites visibly different from the originals?\n"
        "2. Do the restyled sprites preserve the original silhouette/shape?\n"
        "3. Are the restyled sprites rendering correctly (no black boxes, no corruption, proper transparency)?\n"
        "4. Does the restyled style look cohesive and intentional?\n\n"
        "Rate the overall reskin quality 1-10 and explain."
    )

    image_dir = os.path.dirname(os.path.abspath(screenshot_path))
    output = invoke_gemini(prompt, [image_dir])

    if output:
        print(f"\n--- Gemini Judgment ---\n{output}\n")
        rating = parse_rating(output)
        if rating is not None:
            print(f"Rating: {rating}/10")
            return rating >= 5
        else:
            print("Could not parse rating from Gemini output")
            return None
    else:
        print("Gemini invocation failed")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Verify restyled sprites render correctly using Playwright"
    )
    parser.add_argument("--originals", required=True,
                        help="Directory with original sprite PNGs")
    parser.add_argument("--restyled", required=True,
                        help="Directory with restyled sprite PNGs")
    parser.add_argument("--output", default=None,
                        help="Screenshot output path (default: /tmp/reskin-verify.png)")
    parser.add_argument("--judge", action="store_true",
                        help="Also judge the screenshot with Gemini CLI")
    parser.add_argument("--port", type=int, default=0,
                        help="Server port (default: random free port)")
    parser.add_argument("--keep-html", action="store_true",
                        help="Keep the generated HTML comparison dir")
    args = parser.parse_args()

    output_path = args.output or "/tmp/reskin-verify.png"

    # Build comparison page in temp dir
    html_dir = tempfile.mkdtemp(prefix="reskin-verify-")
    try:
        html_path = build_comparison_page(args.originals, args.restyled, html_dir)
        if not html_path:
            sys.exit(1)

        # Screenshot with Playwright
        ok = screenshot_comparison(html_dir, output_path, port=args.port)
        if not ok:
            sys.exit(1)

        # Optional Gemini judgment
        if args.judge:
            passed = judge_comparison(output_path)
            if passed is False:
                print("FAIL: Gemini rated the reskin below threshold")
                sys.exit(1)
            elif passed is True:
                print("PASS: Gemini approved the reskin")
    finally:
        if args.keep_html:
            print(f"HTML comparison kept at: {html_dir}")
        else:
            shutil.rmtree(html_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
