#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  init-reskin-object-workspace.sh <input-upload-zip> <object-path-in-assets-zip> <workspace-dir> [openrct2-cli-cmd]

Description:
  Creates an editable object authoring workspace from an object contained in assets/assets.zip.

  Output workspace includes:
  - object.json (source metadata)
  - images.dat (if present in source .parkobj)
  - object-path-in-assets-zip.txt (target location for upload overlay)
  - source-object/ (original extracted source object file)
  - sprites/ (exported PNG sprite frames)
  - sprites.json (sprite build manifest wrapping exported entries)
  - rebuild-object.sh (rebuild images.dat + pack reskinned.parkobj)

Examples:
  init-reskin-object-workspace.sh \
    /Users/meiliu/Downloads/openrct2-upload.zip \
    object/official/scenery_small/official.scenery_small.support_structure_half.parkobj \
    ./reskin-workbench/support-structure-half

  init-reskin-object-workspace.sh \
    /Users/meiliu/Downloads/openrct2-upload.zip \
    object/official/scenery_small/official.scenery_small.support_structure_half.parkobj \
    ./reskin-workbench/support-structure-half \
    ./scripts/openrct2-cli-docker.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 3 || $# -gt 4 ]]; then
    usage >&2
    exit 1
fi

input_zip="$1"
object_path="$2"
workspace_dir="$3"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cli_cmd="${4:-$repo_root/scripts/openrct2-cli-docker.sh}"

if [[ ! -f "$input_zip" ]]; then
    echo "Input upload zip not found: $input_zip" >&2
    exit 1
fi

if [[ ! -x "$cli_cmd" ]]; then
    echo "openrct2-cli command is not executable: $cli_cmd" >&2
    exit 1
fi

if [[ -e "$workspace_dir" && -n "$(find "$workspace_dir" -mindepth 1 -maxdepth 1 2>/dev/null || true)" ]]; then
    echo "Workspace directory already exists and is not empty: $workspace_dir" >&2
    exit 1
fi

workdir="$(mktemp -d /tmp/openrct2-object-init.XXXXXX)"
cleanup() {
    rm -rf "$workdir"
}
trap cleanup EXIT

echo "Working directory: $workdir"
echo "Input zip:         $input_zip"
echo "Object path:       $object_path"
echo "Workspace:         $workspace_dir"
echo "CLI command:       $cli_cmd"

unzip -q "$input_zip" assets/assets.zip -d "$workdir/in"
assets_zip="$workdir/in/assets/assets.zip"

if [[ ! -f "$assets_zip" ]]; then
    echo "Missing assets/assets.zip in upload: $input_zip" >&2
    exit 1
fi

if ! grep -Fxq "$object_path" < <(unzip -Z1 "$assets_zip"); then
    echo "Object path not found in assets/assets.zip: $object_path" >&2
    exit 1
fi

mkdir -p "$workspace_dir"
mkdir -p "$workspace_dir/source-object"
mkdir -p "$workspace_dir/sprites"

source_basename="$(basename "$object_path")"
source_object_path="$workspace_dir/source-object/$source_basename"
unzip -p "$assets_zip" "$object_path" > "$source_object_path"

printf '%s\n' "$object_path" > "$workspace_dir/object-path-in-assets-zip.txt"

if [[ "$source_basename" == *.parkobj ]]; then
    unzip -p "$source_object_path" object.json > "$workspace_dir/object.json"
    if grep -Fxq "images.dat" < <(unzip -Z1 "$source_object_path"); then
        unzip -p "$source_object_path" images.dat > "$workspace_dir/images.dat"
    else
        echo "Warning: source .parkobj has no images.dat."
    fi
elif [[ "$source_basename" == *.json ]]; then
    cp -f "$source_object_path" "$workspace_dir/object.json"
else
    echo "Unsupported object source extension: $source_basename" >&2
    exit 1
fi

raw_entries="$workdir/sprite_entries.raw"
clean_entries="$workdir/sprite_entries.clean"
(
    cd "$workspace_dir"
    "$cli_cmd" sprite exportobject "source-object/$source_basename" "sprites" > "$raw_entries" 2>&1 || true
)

grep -E '^[[:space:]]*(""{1}|\{)' "$raw_entries" > "$clean_entries" || true

if [[ ! -s "$clean_entries" ]]; then
    echo "Failed to extract valid sprite entries from export output." >&2
    echo "--- begin raw export output ---" >&2
    sed -n '1,120p' "$raw_entries" >&2
    echo "--- end raw export output ---" >&2
    exit 1
fi

{
    echo "{"
    echo "  \"images\": ["
    sed 's/^/    /' "$clean_entries"
    echo "  ]"
    echo "}"
} > "$workspace_dir/sprites.json"

cat > "$workspace_dir/rebuild-object.sh" <<EOF
#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
CLI_CMD="\${1:-$cli_cmd}"

if [[ ! -x "\$CLI_CMD" ]]; then
    echo "openrct2-cli command is not executable: \$CLI_CMD" >&2
    exit 1
fi

(
    cd "\$SCRIPT_DIR"
    "\$CLI_CMD" sprite build "images.dat" "sprites.json" silent
    zip -q -X "reskinned.parkobj" "object.json" "images.dat"
)

echo "Rebuilt:"
echo "  \$SCRIPT_DIR/images.dat"
echo "  \$SCRIPT_DIR/reskinned.parkobj"
EOF
chmod +x "$workspace_dir/rebuild-object.sh"

echo
echo "Workspace ready."
echo "Next steps:"
echo "  1) Edit PNGs in: $workspace_dir/sprites/"
echo "  2) Rebuild object: $workspace_dir/rebuild-object.sh"
echo "  3) Overlay output file into upload package:"
echo "     overlay/assets/object/.../<your file>.parkobj"
