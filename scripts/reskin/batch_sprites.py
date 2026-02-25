#!/usr/bin/env python3
"""Group sprite PNGs into grid batches for AI restyling.

Reads PNGs from a directory, groups by similar size, renders grid images
(4x4 cells on 2048x2048 canvas), and writes a manifest JSON.

Usage:
    python3 batch_sprites.py --sprites-dir ./sprites --batch-dir ./batches
"""

import os
import json
import math
import argparse
from collections import defaultdict
from PIL import Image, ImageDraw

CANVAS_SIZE = 2048
CELL_PADDING = 16
GRID_LINE_WIDTH = 6
BG_COLOR = (200, 200, 200, 255)
LINE_COLOR = (0, 0, 0, 255)
BUCKET_STEP = 128
MAX_PER_BATCH = 16


def load_sprites(sprites_dir):
    """Load sprite metadata from a directory of PNGs."""
    sprites = []
    for f in sorted(os.listdir(sprites_dir)):
        if not f.lower().endswith(".png"):
            continue
        path = os.path.join(sprites_dir, f)
        img = Image.open(path)
        w, h = img.size
        sprites.append({"file": f, "w": w, "h": h})
    return sprites


def create_batches(sprites):
    """Split sprites into batches grouped by similar size."""
    buckets = defaultdict(list)
    for s in sprites:
        bw = ((s["w"] + BUCKET_STEP - 1) // BUCKET_STEP) * BUCKET_STEP
        bh = ((s["h"] + BUCKET_STEP - 1) // BUCKET_STEP) * BUCKET_STEP
        buckets[(bw, bh)].append(s)

    for key in buckets:
        buckets[key].sort(key=lambda s: s["w"] * s["h"], reverse=True)

    batches = []
    for (bw, bh), bucket_sprites in sorted(buckets.items()):
        for i in range(0, len(bucket_sprites), MAX_PER_BATCH):
            batches.append({
                "bucket": (bw, bh),
                "sprites": bucket_sprites[i:i + MAX_PER_BATCH],
            })
    return batches


def render_grid(batch, batch_id):
    """Render a batch as a grid image on a 2048x2048 canvas.

    Returns (canvas_image, draw, batch_metadata, cell_w, cell_h).
    """
    bw, bh = batch["bucket"]
    sprites_meta = batch["sprites"]
    n = len(sprites_meta)
    cols = min(4, n)
    rows = math.ceil(n / 4)

    cell_w = bw + CELL_PADDING * 2
    cell_h = bh + CELL_PADDING * 2

    native_w = cols * cell_w + (cols + 1) * GRID_LINE_WIDTH
    native_h = rows * cell_h + (rows + 1) * GRID_LINE_WIDTH

    scale = min(CANVAS_SIZE / native_w, CANVAS_SIZE / native_h, 3.0)
    actual_w = int(native_w * scale)
    actual_h = int(native_h * scale)
    offset_x = (CANVAS_SIZE - actual_w) // 2
    offset_y = (CANVAS_SIZE - actual_h) // 2

    canvas = Image.new("RGBA", (native_w, native_h), LINE_COLOR)
    draw = ImageDraw.Draw(canvas)

    batch_meta = {
        "batch_id": batch_id,
        "bucket": [bw, bh],
        "cols": cols,
        "rows": rows,
        "scale": scale,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "native_w": native_w,
        "native_h": native_h,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "sprites": [],
    }

    return canvas, draw, batch_meta, cell_w, cell_h


def render_grid_with_sprites(batch, batch_id, sprites_dir):
    """Render a complete grid with sprites pasted in.

    Returns (final_canvas, batch_metadata).
    """
    canvas, draw, batch_meta, cell_w, cell_h = render_grid(batch, batch_id)
    sprites_meta = batch["sprites"]

    for idx, sprite in enumerate(sprites_meta):
        row = idx // 4
        col = idx % 4

        cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
        cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)

        draw.rectangle([cx, cy, cx + cell_w - 1, cy + cell_h - 1], fill=BG_COLOR)

        img = Image.open(os.path.join(sprites_dir, sprite["file"])).convert("RGBA")
        paste_x = cx + (cell_w - sprite["w"]) // 2
        paste_y = cy + (cell_h - sprite["h"]) // 2
        canvas.paste(img, (paste_x, paste_y), img)

        label = f"{chr(65 + row)}{col + 1}"
        batch_meta["sprites"].append({
            "cell_row": row,
            "cell_col": col,
            "cell_label": label,
            "original_file": sprite["file"],
            "original_w": sprite["w"],
            "original_h": sprite["h"],
        })

    native_w = batch_meta["native_w"]
    native_h = batch_meta["native_h"]
    scale = batch_meta["scale"]
    offset_x = batch_meta["offset_x"]
    offset_y = batch_meta["offset_y"]

    actual_w = int(native_w * scale)
    actual_h = int(native_h * scale)
    scaled = canvas.resize((actual_w, actual_h), Image.LANCZOS)
    final = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 255))
    final.paste(scaled, (offset_x, offset_y))

    return final, batch_meta


