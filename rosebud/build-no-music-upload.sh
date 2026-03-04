#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  build-no-music-upload.sh <input-upload-zip> [output-zip]

Description:
  Creates a no-music variant of an OpenRCT2 web upload package by stripping:
  - RCT2 legacy music payloads from rct2-content.zip (Data/css*.dat)
  - OpenRCT2 music payloads from assets.zip:
      - assetpack/openrct2.music.*.parkap
      - object/official/music/*

  The input zip layout:
    index.html, index.js (root — become GenericFiles)
    assets/openrct2.zip, assets/assets.zip, assets/rct2-content.zip (become Assets)

Examples:
  build-no-music-upload.sh /path/to/openrct2-upload.zip
  build-no-music-upload.sh /path/to/openrct2-upload.zip /tmp/openrct2-upload-no-music.zip
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage >&2
    exit 1
fi

input_zip="$1"
output_zip="${2:-/tmp/openrct2-upload-no-music.zip}"

if [[ ! -f "$input_zip" ]]; then
    echo "Input file not found: $input_zip" >&2
    exit 1
fi

workdir="$(mktemp -d /tmp/openrct2-no-music.XXXXXX)"
cleanup() {
    rm -rf "$workdir"
}
trap cleanup EXIT

echo "Working directory: $workdir"
echo "Input:  $input_zip"
echo "Output: $output_zip"

unzip -q "$input_zip" -d "$workdir/in"

rct2_zip="$workdir/in/assets/rct2-content.zip"
assets_zip="$workdir/in/assets/assets.zip"

if [[ ! -f "$rct2_zip" ]]; then
    echo "Missing assets/rct2-content.zip in input upload." >&2
    exit 1
fi
if [[ ! -f "$assets_zip" ]]; then
    echo "Missing assets/assets.zip in input upload." >&2
    exit 1
fi

echo "Stripping legacy CSS music from rct2-content.zip..."
if zip -q -d "$rct2_zip" 'Data/css*.dat' >/dev/null 2>&1; then
    :
else
    echo "No Data/css*.dat entries matched in rct2-content.zip (continuing)."
fi

echo "Stripping OpenRCT2 music objects and music asset packs from assets.zip..."
if zip -q -d "$assets_zip" 'object/official/music/*' >/dev/null 2>&1; then
    :
else
    echo "No object/official/music/* entries matched in assets.zip (continuing)."
fi
if zip -q -d "$assets_zip" 'assetpack/openrct2.music.*.parkap' >/dev/null 2>&1; then
    :
else
    echo "No assetpack/openrct2.music.*.parkap entries matched in assets.zip (continuing)."
fi

(
    cd "$workdir/in"
    # Keep deterministic-ish ordering with sorted file list.
    LC_ALL=C find . -type f | sed 's#^\./##' | sort | zip -q -X "$output_zip" -@
)

input_bytes="$(stat -c%s "$input_zip" 2>/dev/null || stat -f%z "$input_zip")"
output_bytes="$(stat -c%s "$output_zip" 2>/dev/null || stat -f%z "$output_zip")"
delta_bytes="$((input_bytes - output_bytes))"

echo
echo "Done."
echo "Input size : $input_bytes bytes"
echo "Output size: $output_bytes bytes"
echo "Saved      : $delta_bytes bytes"
