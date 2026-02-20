# Object Authoring Workflow (PNG -> images.dat -> .parkobj)

This guide uses scripts in this repo to create editable object workspaces from an existing web upload package.

## Prerequisites

- Input upload zip (example: `/Users/meiliu/Downloads/openrct2-upload.zip`)
- Docker available (used by `scripts/openrct2-cli-docker.sh`)
- `build-native/openrct2-cli` built once (the wrapper prints the exact build command if missing)

## 1) Initialize an editable workspace

```bash
scripts/init-reskin-object-workspace.sh \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  object/official/scenery_small/official.scenery_small.support_structure_half.parkobj \
  /Users/meiliu/git/rosebud/OpenRCT2-Web/reskin-workbench/support-structure-half
```

Workspace contents:

- `object.json`: object metadata and IDs
- `images.dat`: current sprite archive
- `object-path-in-assets-zip.txt`: target file path inside `assets/assets.zip`
- `sprites/*.png`: editable sprite frames
- `sprites.json`: sprite manifest used to rebuild `images.dat`
- `rebuild-object.sh`: one-command rebuild and pack

## 2) Edit sprite PNGs

Edit files in:

`/Users/meiliu/git/rosebud/OpenRCT2-Web/reskin-workbench/support-structure-half/sprites/`

Keep sprite count/order stable unless you intentionally update `object.json` image ranges.

## 3) Rebuild the object

```bash
/Users/meiliu/git/rosebud/OpenRCT2-Web/reskin-workbench/support-structure-half/rebuild-object.sh
```

Outputs:

- `images.dat`
- `reskinned.parkobj`

## 4) Build a patched upload zip

```bash
scripts/build-reskin-object-upload.sh \
  --rebuild \
  /Users/meiliu/Downloads/openrct2-upload.zip \
  /tmp/openrct2-upload-reskinned.zip \
  /Users/meiliu/git/rosebud/OpenRCT2-Web/reskin-workbench/support-structure-half
```

This command rebuilds the workspace artifact, maps it to the original object path from `object-path-in-assets-zip.txt`, and writes a patched upload zip.

For additional options and multi-object packaging, see:
`docs/reskin-pipeline.md`

## Notes

- `scripts/openrct2-cli-docker.sh` runs `openrct2-cli` inside Docker and mirrors your current repo subdirectory as container working directory.
- `init-reskin-object-workspace.sh` filters non-JSON log lines from export output so `sprites.json` stays valid.
- Objects that depend on `$RCT2:OBJDATA/...` can need additional base game data to export perfectly. Start with self-contained `.parkobj` objects (those using `$LGX:images.dat[...]`) for easiest iteration.
