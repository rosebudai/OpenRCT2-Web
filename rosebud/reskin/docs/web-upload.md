# Reskinning OpenRCT2 Web Uploads

This repo's web package is typically distributed as:

- `index.html`
- `index.js`
- `assets/assets.zip`
- `assets/rct2-content.zip`
- `assets/openrct2.zip`

Use `rosebud/reskin/build-upload.sh` to apply your own files on top of an existing upload zip.

If your inputs come from initialized object workspaces (`reskin-workbench/...`), prefer:
`rosebud/reskin/build-object-upload.sh` (see `rosebud/reskin/docs/pipeline.md`).

For creating/editing object sprite files first, see:
`rosebud/reskin/docs/object-authoring.md`

## Overlay Structure

Create an overlay directory with any of these subfolders:

- `upload/` files merged into the top-level upload package.
- `assets/` files merged into `assets/assets.zip`.
- `rct2-content/` files merged into `assets/rct2-content.zip`.
- `openrct2/` files merged into `assets/openrct2.zip`.

Only include files you want to replace or add.

## Command

```bash
rosebud/reskin/build-upload.sh \
  /path/to/openrct2-upload.zip \
  /path/to/overlay \
  /tmp/openrct2-upload-reskinned.zip
```

If output is omitted, it defaults to `/tmp/openrct2-upload-reskinned.zip`.

## Common Reskin Targets

1. Replace OpenRCT2 object visuals:
- Put replacement `.parkobj` or `.json` files under:
`overlay/assets/object/...`
- Example:
`overlay/assets/object/official/ride/openrct2.ride.modern_twister.parkobj`

2. Replace UI sprite data:
- Build new `g2.dat` from a modified sprite manifest (using `openrct2-cli sprite build`).
- Place it at:
`overlay/assets/g2.dat`

3. Replace font/palette data:
- `overlay/assets/fonts.dat`
- `overlay/assets/palettes.dat`

4. Replace legacy RCT2 DAT assets:
- Place replacements under:
`overlay/rct2-content/Data/...` or `overlay/rct2-content/ObjData/...`

## Notes

- The script validates core boot files remain present after patching.
- For object replacements, keep object IDs stable unless you intentionally add new IDs and update content that references them.
- To inspect paths inside an archive, use:

```bash
unzip -Z1 /path/to/assets.zip | head -200
```
