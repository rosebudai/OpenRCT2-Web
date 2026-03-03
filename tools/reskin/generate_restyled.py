#!/usr/bin/env python3
"""Send batch grids to FAL.ai Gemini 3 Pro for AI restyling.

Reads a manifest JSON, builds prompts with optional per-cell descriptions,
calls the FAL.ai image edit API, and saves restyled grid images.

Requires: pip install fal-client
Requires: FAL_KEY environment variable

Usage:
    python3 generate_restyled.py --manifest batches/manifest.json
    python3 generate_restyled.py --manifest batches/manifest.json --skip-existing
"""

import os
import sys
import json
import time
import argparse
import urllib.request

try:
    import fal_client
except ImportError:
    fal_client = None

DEFAULT_STYLE = (
    "Cute cartoony medieval fantasy style. Bold outlines, bright saturated colors, "
    "warm lighting. Hand-painted game art, clean and vibrant."
)


def load_descriptions(descriptions_dir, batch_id):
    """Load per-cell descriptions from descriptions/<batch_id>.json."""
    if not descriptions_dir:
        return {}
    path = os.path.join(descriptions_dir, f"{batch_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def build_prompt(batch_meta, style_desc, descriptions_dir=None):
    """Build a prompt for a batch using per-cell descriptions."""
    cols = batch_meta["cols"]
    rows = batch_meta["rows"]
    batch_id = batch_meta["batch_id"]

    descriptions = load_descriptions(descriptions_dir, batch_id)

    cell_descs = []
    for s in batch_meta["sprites"]:
        label = s["cell_label"]
        row_label = chr(65 + s["cell_row"])
        col_label = s["cell_col"] + 1
        desc = descriptions.get(label, "game sprite")
        cell_descs.append(f"  Row {row_label} Col {col_label}: {desc}")

    cell_text = "\n".join(cell_descs)

    prompt = (
        f"This is a {cols}x{rows} grid of game sprites on gray background, "
        f"separated by black grid lines.\n\n"
        f"Each cell contains:\n{cell_text}\n\n"
        f"Restyle every sprite to: {style_desc}\n\n"
        f"You MUST keep the exact same silhouette, shape, size, and proportions "
        f"of every object. Only change colors and textures. No text, no labels, "
        f"no new objects. Keep grid lines and gray backgrounds."
    )
    return prompt


def generate_with_fal(prompt, condition_path, output_path, retries=3):
    """Call FAL.ai Gemini 3 Pro image edit API.

    Returns True on success, False on failure.
    """
    if fal_client is None:
        print("ERROR: fal-client not installed. Run: pip install fal-client")
        return False

    condition_url = fal_client.upload_file(str(condition_path))

    for attempt in range(retries):
        try:
            result = fal_client.subscribe(
                "fal-ai/gemini-3-pro-image-preview/edit",
                arguments={
                    "prompt": prompt,
                    "image_urls": [condition_url],
                    "num_images": 1,
                    "aspect_ratio": "1:1",
                    "resolution": "4K",
                    "output_format": "png",
                },
                with_logs=True,
            )

            if result and result.get("images"):
                image_url = result["images"][0]["url"]
                urllib.request.urlretrieve(image_url, output_path)
                from PIL import Image
                img = Image.open(output_path)
                if img.size[0] < 1024 or img.size[1] < 1024:
                    print(f"    WARNING: Output too small ({img.size}), retrying...")
                    continue
                return True
            else:
                print(f"    No images in result, attempt {attempt + 1}/{retries}")

        except Exception as e:
            print(f"    FAL Error (attempt {attempt + 1}): {e}")
            time.sleep(5 * (attempt + 1))

    return False


def generate_all(manifest_path, restyled_dir, style=None, descriptions_dir=None,
                 skip_existing=False, batch_id_filter=None):
    """Generate restyled grids for all batches in a manifest.

    Returns list of result dicts with keys: id, status, output.
    """
    with open(manifest_path) as f:
        manifest = json.load(f)

    os.makedirs(restyled_dir, exist_ok=True)
    style_desc = style or manifest.get("style_prompt", DEFAULT_STYLE)

    batches = manifest["batches"]
    if batch_id_filter:
        batches = [b for b in batches if b["batch_id"] == batch_id_filter]
        if not batches:
            print(f"ERROR: Batch '{batch_id_filter}' not found")
            return []

    results = []
    for i, batch_meta in enumerate(batches):
        bid = batch_meta["batch_id"]
        grid_path = batch_meta["grid_file"]
        output_path = os.path.join(restyled_dir, f"{bid}_restyled.png")

        if skip_existing and os.path.exists(output_path):
            print(f"[{i + 1}/{len(batches)}] {bid}: skipping (exists)")
            results.append({"id": bid, "status": "skipped"})
            continue

        print(f"[{i + 1}/{len(batches)}] {bid}: {len(batch_meta['sprites'])} sprites...")

        prompt = build_prompt(batch_meta, style_desc, descriptions_dir)

        # Save prompt for debugging
        prompt_path = os.path.join(restyled_dir, f"{bid}_prompt.txt")
        with open(prompt_path, "w") as f:
            f.write(prompt)

        success = generate_with_fal(prompt, grid_path, output_path)

        status = "success" if success else "failed"
        print(f"    -> {status}")
        results.append({
            "id": bid,
            "status": status,
            "output": output_path if success else None,
        })

    # Summary
    success_count = sum(1 for r in results if r["status"] == "success")
    skip_count = sum(1 for r in results if r["status"] == "skipped")
    fail_count = sum(1 for r in results if r["status"] == "failed")
    print(f"\nDone! {success_count} generated, {skip_count} skipped, {fail_count} failed")

    # Save results log
    results_path = os.path.join(restyled_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    return results


def main():
    if fal_client is None:
        print("ERROR: fal-client not installed. Run: pip install fal-client")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Generate restyled sprites via FAL.ai"
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--restyled-dir", default=None,
                        help="Output dir for restyled grids "
                             "(default: sibling of manifest dir named 'restyled')")
    parser.add_argument("--descriptions-dir", default=None,
                        help="Dir with per-batch description JSON files")
    parser.add_argument("--style", default=None, help="Override style prompt")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip batches with existing output")
    parser.add_argument("--batch", default=None,
                        help="Process only this batch ID (e.g. batch_001)")
    args = parser.parse_args()

    if not os.environ.get("FAL_KEY"):
        print("ERROR: FAL_KEY environment variable not set")
        sys.exit(1)

    restyled_dir = args.restyled_dir or os.path.join(
        os.path.dirname(os.path.dirname(args.manifest)), "restyled"
    )

    generate_all(
        manifest_path=args.manifest,
        restyled_dir=restyled_dir,
        style=args.style,
        descriptions_dir=args.descriptions_dir,
        skip_existing=args.skip_existing,
        batch_id_filter=args.batch,
    )


if __name__ == "__main__":
    main()
