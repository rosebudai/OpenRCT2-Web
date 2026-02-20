#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  create-reskin-overlay.sh <overlay-dir> <workspace-dir> [workspace-dir...]

Description:
  Assembles an overlay directory from one or more initialized reskin workspaces.

Each workspace must contain:
  - object-path-in-assets-zip.txt
  - reskinned.parkobj (for .parkobj targets) OR object.json (for .json targets)

The generated overlay can be consumed by scripts/build-reskin-upload.sh.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 2 ]]; then
    usage >&2
    exit 1
fi

overlay_dir="$1"
shift

mkdir -p "$overlay_dir/assets"

copied=0
for workspace_dir in "$@"; do
    if [[ ! -d "$workspace_dir" ]]; then
        echo "Workspace directory not found: $workspace_dir" >&2
        exit 1
    fi

    object_path_file="$workspace_dir/object-path-in-assets-zip.txt"
    if [[ ! -f "$object_path_file" ]]; then
        echo "Missing workspace metadata file: $object_path_file" >&2
        echo "Re-run scripts/init-reskin-object-workspace.sh for this workspace." >&2
        exit 1
    fi

    object_path="$(<"$object_path_file")"
    object_path="${object_path%$'\r'}"

    if [[ -z "$object_path" ]]; then
        echo "Empty object path in metadata: $object_path_file" >&2
        exit 1
    fi
    if [[ "$object_path" = /* || "$object_path" == *"/../"* || "$object_path" == "../"* || "$object_path" == *"/.." ]]; then
        echo "Unsafe object path in metadata: $object_path" >&2
        exit 1
    fi

    artifact_path=""
    case "$object_path" in
        *.parkobj)
            artifact_path="$workspace_dir/reskinned.parkobj"
            if [[ ! -f "$artifact_path" ]]; then
                echo "Missing artifact for $workspace_dir: $artifact_path" >&2
                echo "Run: $workspace_dir/rebuild-object.sh" >&2
                exit 1
            fi
            ;;
        *.json)
            artifact_path="$workspace_dir/object.json"
            if [[ ! -f "$artifact_path" ]]; then
                echo "Missing artifact for $workspace_dir: $artifact_path" >&2
                exit 1
            fi
            ;;
        *)
            echo "Unsupported object target path extension: $object_path" >&2
            exit 1
            ;;
    esac

    target_path="$overlay_dir/assets/$object_path"
    mkdir -p "$(dirname "$target_path")"
    cp -f "$artifact_path" "$target_path"
    copied="$((copied + 1))"

    echo "Mapped workspace:"
    echo "  $workspace_dir"
    echo "    -> assets/$object_path"
done

echo
echo "Overlay ready: $overlay_dir"
echo "Objects mapped: $copied"
