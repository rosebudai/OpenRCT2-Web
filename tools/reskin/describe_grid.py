#!/usr/bin/env python3
"""Generate per-cell descriptions for batch grids using Gemini CLI.

Looks at each grid image and asks Gemini to describe what's in each cell.
Writes description JSON files that generate_restyled.py uses for better prompts.

Usage:
    python3 describe_grid.py --manifest batches/manifest.json
    python3 describe_grid.py --manifest batches/manifest.json --skip-existing
"""

import os
import sys
import json
import argparse
import subprocess
import re


def invoke_gemini(prompt, image_dirs):
    """Shell out to Gemini CLI for image analysis."""
    cmd = [
        "gemini", "-p", prompt,
        "-m", "gemini-3.1-pro-preview",
        "--yolo",
        "--output-format", "text",
    ]
    for d in image_dirs:
        cmd.extend(["--include-directories", d])

    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=120,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        print("ERROR: gemini CLI not found. Install: npm install -g @anthropic-ai/gemini-cli")
        return None
    except subprocess.TimeoutExpired:
        print("WARNING: Gemini timed out")
        return None


def parse_descriptions(gemini_output, expected_labels):
    """Parse Gemini's response into a {label: description} dict.

    Looks for patterns like:
        A1: description text
        A2: description text
    """
    descriptions = {}
    if not gemini_output:
        return descriptions

    for label in expected_labels:
        # Match "A1:" or "**A1:**" or "- A1:" etc.
        pattern = rf'(?:^|\n)\s*(?:[-*]*\s*)?(?:\*\*)?{re.escape(label)}(?:\*\*)?[:\s]+(.+?)(?:\n|$)'
        m = re.search(pattern, gemini_output, re.IGNORECASE)
        if m:
            desc = m.group(1).strip().rstrip('.')
            # Clean up markdown formatting
            desc = re.sub(r'\*\*', '', desc)
            desc = re.sub(r'^\s*[-*]\s*', '', desc)
            if desc:
                descriptions[label] = desc

    return descriptions


def describe_batch(batch_meta, grid_dir, hint=""):
    """Use Gemini to describe what's in each cell of a grid image."""
    grid_file = batch_meta["grid_file"]
    if not os.path.isabs(grid_file):
        grid_file = os.path.abspath(grid_file)

    labels = [s["cell_label"] for s in batch_meta["sprites"]]
    cols = batch_meta["cols"]
    rows = batch_meta["rows"]

    label_list = ", ".join(labels)
    hint_text = f" These are {hint}." if hint else ""

    prompt = (
        f"This image is a {cols}x{rows} grid of game sprites on a gray background, "
        f"separated by black grid lines. The cells are labeled {label_list} "
        f"(row letter + column number, left to right, top to bottom).{hint_text}\n\n"
        f"For EACH cell, write exactly one short description (5-15 words) of what "
        f"the sprite depicts. Focus on the object's shape, material, and purpose.\n\n"
        f"Format your response EXACTLY like this, one line per cell:\n"
    )
    for label in labels:
        prompt += f"{label}: <description>\n"

    image_dir = os.path.dirname(grid_file)
    output = invoke_gemini(prompt, [image_dir])

    if output is None:
        return {label: hint or "game sprite" for label in labels}

    descriptions = parse_descriptions(output, labels)

    # Fill in any missing labels with the hint
    for label in labels:
        if label not in descriptions:
            descriptions[label] = hint or "game sprite"

    return descriptions


def describe_all(manifest_path, descriptions_dir=None, skip_existing=False):
    """Generate descriptions for all batches in a manifest."""
    with open(manifest_path) as f:
        manifest = json.load(f)

    batch_dir = os.path.dirname(manifest_path)
    if descriptions_dir is None:
        descriptions_dir = os.path.join(os.path.dirname(batch_dir), "descriptions")

    os.makedirs(descriptions_dir, exist_ok=True)
    hint = manifest.get("description_hint", "")

    for i, batch_meta in enumerate(manifest["batches"]):
        batch_id = batch_meta["batch_id"]
        desc_path = os.path.join(descriptions_dir, f"{batch_id}.json")

        if skip_existing and os.path.exists(desc_path):
            print(f"[{i + 1}/{len(manifest['batches'])}] {batch_id}: skipping (exists)")
            continue

        n = len(batch_meta["sprites"])
        print(f"[{i + 1}/{len(manifest['batches'])}] {batch_id}: describing {n} sprites...")

        descriptions = describe_batch(batch_meta, batch_dir, hint)

        with open(desc_path, "w") as f:
            json.dump(descriptions, f, indent=2)

        for label, desc in sorted(descriptions.items()):
            print(f"  {label}: {desc}")

    print(f"\nDescriptions saved to {descriptions_dir}/")
    return descriptions_dir


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-cell sprite descriptions using Gemini CLI"
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--descriptions-dir", default=None,
                        help="Output directory for description JSON files")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip batches with existing descriptions")
    args = parser.parse_args()

    describe_all(
        manifest_path=args.manifest,
        descriptions_dir=args.descriptions_dir,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
