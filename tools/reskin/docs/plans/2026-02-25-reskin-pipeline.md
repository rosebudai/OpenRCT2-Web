# OpenRCT2 AI Reskin Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Add AI-powered sprite reskinning scripts that batch OpenRCT2 sprite PNGs into grids, send them to FAL.ai for restyling, and extract the results back — integrating with the existing workspace/overlay/upload pipeline.

**Architecture:** Five Python scripts under `tools/reskin/`. The core pipeline is game-agnostic (batch PNGs into grids, call FAL.ai, extract results). An orchestrator script (`reskin.py`) provides both workspace mode (integrates with `init-reskin-object-workspace.sh` outputs) and standalone mode (any directory of PNGs). Category presets in `categories.py` provide reusable style configs.

**Tech Stack:** Python 3.8+, Pillow, numpy, fal-client. FAL.ai Gemini 3 Pro image-edit API.

---

## Reference: ottd-reskin-pipeline

The source code being adapted lives at `/workspace/ottd-reskin-pipeline/`. Key files:

| ottd file | Becomes | What changes |
|-----------|---------|--------------|
| `batch_env.py` | `tools/reskin/batch_sprites.py` | Remove NFO parsing. Input is just a PNG directory. No sprite ID ranges — discover files from disk. |
| `generate_restyled.py` | `tools/reskin/generate_restyled.py` | Nearly identical. Update default paths. Keep FAL.ai logic as-is. |
| `parse_and_replace.py` | `tools/reskin/parse_restyled.py` | Remove GRF rebuild / sheet patching. Output is restyled PNGs to a target dir. Keep alpha restore + edge blending. |
| `restyle_env.py` | `tools/reskin/reskin.py` | Replace subprocess calls with direct function imports. Add `--workspace` mode. |
| `env_categories.py` | `tools/reskin/categories.py` | Replace zBase sprite ID ranges with OpenRCT2 style presets (scenery, terrain, rides). No ID ranges needed. |

## Reference: existing OpenRCT2-Web reskin scripts

- `tools/reskin/init-workspace.sh` — creates `<workspace>/sprites/` with exported PNGs + `sprites.json`
- `<workspace>/rebuild-object.sh` — rebuilds `images.dat` + `reskinned.parkobj` from sprites
- `tools/reskin/create-overlay.sh` — maps workspaces into overlay dirs
- `tools/reskin/build-upload.sh` — merges overlays into web upload zip

The new Python pipeline slots in between steps 1 and the rebuild: it reads from `sprites/`, writes restyled PNGs back there (or to a separate output dir).

---

### Task 1: `categories.py` — Style preset definitions

**Files:**
- Create: `tools/reskin/categories.py`

**Step 1: Create the categories module**

```python
"""OpenRCT2 sprite category presets for AI restyling.

Categories define style prompts, tiling flags, and description hints.
Unlike the ottd pipeline, these do NOT define sprite ID ranges —
OpenRCT2 sprites are discovered from the filesystem.
"""

CATEGORIES = {
    "scenery_small": {
        "tiling": False,
        "style_prompt": (
            "Cartoony hand-painted fantasy scenery. Bold outlines, bright saturated "
            "colors, warm lighting. Rich detail, painterly textures. "
            "Think Warcraft III or Clash of Clans decorations."
        ),
        "description_hint": "small scenery object sprite (bench, lamp, fence, planter, etc.)",
    },
    "scenery_large": {
        "tiling": False,
        "style_prompt": (
            "Cartoony hand-painted fantasy scenery. Bold outlines, bright saturated "
            "colors, warm lighting. Large decorative structures with rich detail. "
            "Think theme park attractions in a fantasy art style."
        ),
        "description_hint": "large scenery object sprite (building, tower, statue, etc.)",
    },
    "scenery_wall": {
        "tiling": True,
        "style_prompt": (
            "Cartoony hand-painted fantasy walls and fences. Bold outlines, "
            "warm browns for wood, gray for stone, vibrant colors for decorative walls. "
            "Painterly textures. Think medieval fantasy theme park barriers."
        ),
        "description_hint": "wall or fence segment sprite",
    },
    "terrain": {
        "tiling": True,
        "style_prompt": (
            "Cartoony hand-painted fantasy terrain. Rich vibrant greens and warm "
            "earth tones. Bold color gradients. Painterly brushstroke textures. "
            "Keep isometric diamond shape and edge pixels unchanged."
        ),
        "description_hint": "isometric terrain ground tile",
    },
    "footpath": {
        "tiling": True,
        "style_prompt": (
            "Cartoony hand-painted fantasy footpaths. Warm cobblestone or "
            "wooden plank textures. Bold outlines between stones/planks. "
            "Medieval fantasy style path tiles. Keep exact shape and edges."
        ),
        "description_hint": "footpath or queue surface tile",
    },
    "ride": {
        "tiling": False,
        "style_prompt": (
            "Cartoony hand-painted fantasy ride vehicle. Bold outlines, bright "
            "saturated colors, warm lighting. Keep exact silhouette and proportions. "
            "Think whimsical theme park ride in fantasy art style."
        ),
        "description_hint": "ride vehicle or track piece sprite",
    },
}
```