def batch_sprites(sprites_dir, batch_dir, style_prompt="", description_hint="",
                  tiling=False):
    """Main entry point: batch a directory of PNGs into grids.

    Returns the manifest dict.
    """
    os.makedirs(batch_dir, exist_ok=True)

    sprites = load_sprites(sprites_dir)
    if not sprites:
        print(f"No PNG files found in {sprites_dir}")
        return None

    print(f"Loaded {len(sprites)} sprites from {sprites_dir}")

    batches = create_batches(sprites)
    print(f"Created {len(batches)} batches")

    manifest = {
        "version": 1,
        "sprites_dir": os.path.abspath(sprites_dir),
        "canvas_size": CANVAS_SIZE,
        "grid_line_width": GRID_LINE_WIDTH,
        "cell_padding": CELL_PADDING,
        "style_prompt": style_prompt,
        "description_hint": description_hint,
        "tiling": tiling,
        "batches": [],
    }

    for i, batch in enumerate(batches):
        batch_id = f"batch_{i + 1:03d}"
        grid_path = os.path.join(batch_dir, f"{batch_id}.png")

        grid_img, batch_meta = render_grid_with_sprites(batch, batch_id, sprites_dir)
        batch_meta["grid_file"] = grid_path
        grid_img.save(grid_path)
        manifest["batches"].append(batch_meta)

        n = len(batch["sprites"])
        print(f"  {batch_id}: {n:2d} sprites, bucket {batch['bucket']}")

    manifest_path = os.path.join(batch_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    total = sum(len(b["sprites"]) for b in manifest["batches"])
    print(f"\nDone! {total} sprites in {len(manifest['batches'])} batches")
    print(f"Manifest: {manifest_path}")

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Batch sprite PNGs into grids for AI restyling"
    )
    parser.add_argument("--sprites-dir", required=True,
                        help="Directory containing sprite PNGs")
    parser.add_argument("--batch-dir", default=None,
                        help="Output directory for grid images + manifest "
                             "(default: <sprites-dir>/../batches)")
    parser.add_argument("--style", default="",
                        help="Style prompt to store in manifest")
    parser.add_argument("--description-hint", default="game sprite",
                        help="Hint for per-cell descriptions")
    parser.add_argument("--tiling", action="store_true",
                        help="Flag sprites as tiling (blends edges during parse)")
    args = parser.parse_args()

    batch_dir = args.batch_dir or os.path.join(
        os.path.dirname(args.sprites_dir.rstrip("/")), "batches"
    )

    batch_sprites(
        sprites_dir=args.sprites_dir,
        batch_dir=batch_dir,
        style_prompt=args.style,
        description_hint=args.description_hint,
        tiling=args.tiling,
    )


if __name__ == "__main__":
    main()
