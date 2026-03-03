# Reskin Pipeline (Workspace -> Upload Zip)

This pipeline packages object reskins into a playable OpenRCT2 web upload zip.

It is built from these scripts:

- `rosebud/reskin/init-workspace.sh`
- `rosebud/reskin/build-object-upload.sh`
- `rosebud/reskin/build-upload.sh`

## Prerequisites

- Input upload zip (example: `/Users/meiliu/Downloads/openrct2-upload.zip`)
- Docker available (for `scripts/openrct2-cli-docker.sh`)
- `build_native/openrct2-cli` built once

## 1) Initialize one or more workspaces

```bash
rosebud/reskin/init-workspace.sh \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  object/official/scenery_small/official.scenery_small.support_structure_half.parkobj \
  ./reskin-workbench/support-structure-half
```

The initializer writes `object-path-in-assets-zip.txt` in each workspace so the pipeline can map output files automatically.

## 2) Edit sprites

Edit PNGs under each workspace `sprites/` directory.

## 3) Build a patched upload zip (single command)

For one workspace:

```bash
rosebud/reskin/build-object-upload.sh \
  --rebuild \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  /tmp/openrct2-upload-reskinned.zip \
  ./reskin-workbench/support-structure-half
```

For multiple workspaces:

```bash
rosebud/reskin/build-object-upload.sh \
  --rebuild \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  /tmp/openrct2-upload-reskinned.zip \
  ./reskin-workbench/support-structure-half \
  ./reskin-workbench/another-object
```

If you already rebuilt the workspace artifacts, omit `--rebuild`.

## Optional: Keep the generated overlay for inspection

```bash
rosebud/reskin/build-object-upload.sh \
  --rebuild \
  --overlay-dir /tmp/reskin-overlay \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  /tmp/openrct2-upload-reskinned.zip \
  ./reskin-workbench/support-structure-half
```

## Optional: Use a custom `openrct2-cli` command

```bash
rosebud/reskin/build-object-upload.sh \
  --rebuild \
  --cli-cmd ./scripts/openrct2-cli-docker.sh \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  /tmp/openrct2-upload-reskinned.zip \
  ./reskin-workbench/support-structure-half
```
