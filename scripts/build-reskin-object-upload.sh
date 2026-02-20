#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  build-reskin-object-upload.sh [options] <input-upload-zip> <output-upload-zip> <workspace-dir> [workspace-dir...]

Description:
  End-to-end object reskin pipeline:
    1) Optionally rebuild each workspace artifact.
    2) Assemble an overlay from workspace metadata.
    3) Produce a patched upload zip.

Options:
  --rebuild               Run <workspace>/rebuild-object.sh before packaging.
  --cli-cmd <path>        openrct2-cli command passed to rebuild-object.sh (only with --rebuild).
  --overlay-dir <path>    Keep/use this overlay directory instead of a temporary one.
  -h, --help              Show this help message.

Examples:
  build-reskin-object-upload.sh \
    --rebuild \
    /path/to/openrct2-upload.zip \
    /tmp/openrct2-upload-reskinned.zip \
    ./reskin-workbench/support-structure-half

  build-reskin-object-upload.sh \
    --overlay-dir /tmp/reskin-overlay \
    /path/to/openrct2-upload.zip \
    /tmp/openrct2-upload-reskinned.zip \
    ./reskin-workbench/support-structure-half \
    ./reskin-workbench/another-object
EOF
}

rebuild=0
cli_cmd=""
overlay_dir=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --rebuild)
            rebuild=1
            shift
            ;;
        --cli-cmd)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --cli-cmd." >&2
                exit 1
            fi
            cli_cmd="$2"
            shift 2
            ;;
        --overlay-dir)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --overlay-dir." >&2
                exit 1
            fi
            overlay_dir="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -lt 3 ]]; then
    usage >&2
    exit 1
fi

input_zip="$1"
output_zip="$2"
shift 2
workspace_dirs=("$@")

if [[ ! -f "$input_zip" ]]; then
    echo "Input upload zip not found: $input_zip" >&2
    exit 1
fi

if [[ "$rebuild" -eq 0 && -n "$cli_cmd" ]]; then
    echo "--cli-cmd requires --rebuild." >&2
    exit 1
fi
if [[ "$rebuild" -eq 1 && -n "$cli_cmd" && ! -x "$cli_cmd" ]]; then
    echo "openrct2-cli command is not executable: $cli_cmd" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
overlay_builder="$repo_root/scripts/create-reskin-overlay.sh"
upload_builder="$repo_root/scripts/build-reskin-upload.sh"

if [[ ! -x "$overlay_builder" ]]; then
    echo "Missing executable script: $overlay_builder" >&2
    exit 1
fi
if [[ ! -x "$upload_builder" ]]; then
    echo "Missing executable script: $upload_builder" >&2
    exit 1
fi

for workspace_dir in "${workspace_dirs[@]}"; do
    if [[ ! -d "$workspace_dir" ]]; then
        echo "Workspace directory not found: $workspace_dir" >&2
        exit 1
    fi
done

cleanup_overlay=0
if [[ -z "$overlay_dir" ]]; then
    overlay_dir="$(mktemp -d /tmp/openrct2-reskin-overlay.XXXXXX)"
    cleanup_overlay=1
else
    mkdir -p "$overlay_dir"
    if [[ -n "$(find "$overlay_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null || true)" ]]; then
        echo "Overlay directory must be empty: $overlay_dir" >&2
        exit 1
    fi
fi

cleanup() {
    if [[ "$cleanup_overlay" -eq 1 ]]; then
        rm -rf "$overlay_dir"
    fi
}
trap cleanup EXIT

if [[ "$rebuild" -eq 1 ]]; then
    echo "Rebuilding workspace artifacts..."
    for workspace_dir in "${workspace_dirs[@]}"; do
        rebuild_script="$workspace_dir/rebuild-object.sh"
        if [[ ! -x "$rebuild_script" ]]; then
            echo "Missing executable rebuild script: $rebuild_script" >&2
            exit 1
        fi
        if [[ -n "$cli_cmd" ]]; then
            "$rebuild_script" "$cli_cmd"
        else
            "$rebuild_script"
        fi
    done
fi

echo "Assembling overlay at: $overlay_dir"
"$overlay_builder" "$overlay_dir" "${workspace_dirs[@]}"

echo "Building patched upload: $output_zip"
"$upload_builder" "$input_zip" "$overlay_dir" "$output_zip"

echo
echo "Pipeline complete."
echo "Output: $output_zip"
if [[ "$cleanup_overlay" -eq 0 ]]; then
    echo "Overlay: $overlay_dir"
fi
