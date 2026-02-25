#!/usr/bin/env python3
"""Extract restyled sprites from AI-generated grids.

Reads the manifest and restyled grid images, extracts individual sprites
using exact inverse transforms, applies original alpha masks, optionally
blends tile edges, and saves restyled PNGs.

Usage:
    python3 parse_restyled.py --manifest batches/manifest.json --sprites-dir sprites/
    python3 parse_restyled.py --manifest batches/manifest.json --sprites-dir sprites/ --dry-run
"""

import os
import json
import argparse
from PIL import Image
import numpy as np


def extract_sprites_from_grid(restyled_path, batch_meta, canvas_size):
    """Extract individual sprites from a restyled grid image.

    Returns list of (original_filename, cropped_image, sprite_meta).
    """
    img = Image.open(restyled_path).convert("RGBA")
    img_w, img_h = img.size

    scale = batch_meta["scale"]
    offset_x = batch_meta["offset_x"]
    offset_y = batch_meta["offset_y"]
    native_w = batch_meta["native_w"]
    native_h = batch_meta["native_h"]
    cell_w = batch_meta["cell_w"]
    cell_h = batch_meta["cell_h"]
    glw = 6  # grid line width

    # Scale offsets if AI returned a different resolution
    img_scale = img_w / canvas_size
    actual_offset_x = int(offset_x * img_scale)
    actual_offset_y = int(offset_y * img_scale)
    actual_w = int(native_w * scale * img_scale)
    actual_h = int(native_h * scale * img_scale)

    # Crop the grid region from the canvas
    grid_crop = img.crop((
        actual_offset_x, actual_offset_y,
        actual_offset_x + actual_w, actual_offset_y + actual_h
    ))

    # Scale back to native resolution
    grid_native = grid_crop.resize((native_w, native_h), Image.LANCZOS)

    extracted = []
    for sprite_info in batch_meta["sprites"]:
        row = sprite_info["cell_row"]
        col = sprite_info["cell_col"]
        orig_w = sprite_info["original_w"]
        orig_h = sprite_info["original_h"]

        # Cell top-left in native coordinates
        cx = glw + col * (cell_w + glw)
        cy = glw + row * (cell_h + glw)

        # Sprite was centered in cell
        paste_x = cx + (cell_w - orig_w) // 2
        paste_y = cy + (cell_h - orig_h) // 2

        # Extract at exact original dimensions
        sprite_crop = grid_native.crop((
            paste_x, paste_y,
            paste_x + orig_w, paste_y + orig_h
        ))

        extracted.append((sprite_info["original_file"], sprite_crop, sprite_info))

    return extracted


def restore_alpha(restyled_sprite, original_path):
    """Apply original sprite's alpha channel to the restyled sprite."""
    original = Image.open(original_path).convert("RGBA")
    restyled = restyled_sprite.convert("RGBA")

    if restyled.size != original.size:
        restyled = restyled.resize(original.size, Image.LANCZOS)

    r, g, b, _ = restyled.split()
    _, _, _, original_alpha = original.split()

    return Image.merge("RGBA", (r, g, b, original_alpha))