**Step 2: Verify it imports cleanly**

Run: `python3 -c "import sys; sys.path.insert(0, 'tools/reskin'); from categories import CATEGORIES; print(f'{len(CATEGORIES)} categories loaded')" `
Expected: `6 categories loaded`

**Step 3: Commit**

```
/commit
```

---

### Task 2: `batch_sprites.py` — Grid batching

**Files:**
- Create: `tools/reskin/batch_sprites.py`

This is adapted from `/workspace/ottd-reskin-pipeline/batch_env.py`. Key changes:
- No NFO parsing — sprites come from a flat PNG directory
- No sprite ID extraction from filenames (use filename as-is)
- No subcategory batching (not needed without ID ranges)
- Exposed as importable functions AND standalone CLI

**Step 1: Create the batch_sprites module**

```python
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

    Returns (canvas_image, batch_metadata_dict).
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
```

**Step 2: Write a smoke test**

Create `tools/reskin/test_batch_sprites.py`:

```python
"""Smoke tests for batch_sprites.py."""

import json
import os
import tempfile
from PIL import Image

from batch_sprites import load_sprites, create_batches, batch_sprites


def _make_sprite(dir_path, name, w, h):
    """Create a test sprite PNG."""
    img = Image.new("RGBA", (w, h), (255, 0, 0, 200))
    img.save(os.path.join(dir_path, name))


def test_load_sprites():
    with tempfile.TemporaryDirectory() as d:
        _make_sprite(d, "a.png", 64, 64)
        _make_sprite(d, "b.png", 128, 128)
        sprites = load_sprites(d)
        assert len(sprites) == 2
        assert sprites[0]["file"] == "a.png"
        assert sprites[0]["w"] == 64
        assert sprites[1]["file"] == "b.png"


def test_load_sprites_ignores_non_png():
    with tempfile.TemporaryDirectory() as d:
        _make_sprite(d, "a.png", 64, 64)
        with open(os.path.join(d, "readme.txt"), "w") as f:
            f.write("not a sprite")
        sprites = load_sprites(d)
        assert len(sprites) == 1


def test_create_batches_single_bucket():
    sprites = [{"file": f"s{i}.png", "w": 64, "h": 64} for i in range(4)]
    batches = create_batches(sprites)
    assert len(batches) == 1
    assert len(batches[0]["sprites"]) == 4


def test_create_batches_splits_at_16():
    sprites = [{"file": f"s{i}.png", "w": 64, "h": 64} for i in range(20)]
    batches = create_batches(sprites)
    assert len(batches) == 2
    assert len(batches[0]["sprites"]) == 16
    assert len(batches[1]["sprites"]) == 4


def test_create_batches_separates_sizes():
    sprites = [
        {"file": "small.png", "w": 32, "h": 32},
        {"file": "big.png", "w": 256, "h": 256},
    ]
    batches = create_batches(sprites)
    assert len(batches) == 2


def test_batch_sprites_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        sprites_dir = os.path.join(d, "sprites")
        batch_dir = os.path.join(d, "batches")
        os.makedirs(sprites_dir)

        for i in range(5):
            _make_sprite(sprites_dir, f"sprite_{i:03d}.png", 100, 80)

        manifest = batch_sprites(
            sprites_dir=sprites_dir,
            batch_dir=batch_dir,
            style_prompt="test style",
            tiling=True,
        )

        assert manifest is not None
        assert manifest["tiling"] is True
        assert manifest["style_prompt"] == "test style"
        assert len(manifest["batches"]) == 1
        assert len(manifest["batches"][0]["sprites"]) == 5

        # Grid image exists
        grid_path = manifest["batches"][0]["grid_file"]
        assert os.path.exists(grid_path)
        grid = Image.open(grid_path)
        assert grid.size == (2048, 2048)

        # Manifest JSON written
        manifest_path = os.path.join(batch_dir, "manifest.json")
        assert os.path.exists(manifest_path)
        with open(manifest_path) as f:
            loaded = json.load(f)
        assert loaded["version"] == 1
```

