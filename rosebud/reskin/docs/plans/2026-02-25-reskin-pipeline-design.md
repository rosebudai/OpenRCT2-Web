# OpenRCT2 AI Reskin Pipeline Design

## Problem

The existing OpenRCT2-Web reskin workflow requires manual sprite editing. The ottd-reskin-pipeline repo demonstrates that AI-powered restyling (FAL.ai Gemini 3 Pro) works well for game sprites when batched into 4x4 grids. We want to bring that capability into OpenRCT2.

## Architecture

```
.parkobj files (via init-reskin-object-workspace.sh)
    OR
Arbitrary sprite PNG directories
    |
rosebud/reskin/batch_sprites.py       <- generic: creates 4x4 grids + manifest.json
    |
rosebud/reskin/generate_restyled.py   <- generic: sends grids to FAL.ai Gemini 3 Pro
    |
rosebud/reskin/parse_restyled.py      <- generic: extracts sprites, restores alpha, blends edges
    |
Restyled PNGs back in workspace sprites/ dir
    |
rebuild-object.sh -> create-reskin-overlay.sh -> build-reskin-upload.sh  (existing)
```

## Files

| File | Role |
|------|------|
| `rosebud/reskin/categories.py` | Category configs: style prompts, tiling flags, description hints. Starts with scenery presets, extensible. |
| `rosebud/reskin/batch_sprites.py` | Scans a sprite directory, groups by size into 4x4 grids (2048x2048), writes manifest.json. Game-agnostic. |
| `rosebud/reskin/generate_restyled.py` | Reads manifest, sends each grid to FAL.ai Gemini 3 Pro, saves restyled grids. |
| `rosebud/reskin/parse_restyled.py` | Extracts sprites from AI grids using manifest coordinates, restores original alpha masks, blends tile edges. |
| `rosebud/reskin/reskin.py` | Orchestrator: chains batch -> generate -> parse. Supports `--step` and `--through`. |

## Adaptations from ottd pipeline

1. **No NFO/GRF parsing** - OpenRCT2 uses .parkobj (zip with object.json + images.dat). Existing shell scripts handle extraction/repackaging. Python pipeline works on flat PNG directories only.
2. **Workspace integration** - `reskin.py` accepts a workspace dir from `init-reskin-object-workspace.sh`, finds `sprites/`, runs the pipeline, writes restyled PNGs back.
3. **Standalone mode** - Also works on any PNG directory via `--sprites-dir` for g2.dat sprites, legacy DAT assets, etc.
4. **Category config is optional** - Categories provide style prompts and tiling flags but aren't required. Can use `--style` and `--tiling` directly.

## What stays from ottd pipeline

- 4x4 grid batching with size bucketing (128px steps)
- 2048x2048 canvas, gray background, black grid lines
- FAL.ai Gemini 3 Pro image-edit API
- Alpha mask restoration from originals
- Tile edge blending (6px gradient, clamped to half dimension)
- Per-cell description support
- Manifest JSON format tracking exact coordinates

## Example workflows

### Workspace mode (.parkobj)

```bash
# 1. Init workspace (existing)
rosebud/reskin/init-workspace.sh \
  upload.zip \
  object/official/scenery_small/official.scenery_small.support_structure_half.parkobj \
  ./reskin-workbench/support-structure

# 2. AI reskin (NEW)
python3 rosebud/reskin/reskin.py \
  --workspace ./reskin-workbench/support-structure \
  --style "Cartoony hand-painted fantasy. Bold outlines, vibrant colors." \
  --through generate

# 3. Review, then apply
python3 rosebud/reskin/reskin.py \
  --workspace ./reskin-workbench/support-structure \
  --step parse

# 4. Rebuild + package (existing)
./reskin-workbench/support-structure/rebuild-object.sh
rosebud/reskin/build-object-upload.sh \
  upload.zip /tmp/reskinned.zip ./reskin-workbench/support-structure
```

### Standalone mode (any PNGs)

```bash
python3 rosebud/reskin/reskin.py \
  --sprites-dir ./my-sprites/ \
  --style "Pixel art, 16-bit SNES style" \
  --tiling
```

## Dependencies

- Python 3.8+
- Pillow, numpy, fal-client
- FAL_KEY environment variable