def blend_tile_edges(restyled, original, edge_pixels=6):
    """Blend outer edge pixels back to original for seamless tiling."""
    res = np.array(restyled).astype(float)
    orig = np.array(original).astype(float)
    h, w = res.shape[:2]
    edge_pixels = min(edge_pixels, h // 2, w // 2)
    if edge_pixels <= 0:
        return restyled
    mask = np.ones((h, w), dtype=float)
    for i in range(edge_pixels):
        a = i / edge_pixels
        mask[i, :] = np.minimum(mask[i, :], a)
        mask[h - 1 - i, :] = np.minimum(mask[h - 1 - i, :], a)
        mask[:, i] = np.minimum(mask[:, i], a)
        mask[:, w - 1 - i] = np.minimum(mask[:, w - 1 - i], a)
    m = mask[:, :, np.newaxis]
    blended = res * m + orig * (1.0 - m)
    return Image.fromarray(blended.astype(np.uint8))


def validate_sprite(restyled, original_path):
    """Check that the restyled sprite is reasonable.

    Returns (ok, message).
    """
    original = Image.open(original_path).convert("RGBA")

    if restyled.size != original.size:
        return False, f"Size mismatch: {restyled.size} vs {original.size}"

    orig_arr = np.array(original)
    rest_arr = np.array(restyled)
    orig_alpha = orig_arr[:, :, 3]
    visible = orig_alpha > 0

    if not visible.any():
        return True, "OK (fully transparent)"

    orig_rgb = orig_arr[:, :, :3].astype(float)
    rest_rgb = rest_arr[:, :, :3].astype(float)
    diff = np.abs(rest_rgb - orig_rgb)
    mean_diff = diff[visible].mean()

    if mean_diff < 3:
        return False, f"Too similar (diff={mean_diff:.1f})"

    return True, f"OK (diff={mean_diff:.1f})"


def parse_restyled(manifest_path, sprites_dir, restyled_dir=None,
                   output_dir=None, tiling=None, dry_run=False):
    """Main entry point: extract restyled sprites from AI grids.

    Args:
        manifest_path: Path to batches/manifest.json.
        sprites_dir: Directory with original sprite PNGs (for alpha masks).
        restyled_dir: Directory with restyled grid images
                      (default: sibling of batch dir named 'restyled').
        output_dir: Where to write restyled individual PNGs
                    (default: same as sprites_dir, overwriting originals).
        tiling: Whether to blend tile edges. If None, reads from manifest.
        dry_run: Validate only, don't write files.

    Returns dict with keys: total, skipped, missing_batches.
    """
    with open(manifest_path) as f:
        manifest = json.load(f)

    canvas_size = manifest["canvas_size"]
    use_tiling = tiling if tiling is not None else manifest.get("tiling", False)

    batch_dir = os.path.dirname(manifest_path)
    if restyled_dir is None:
        restyled_dir = os.path.join(os.path.dirname(batch_dir), "restyled")
    if output_dir is None:
        output_dir = sprites_dir

    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)

    all_ok = []
    skipped = 0
    missing_batches = []

    for batch_meta in manifest["batches"]:
        batch_id = batch_meta["batch_id"]
        restyled_path = os.path.join(restyled_dir, f"{batch_id}_restyled.png")

        if not os.path.exists(restyled_path):
            print(f"  {batch_id}: MISSING, skipping")
            missing_batches.append(batch_id)
            continue

        try:
            extracted = extract_sprites_from_grid(
                restyled_path, batch_meta, canvas_size
            )
        except Exception as e:
            print(f"  {batch_id}: ERROR ({e}), skipping")
            missing_batches.append(batch_id)
            continue

        batch_ok = 0
        batch_warn = 0
        for filename, sprite_img, meta in extracted:
            orig_path = os.path.join(sprites_dir, filename)

            # Restore original alpha mask
            sprite_img = restore_alpha(sprite_img, orig_path)

            # Blend tile edges
            if use_tiling:
                original = Image.open(orig_path).convert("RGBA")
                sprite_img = blend_tile_edges(sprite_img, original)

            # Validate
            ok, msg = validate_sprite(sprite_img, orig_path)
            if not ok:
                print(f"    WARNING: {filename}: {msg}")
                batch_warn += 1
                skipped += 1
                continue

            if not dry_run:
                sprite_img.save(os.path.join(output_dir, filename))

            all_ok.append(filename)
            batch_ok += 1

        print(f"  {batch_id}: {batch_ok} OK, {batch_warn} warnings")

    print(f"\nTotal: {len(all_ok)} sprites ready, {skipped} skipped, "
          f"{len(missing_batches)} batches missing")

    if dry_run:
        print("Dry run - no files written.")

    return {
        "total": len(all_ok),
        "skipped": skipped,
        "missing_batches": missing_batches,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract restyled sprites from AI grids"
    )
    parser.add_argument("--manifest", required=True,
                        help="Path to manifest.json")
    parser.add_argument("--sprites-dir", required=True,
                        help="Directory with original sprite PNGs")
    parser.add_argument("--restyled-dir", default=None,
                        help="Directory with restyled grid images")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for restyled PNGs "
                             "(default: overwrite sprites-dir)")
    parser.add_argument("--tiling", action="store_true",
                        help="Blend tile edges for seamless tiling")
    parser.add_argument("--no-tiling", action="store_true",
                        help="Disable tile edge blending even if manifest says tiling")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate only, don't write files")
    args = parser.parse_args()

    tiling = None
    if args.tiling:
        tiling = True
    elif args.no_tiling:
        tiling = False

    parse_restyled(
        manifest_path=args.manifest,
        sprites_dir=args.sprites_dir,
        restyled_dir=args.restyled_dir,
        output_dir=args.output_dir,
        tiling=tiling,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
