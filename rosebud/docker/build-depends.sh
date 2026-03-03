#!/bin/bash
set -euo pipefail

START_DIR=/ext

cd $START_DIR

# Sources are expected to be pre-populated via COPY in the Dockerfile.
# Run clone-deps.sh locally first to populate docker/emscripten/ext/.

cd speexdsp
emmake ./autogen.sh
emmake ./configure --enable-shared --disable-neon
emmake make -j$(nproc)
cd $START_DIR

cd icu/icu4c/source
ac_cv_namespace_ok=yes icu_cv_host_frag=mh-linux emmake ./configure \
    --enable-release \
    --enable-shared \
    --disable-icu-config \
    --disable-extras \
    --disable-icuio \
    --disable-layoutex \
    --disable-tools \
    --disable-tests \
    --disable-samples
emmake make -j$(nproc)
cd $START_DIR

cd zlib
mkdir -p build/
cd build/
emcmake cmake ../
emmake make zlib -j$(nproc)
emmake make install
ZLIB_ROOT=$(pwd)
cd $START_DIR

cd libzip
mkdir -p build/
cd build/
emcmake cmake ../ -DZLIB_INCLUDE_DIR="$ZLIB_ROOT" -DZLIB_LIBRARY="$ZLIB_ROOT/libz.a"
emmake make zip -j$(nproc)
emmake make install
cd $START_DIR

cd zstd
mkdir -p build/build/
cd build/build/
emcmake cmake ../cmake/ -DZSTD_BUILD_STATIC=ON -DZSTD_BUILD_SHARED=OFF -DZSTD_BUILD_PROGRAMS=OFF
emmake make -j$(nproc)
emmake make install
cd $START_DIR
