#!/bin/bash
# Pre-clone dependency sources for the Docker build.
# Run this once before building the Docker image.
# Sources are cached in docker/emscripten/ext/ and COPYed into the image.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXT_DIR="$SCRIPT_DIR/ext"

mkdir -p "$EXT_DIR"
cd "$EXT_DIR"

clone_if_missing() {
    local name="$1"
    local url="$2"
    local branch="$3"
    if [ ! -d "$name" ]; then
        echo "Cloning $name ($branch)..."
        git clone "$url" --depth 1 --branch "$branch" "$name"
    else
        echo "Already have $name, skipping"
    fi
}

clone_if_missing speexdsp https://gitlab.xiph.org/xiph/speexdsp.git SpeexDSP-1.2.1
clone_if_missing icu      https://github.com/unicode-org/icu.git    release-77-1
clone_if_missing libzip   https://github.com/nih-at/libzip.git      v1.11.4
clone_if_missing zlib     https://github.com/madler/zlib.git        v1.3.1
clone_if_missing zstd     https://github.com/facebook/zstd.git      v1.5.7

echo "All dependencies cloned to $EXT_DIR"
