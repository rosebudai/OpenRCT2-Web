#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  build-reskin-upload.sh <input-upload-zip> <overlay-dir> [output-zip]

Description:
  Creates a reskinned OpenRCT2 web upload package by applying file overlays.

Overlay layout:
  <overlay-dir>/upload/        -> merged into upload root (index.html, index.js, etc.)
  <overlay-dir>/assets/        -> merged into assets/assets.zip
  <overlay-dir>/rct2-content/  -> merged into assets/rct2-content.zip
  <overlay-dir>/openrct2/      -> merged into assets/openrct2.zip

Examples:
  build-reskin-upload.sh \
      /path/to/openrct2-upload.zip \
      /path/to/overlay

  build-reskin-upload.sh \
      /path/to/openrct2-upload.zip \
      /path/to/overlay \
      /tmp/openrct2-upload-reskinned.zip
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage >&2
    exit 1
fi

input_zip="$1"
overlay_dir="$2"
output_zip="${3:-/tmp/openrct2-upload-reskinned.zip}"

if [[ ! -f "$input_zip" ]]; then
    echo "Input file not found: $input_zip" >&2
    exit 1
fi
if [[ ! -d "$overlay_dir" ]]; then
    echo "Overlay directory not found: $overlay_dir" >&2
    exit 1
fi

workdir="$(mktemp -d /tmp/openrct2-reskin-upload.XXXXXX)"
cleanup() {
    rm -rf "$workdir"
}
trap cleanup EXIT

merge_tree() {
    local src="$1"
    local dst="$2"
    local label="$3"

    if [[ ! -d "$src" ]]; then
        echo "No overlay for $label ($src)."
        return 0
    fi

    local copied=0
    while IFS= read -r -d '' rel; do
        rel="${rel#./}"
        mkdir -p "$dst/$(dirname "$rel")"
        cp -f "$src/$rel" "$dst/$rel"
        copied="$((copied + 1))"
    done < <(cd "$src" && find . -type f ! -name '.DS_Store' ! -name '._*' -print0)

    echo "Applied $copied file(s) to $label."
}

repack_zip_from_dir() {
    local source_dir="$1"
    local zip_path="$2"
    local repacked_zip="$zip_path.repacked"
    local list_file
    list_file="$(mktemp "$workdir/files.XXXXXX")"
    local dirs_file
    dirs_file="$(mktemp "$workdir/dirs.XXXXXX")"
    local merged_file
    merged_file="$(mktemp "$workdir/merged.XXXXXX")"

    (
        cd "$source_dir"
        LC_ALL=C find . -type f | sed 's#^\./##' | sort > "$list_file"
        LC_ALL=C find . -type d | sed 's#^\./##' | awk '$0 != "." && NF { print $0 "/" }' | sort > "$dirs_file"
        if [[ ! -s "$list_file" ]]; then
            echo "Refusing to create empty archive: $zip_path" >&2
            exit 1
        fi
        cat "$dirs_file" "$list_file" > "$merged_file"
        rm -f "$repacked_zip"
        zip -q -X "$repacked_zip" -@ < "$merged_file"
    )

    mv -f "$repacked_zip" "$zip_path"
    rm -f "$list_file" "$dirs_file" "$merged_file"
}

apply_overlay_to_nested_zip() {
    local zip_path="$1"
    local nested_overlay="$2"
    local label="$3"
    local tmp_dir="$workdir/${label//[^a-zA-Z0-9._-]/_}"

    if [[ ! -f "$zip_path" ]]; then
        echo "Missing required archive: $zip_path" >&2
        exit 1
    fi

    if [[ ! -d "$nested_overlay" ]]; then
        echo "No overlay for $label ($nested_overlay)."
        return 0
    fi

    mkdir -p "$tmp_dir"
    unzip -q "$zip_path" -d "$tmp_dir"
    merge_tree "$nested_overlay" "$tmp_dir" "$label"
    repack_zip_from_dir "$tmp_dir" "$zip_path"
}

require_zip_entry() {
    local zip_path="$1"
    local entry="$2"

    if ! grep -Fxq "$entry" < <(unzip -Z1 "$zip_path"); then
        echo "Missing required entry in $(basename "$zip_path"): $entry" >&2
        exit 1
    fi
}

echo "Working directory: $workdir"
echo "Input:   $input_zip"
echo "Overlay: $overlay_dir"
echo "Output:  $output_zip"

unzip -q "$input_zip" -d "$workdir/in"

assets_zip="$workdir/in/assets/assets.zip"
rct2_zip="$workdir/in/assets/rct2-content.zip"
openrct2_zip="$workdir/in/assets/openrct2.zip"

merge_tree "$overlay_dir/upload" "$workdir/in" "upload root"
apply_overlay_to_nested_zip "$assets_zip" "$overlay_dir/assets" "assets.zip"
apply_overlay_to_nested_zip "$rct2_zip" "$overlay_dir/rct2-content" "rct2-content.zip"
apply_overlay_to_nested_zip "$openrct2_zip" "$overlay_dir/openrct2" "openrct2.zip"

# Keep the required files used by the web loader.
require_zip_entry "$assets_zip" "language/en-US.txt"
require_zip_entry "$assets_zip" "g2.dat"
require_zip_entry "$assets_zip" "object/official/footpath_surface/openrct2.footpath_surface.invisible.json"
require_zip_entry "$assets_zip" "sequence/openrct2.parkseq"
require_zip_entry "$rct2_zip" "Data/ch.dat"
require_zip_entry "$rct2_zip" "ObjData/BALLN.DAT"

mkdir -p "$(dirname "$output_zip")"
rm -f "$output_zip"
(
    cd "$workdir/in"
    LC_ALL=C find . -type f | sed 's#^\./##' | sort | zip -q -X "$output_zip" -@
)

input_bytes="$(stat -f%z "$input_zip")"
output_bytes="$(stat -f%z "$output_zip")"
delta_bytes="$((input_bytes - output_bytes))"

echo
echo "Done."
echo "Input size : $input_bytes bytes"
echo "Output size: $output_bytes bytes"
echo "Delta      : $delta_bytes bytes"