**Step 3: Run tests**

Run: `cd /workspace/OpenRCT2-Web && python3 -m pytest tools/reskin/test_batch_sprites.py -v`
Expected: All 6 tests PASS.

**Step 4: Commit**

```
/commit
```

---

### Task 3: `generate_restyled.py` — FAL.ai generation

**Files:**
- Create: `tools/reskin/generate_restyled.py`

Adapted from `/workspace/ottd-reskin-pipeline/generate_restyled.py`. Changes:
- Update default paths to match our directory layout
- Keep all FAL.ai logic identical
- Expose `generate_batch` as importable function

**Step 1: Create the generate module**

```python
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
```

**Step 2: Write tests for the non-API functions**

Add to `tools/reskin/test_generate_restyled.py`:

```python
"""Tests for generate_restyled.py (non-API functions only)."""

from generate_restyled import build_prompt, load_descriptions

import json
import os
import tempfile


def test_build_prompt_no_descriptions():
    batch_meta = {
        "batch_id": "batch_001",
        "cols": 2,
        "rows": 1,
        "sprites": [
            {"cell_row": 0, "cell_col": 0, "cell_label": "A1",
             "original_file": "a.png", "original_w": 64, "original_h": 64},
            {"cell_row": 0, "cell_col": 1, "cell_label": "A2",
             "original_file": "b.png", "original_w": 64, "original_h": 64},
        ],
    }
    prompt = build_prompt(batch_meta, "fantasy style")
    assert "2x1 grid" in prompt
    assert "fantasy style" in prompt
    assert "Row A Col 1: game sprite" in prompt
    assert "Row A Col 2: game sprite" in prompt


def test_build_prompt_with_descriptions():
    batch_meta = {
        "batch_id": "batch_001",
        "cols": 1,
        "rows": 1,
        "sprites": [
            {"cell_row": 0, "cell_col": 0, "cell_label": "A1",
             "original_file": "a.png", "original_w": 64, "original_h": 64},
        ],
    }
    with tempfile.TemporaryDirectory() as d:
        desc_path = os.path.join(d, "batch_001.json")
        with open(desc_path, "w") as f:
            json.dump({"A1": "a wooden bench"}, f)

        prompt = build_prompt(batch_meta, "fantasy style", descriptions_dir=d)
        assert "a wooden bench" in prompt


def test_load_descriptions_missing_dir():
    result = load_descriptions(None, "batch_001")
    assert result == {}


def test_load_descriptions_missing_file():
    with tempfile.TemporaryDirectory() as d:
        result = load_descriptions(d, "batch_999")
        assert result == {}
```

**Step 3: Run tests**

Run: `cd /workspace/OpenRCT2-Web && python3 -m pytest tools/reskin/test_generate_restyled.py -v`
Expected: All 4 tests PASS.

**Step 4: Commit**

```
/commit
```

---

### Task 4: `parse_restyled.py` — Extract and restore sprites

**Files:**
- Create: `tools/reskin/parse_restyled.py`

Adapted from `/workspace/ottd-reskin-pipeline/parse_and_replace.py`. Changes:
- Remove `patch_sprite_sheets()` and `rebuild_grf()` — not needed for OpenRCT2
- Remove `save_png_small_idat()` — standard Pillow PNG is fine
- Output is individual restyled PNGs to a target dir
- Keep `extract_sprites_from_grid()`, `restore_alpha()`, `blend_tile_edges()`, `validate_sprite()` as-is

**Step 1: Create the parse module**

```python
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
```

**Step 2: Write tests**

Create `tools/reskin/test_parse_restyled.py`:

