#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
host_pwd="$(pwd -P)"
container_wd="/workspaces/OpenRCT2"
cli_host_path="$repo_root/build-native/openrct2-cli"

if [[ ! -x "$cli_host_path" ]]; then
    cat >&2 <<EOF
Missing required CLI binary:
  $cli_host_path

Build it first with:
  docker run --rm -v "$repo_root:/workspaces/OpenRCT2" -w /workspaces/OpenRCT2 openrct2/openrct2-build:25-noble bash -lc 'cmake -S . -B build-native -G Ninja -DDISABLE_DISCORD_RPC=ON -DDOWNLOAD_TITLE_SEQUENCES=OFF -DDOWNLOAD_OBJECTS=OFF -DDOWNLOAD_OPENSFX=OFF -DDOWNLOAD_OPENMUSIC=OFF -DDOWNLOAD_REPLAYS=OFF -DDISABLE_GOOGLE_BENCHMARK=ON -DWITH_TESTS=OFF && cmake --build build-native -j4 --target openrct2-cli'
EOF
    exit 1
fi

if [[ "$host_pwd" == "$repo_root" ]]; then
    container_wd="/workspaces/OpenRCT2"
elif [[ "$host_pwd" == "$repo_root/"* ]]; then
    rel="${host_pwd#"$repo_root"}"
    container_wd="/workspaces/OpenRCT2$rel"
fi

exec docker run --rm \
    --platform linux/amd64 \
    -v "$repo_root:/workspaces/OpenRCT2" \
    -w "$container_wd" \
    openrct2/openrct2-build:25-noble \
    /workspaces/OpenRCT2/build-native/openrct2-cli "$@"
