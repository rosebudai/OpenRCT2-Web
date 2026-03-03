FROM fedora:42

# Install build dependencies
RUN dnf update -y && dnf install -y \
    autoconf \
    automake \
    bzip2-devel \
    ccache \
    cmake \
    git \
    json-devel \
    libicu-devel \
    libtool \
    libzip-devel \
    ninja-build \
    pkg-config \
    python3 \
    zip \
    && dnf clean all

# Install Emscripten SDK
WORKDIR /
RUN git clone https://github.com/emscripten-core/emsdk.git
WORKDIR /emsdk/
RUN ./emsdk install 5.0.0
RUN ./emsdk activate 5.0.0
ENV PATH="/emsdk:/emsdk/upstream/emscripten:/emsdk/node/22.16.0_64bit/bin:${PATH}"

# Copy nlohmann headers where the build expects them
RUN cp -r /usr/include/nlohmann /emsdk/upstream/emscripten/cache/sysroot/include/

# Copy pre-cloned dependency sources and build script
WORKDIR /ext/
COPY ext/ /ext/
COPY build-depends.sh /ext/
RUN bash build-depends.sh

ENV SPEEXDSP_ROOT=/ext/speexdsp
ENV ICU_ROOT=/ext/icu/icu4c/source
ENV LIBZIP_ROOT=/ext/libzip/build

SHELL ["/bin/bash", "-c"]