```python
"""Tests for parse_restyled.py."""

import json
import os
import tempfile
import numpy as np
from PIL import Image

from parse_restyled import (
    restore_alpha,
    blend_tile_edges,
    validate_sprite,
    extract_sprites_from_grid,
)


def _make_sprite(w, h, color=(255, 0, 0, 200)):
    return Image.new("RGBA", (w, h), color)


def test_restore_alpha():
    """RGB from restyled, alpha from original."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 128))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        result = restore_alpha(restyled, orig_path)

        arr = np.array(result)
        assert arr[0, 0, 0] == 255  # red from restyled
        assert arr[0, 0, 3] == 128  # alpha from original


def test_restore_alpha_transparent_original():
    """Fully transparent original stays transparent."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        result = restore_alpha(restyled, orig_path)

        arr = np.array(result)
        assert (arr[:, :, 3] == 0).all()


def test_blend_tile_edges():
    """Edges should blend toward original."""
    restyled = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
    original = Image.new("RGBA", (20, 20), (0, 0, 255, 255))
    result = blend_tile_edges(restyled, original, edge_pixels=4)
    arr = np.array(result)
    # Corner (0,0) should be close to original (blue)
    assert arr[0, 0, 2] > arr[0, 0, 0]  # more blue than red
    # Center should be close to restyled (red)
    assert arr[10, 10, 0] > arr[10, 10, 2]  # more red than blue


def test_blend_tile_edges_tiny_sprite():
    """Tiny sprites shouldn't crash."""
    restyled = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    original = Image.new("RGBA", (4, 4), (0, 0, 255, 255))
    result = blend_tile_edges(restyled, original, edge_pixels=6)
    assert result.size == (4, 4)


def test_validate_sprite_different():
    """Sufficiently different sprite passes validation."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        ok, msg = validate_sprite(restyled, orig_path)
        assert ok
        assert "OK" in msg


def test_validate_sprite_too_similar():
    """Nearly identical sprite fails validation."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (100, 100, 100, 255))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (101, 100, 100, 255))
        ok, msg = validate_sprite(restyled, orig_path)
        assert not ok
        assert "Too similar" in msg


def test_validate_sprite_transparent():
    """Fully transparent sprite passes."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
        ok, msg = validate_sprite(restyled, orig_path)
        assert ok
```

**Step 3: Run tests**

Run: `cd /workspace/OpenRCT2-Web && python3 -m pytest tools/reskin/test_parse_restyled.py -v`
Expected: All 7 tests PASS.

**Step 4: Commit**

```
/commit
```

---

### Task 5: `reskin.py` — Orchestrator

**Files:**
- Create: `tools/reskin/reskin.py`

This chains batch -> generate -> parse and supports both workspace mode and standalone mode.

**Step 1: Create the orchestrator**

