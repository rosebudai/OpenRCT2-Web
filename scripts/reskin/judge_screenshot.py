#!/usr/bin/env python3
"""Invoke Gemini CLI to visually judge a game screenshot.

Evaluates a screenshot (optionally against a reference image) using
Gemini's vision capabilities and returns a quality rating.

Usage::

    python3 judge_screenshot.py screenshot.png
    python3 judge_screenshot.py reskinned.png --reference original.png
    python3 judge_screenshot.py shot.png --criteria 'Check if trees look natural'
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

PROMPT_SINGLE = (
    "Evaluate this game screenshot. Is it rendering correctly? "
    "Are there visual artifacts, black screens, or missing textures? "
    "Rate quality 1-10 and explain."
)

PROMPT_COMPARISON = (
    "Compare these two screenshots. The first is the original, the second "
    "is reskinned. Evaluate: (1) Did the reskin change the visual style? "
    "(2) Are game elements still recognizable? (3) Is the overall quality "
    "acceptable? Rate 1-10 and explain."
)


def build_prompt(
    screenshot: str,
    reference: Optional[str] = None,
    criteria: Optional[str] = None,
) -> str:
    """Build the evaluation prompt for Gemini.

    Parameters
    ----------
    screenshot:
        Path to the screenshot image (used for context, not embedded).
    reference:
        Optional path to a reference image for comparison.
    criteria:
        Optional additional evaluation criteria to append.

    Returns
    -------
    The assembled prompt string.
    """
    if reference:
        prompt = PROMPT_COMPARISON
    else:
        prompt = PROMPT_SINGLE

    if criteria:
        prompt = prompt + " " + criteria

    return prompt


# ---------------------------------------------------------------------------
# Rating parser
# ---------------------------------------------------------------------------


def parse_rating(text: str) -> Optional[int]:
    """Extract an X/10 rating from Gemini's response.

    Looks for patterns like ``7/10``, ``8 / 10``, ``Rating: 9/10``.

    Returns
    -------
    The integer rating, or ``None`` if no rating was found.
    """
    match = re.search(r"\b(\d{1,2})\s*/\s*10\b", text)
    if match:
        value = int(match.group(1))
        if 1 <= value <= 10:
            return value
    return None


# ---------------------------------------------------------------------------
# Gemini invocation
# ---------------------------------------------------------------------------


def invoke_gemini(
    prompt: str,
    image_dirs: list[str],
) -> str:
    """Call the Gemini CLI and return its text output.

    Parameters
    ----------
    prompt:
        The evaluation prompt.
    image_dirs:
        Directories to pass via ``--include-directories`` so Gemini can
        see the images.

    Returns
    -------
    Gemini's response text, or an error string on failure.
    """
    cmd = [
        "gemini",
        "-p",
        prompt,
        "-m",
        "gemini-3.1-pro-preview",
        "--yolo",
        "--output-format",
        "text",
    ]
    for d in image_dirs:
        cmd.extend(["--include-directories", d])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        return "Error: gemini CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return "Error: gemini CLI timed out after 120s"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def judge(
    screenshot: str,
    reference: Optional[str] = None,
    criteria: Optional[str] = None,
) -> tuple[str, Optional[int]]:
    """Judge a screenshot and return (response_text, rating).

    Parameters
    ----------
    screenshot:
        Path to the screenshot PNG.
    reference:
        Optional path to a reference PNG for comparison.
    criteria:
        Optional additional evaluation criteria.

    Returns
    -------
    (response, rating) where rating is an int 1-10 or None.
    """
    prompt = build_prompt(screenshot, reference=reference, criteria=criteria)

    # Collect unique directories containing the images so Gemini can access them.
    image_dirs: list[str] = []
    seen: set[str] = set()
    for path in [screenshot, reference]:
        if path is not None:
            d = str(Path(path).resolve().parent)
            if d not in seen:
                image_dirs.append(d)
                seen.add(d)

    response = invoke_gemini(prompt, image_dirs)
    rating = parse_rating(response)
    return response, rating


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use Gemini to visually judge a game screenshot.",
    )
    parser.add_argument(
        "screenshot",
        help="Path to the screenshot PNG to evaluate.",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Optional reference screenshot for comparison.",
    )
    parser.add_argument(
        "--criteria",
        default=None,
        help="Additional evaluation criteria to append to the prompt.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # Validate paths.
    if not os.path.isfile(args.screenshot):
        print(f"Error: screenshot not found: {args.screenshot}", file=sys.stderr)
        sys.exit(1)
    if args.reference and not os.path.isfile(args.reference):
        print(f"Error: reference not found: {args.reference}", file=sys.stderr)
        sys.exit(1)

    response, rating = judge(
        args.screenshot,
        reference=args.reference,
        criteria=args.criteria,
    )

    print(response)

    if rating is not None:
        print(f"\nRating: {rating}/10")
        sys.exit(0 if rating >= 5 else 1)
    else:
        print("\nWarning: could not parse a rating from the response", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