```python
#!/usr/bin/env python3
"""Orchestrate the OpenRCT2 sprite reskin pipeline.

Chains: batch -> generate -> parse for a sprite directory or workspace.

Workspace mode (from init-reskin-object-workspace.sh):
    python3 reskin.py --workspace ./reskin-workbench/my-object --style "fantasy style"
    python3 reskin.py --workspace ./reskin-workbench/my-object --step parse

Standalone mode (any PNG directory):
    python3 reskin.py --sprites-dir ./sprites --style "pixel art" --through generate
    python3 reskin.py --sprites-dir ./sprites --step parse

Steps: batch -> generate -> parse
"""

import os
import sys
import argparse

# Allow imports from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from categories import CATEGORIES
from batch_sprites import batch_sprites
from generate_restyled import generate_all
from parse_restyled import parse_restyled

STEPS = ["batch", "generate", "parse"]


def resolve_dirs(args):
    """Resolve sprites_dir, batch_dir, restyled_dir from args.

    Returns (sprites_dir, batch_dir, restyled_dir, output_dir).
    """
    if args.workspace:
        base = args.workspace
        sprites_dir = os.path.join(base, "sprites")
        batch_dir = os.path.join(base, "batches")
        restyled_dir = os.path.join(base, "restyled")
        output_dir = sprites_dir  # overwrite originals in workspace
        if not os.path.isdir(sprites_dir):
            print(f"ERROR: Workspace sprites dir not found: {sprites_dir}")
            sys.exit(1)
    elif args.sprites_dir:
        sprites_dir = args.sprites_dir
        parent = os.path.dirname(sprites_dir.rstrip("/"))
        batch_dir = os.path.join(parent, "batches")
        restyled_dir = os.path.join(parent, "restyled")
        output_dir = args.output_dir or sprites_dir
    else:
        print("ERROR: Provide --workspace or --sprites-dir")
        sys.exit(1)

    # Allow explicit overrides
    batch_dir = args.batch_dir or batch_dir
    restyled_dir = args.restyled_dir or restyled_dir
    output_dir = args.output_dir or output_dir

    return sprites_dir, batch_dir, restyled_dir, output_dir


def resolve_style(args):
    """Get style prompt from args or category."""
    if args.style:
        return args.style
    if args.category and args.category in CATEGORIES:
        return CATEGORIES[args.category]["style_prompt"]
    return ""


def resolve_tiling(args):
    """Get tiling flag from args or category."""
    if args.tiling:
        return True
    if args.no_tiling:
        return False
    if args.category and args.category in CATEGORIES:
        return CATEGORIES[args.category].get("tiling", False)
    return None  # let manifest decide


def resolve_description_hint(args):
    """Get description hint from args or category."""
    if args.description_hint:
        return args.description_hint
    if args.category and args.category in CATEGORIES:
        return CATEGORIES[args.category].get("description_hint", "game sprite")
    return "game sprite"


def run_step(step, sprites_dir, batch_dir, restyled_dir, output_dir, args):
    """Run one pipeline step."""
    manifest_path = os.path.join(batch_dir, "manifest.json")

    if step == "batch":
        print("\n--- Batch ---")
        style = resolve_style(args)
        tiling = resolve_tiling(args)
        hint = resolve_description_hint(args)
        batch_sprites(
            sprites_dir=sprites_dir,
            batch_dir=batch_dir,
            style_prompt=style,
            description_hint=hint,
            tiling=tiling if tiling is not None else False,
        )

    elif step == "generate":
        print("\n--- Generate ---")
        if not os.path.exists(manifest_path):
            print(f"ERROR: {manifest_path} not found. Run batch step first.")
            return False

        if not os.environ.get("FAL_KEY"):
            print("ERROR: FAL_KEY environment variable not set")
            return False

        style = resolve_style(args)
        descriptions_dir = args.descriptions_dir
        generate_all(
            manifest_path=manifest_path,
            restyled_dir=restyled_dir,
            style=style or None,
            descriptions_dir=descriptions_dir,
            skip_existing=args.skip_existing,
        )

    elif step == "parse":
        print("\n--- Parse ---")
        if not os.path.exists(manifest_path):
            print(f"ERROR: {manifest_path} not found. Run batch step first.")
            return False

        tiling = resolve_tiling(args)
        parse_restyled(
            manifest_path=manifest_path,
            sprites_dir=sprites_dir,
            restyled_dir=restyled_dir,
            output_dir=output_dir,
            tiling=tiling,
            dry_run=args.dry_run,
        )

    return True


def main():
    parser = argparse.ArgumentParser(
        description="OpenRCT2 AI sprite reskin pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Workspace mode
  python3 reskin.py --workspace ./reskin-workbench/my-object \\
      --style "Cartoony fantasy, bold outlines" --through generate
  python3 reskin.py --workspace ./reskin-workbench/my-object --step parse

  # Standalone mode
  python3 reskin.py --sprites-dir ./sprites --style "pixel art" --tiling

  # Using a category preset
  python3 reskin.py --sprites-dir ./sprites --category scenery_small
""",
    )

    # Input source (one required)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--workspace", help="Reskin workspace dir "
                        "(from init-reskin-object-workspace.sh)")
    source.add_argument("--sprites-dir", help="Directory of sprite PNGs")

    # Style
    parser.add_argument("--style", default=None, help="Style prompt for AI")
    parser.add_argument("--category", default=None,
                        choices=list(CATEGORIES.keys()),
                        help="Use a category preset for style/tiling/hints")
    parser.add_argument("--description-hint", default=None,
                        help="Hint for per-cell descriptions")
    parser.add_argument("--descriptions-dir", default=None,
                        help="Dir with per-batch description JSON files")

    # Tiling
    parser.add_argument("--tiling", action="store_true",
                        help="Enable tile edge blending")
    parser.add_argument("--no-tiling", action="store_true",
                        help="Disable tile edge blending")

    # Step control
    parser.add_argument("--step", choices=STEPS,
                        help="Run only this step")
    parser.add_argument("--through", choices=STEPS,
                        help="Run all steps through this one")

    # Flags
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse step: validate only")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Generate step: skip existing outputs")

    # Path overrides
    parser.add_argument("--batch-dir", default=None)
    parser.add_argument("--restyled-dir", default=None)
    parser.add_argument("--output-dir", default=None)

    # Info
    parser.add_argument("--list-categories", action="store_true",
                        help="List available category presets and exit")

    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for name, cfg in CATEGORIES.items():
            tiling = "tiling" if cfg.get("tiling") else "no-tiling"
            print(f"  {name:20s} [{tiling}]")
            print(f"    {cfg['style_prompt'][:80]}...")
        return

    if not args.workspace and not args.sprites_dir:
        parser.print_help()
        return

    sprites_dir, batch_dir, restyled_dir, output_dir = resolve_dirs(args)

    print(f"Sprites:  {sprites_dir}")
    print(f"Batches:  {batch_dir}")
    print(f"Restyled: {restyled_dir}")
    print(f"Output:   {output_dir}")

    if args.step:
        steps = [args.step]
    elif args.through:
        idx = STEPS.index(args.through)
        steps = STEPS[:idx + 1]
    else:
        steps = STEPS

    for step in steps:
        ok = run_step(step, sprites_dir, batch_dir, restyled_dir, output_dir, args)
        if not ok:
            print(f"\nStep '{step}' failed. Stopping.")
            sys.exit(1)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
```

**Step 2: Write tests**

Create `tools/reskin/test_reskin.py`:

```python
"""Tests for reskin.py orchestrator."""

import os
import sys
import tempfile
from unittest.mock import patch
from PIL import Image
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reskin import resolve_dirs, resolve_style, resolve_tiling


def test_resolve_dirs_workspace():
    with tempfile.TemporaryDirectory() as d:
        sprites = os.path.join(d, "sprites")
        os.makedirs(sprites)
        args = SimpleNamespace(
            workspace=d, sprites_dir=None,
            batch_dir=None, restyled_dir=None, output_dir=None,
        )
        s, b, r, o = resolve_dirs(args)
        assert s == sprites
        assert b == os.path.join(d, "batches")
        assert r == os.path.join(d, "restyled")
        assert o == sprites  # overwrites originals


def test_resolve_dirs_standalone():
    args = SimpleNamespace(
        workspace=None, sprites_dir="/tmp/my-sprites",
        batch_dir=None, restyled_dir=None, output_dir=None,
    )
    s, b, r, o = resolve_dirs(args)
    assert s == "/tmp/my-sprites"
    assert b == "/tmp/batches"
    assert r == "/tmp/restyled"
    assert o == "/tmp/my-sprites"


def test_resolve_style_explicit():
    args = SimpleNamespace(style="pixel art", category=None)
    assert resolve_style(args) == "pixel art"


def test_resolve_style_from_category():
    args = SimpleNamespace(style=None, category="scenery_small")
    style = resolve_style(args)
    assert "fantasy" in style.lower() or "cartoony" in style.lower()


def test_resolve_tiling_explicit():
    args = SimpleNamespace(tiling=True, no_tiling=False, category=None)
    assert resolve_tiling(args) is True


def test_resolve_tiling_from_category():
    args = SimpleNamespace(tiling=False, no_tiling=False, category="terrain")
    assert resolve_tiling(args) is True

    args = SimpleNamespace(tiling=False, no_tiling=False, category="scenery_small")
    assert resolve_tiling(args) is False
```

**Step 3: Run tests**

Run: `cd /workspace/OpenRCT2-Web && python3 -m pytest tools/reskin/test_reskin.py -v`
Expected: All 6 tests PASS.

**Step 4: Commit**

```
/commit
```

---

### Task 6: Run full test suite and final commit

**Step 1: Run all tests together**

Run: `cd /workspace/OpenRCT2-Web && python3 -m pytest tools/reskin/ -v`
Expected: All tests pass (6 + 4 + 7 + 6 = 23 tests).

**Step 2: Verify CLI help works**

Run these four commands and verify each prints usage/help:
```bash
python3 tools/reskin/batch_sprites.py --help
python3 tools/reskin/generate_restyled.py --help
python3 tools/reskin/parse_restyled.py --help
python3 tools/reskin/reskin.py --help
```

**Step 3: Verify category listing**

Run: `python3 tools/reskin/reskin.py --list-categories`
Expected: Lists 6 categories with tiling flags.

**Step 4: Final commit with all files**

```
/commit
```
