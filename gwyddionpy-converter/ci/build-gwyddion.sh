#!/usr/bin/env bash
# Build Gwyddion from its official source tarball (--without-gl), then
# build gwyconvert against that fresh install.
#
# The single "build Gwyddion from source" recipe. Every caller goes through
# it, so continuous integration tests the same Gwyddion that ships.
# Building it here also avoids depending on how a distribution splits its
# Gwyddion packages: on Debian and Ubuntu the file-format plugins live in
# `gwyddion`, not `libgwyddion20-dev`, so a -dev-only install yields a
# converter that runs and reports zero formats.
#
# Inputs (all optional, via environment): GWYDDION_VERSION, WORK_DIR,
# PREFIX, GWYCONVERT_OUT, CC.
#
# Leaves everything under $PREFIX; cleanup is the caller's job. Gwyddion
# compiles its module search path in at build time, so that path is valid
# only while $PREFIX exists. Every caller must therefore run a bundle-*.sh
# afterwards to copy lib/gwyddion/ somewhere permanent.
#
# Upstream releases: https://sourceforge.net/projects/gwyddion/files/gwyddion/
set -euo pipefail

GWYDDION_VERSION="${GWYDDION_VERSION:-2.71}"
WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
PREFIX="${PREFIX:-$WORK_DIR/install}"
GWYCONVERT_OUT="${GWYCONVERT_OUT:-$WORK_DIR/gwyconvert}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERTER_SRC="$SCRIPT_DIR/../gwyconvert.c"

mkdir -p "$WORK_DIR" "$(dirname "$GWYCONVERT_OUT")"

echo "== Downloading Gwyddion $GWYDDION_VERSION source =="
curl -Ls --retry 6 --retry-delay 3 -o "$WORK_DIR/gwyddion.tar.xz" \
  "https://sourceforge.net/projects/gwyddion/files/gwyddion/${GWYDDION_VERSION}/gwyddion-${GWYDDION_VERSION}.tar.xz/download"
tar xf "$WORK_DIR/gwyddion.tar.xz" -C "$WORK_DIR"

# --without-gl drops the OpenGL/GLX/gtkglext dependency outright. gwyconvert
# uses no 3D widgets, and a released binary has to stay minimal and portable.
echo "== Configuring (--without-gl) =="
cd "$WORK_DIR/gwyddion-${GWYDDION_VERSION}"
./configure --prefix="$PREFIX" --without-gl \
  --disable-gtk-doc --disable-desktop-file-update
# nproc is GNU coreutils and absent on macOS; sysctl is the BSD equivalent.
# Fall back to 1 rather than an empty -j (which would be unbounded).
JOBS="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)"
make -j"$JOBS"
make install

echo "== Building gwyconvert against the fresh install =="
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
# -Wl,-rpath is required, not cosmetic. pkg-config's -L affects link time
# only; at run time the loader searches the system paths. On a machine that
# also has Gwyddion installed system-wide, that loads the system copy
# instead of this build and defeats the point of building our own.
#
# Both gcc and clang understand the flag, so one line serves Linux and
# macOS. $CC lets the caller choose the compiler.
"${CC:-gcc}" -O2 -Wall $(pkg-config --cflags gwyddion) -o "$GWYCONVERT_OUT" \
  "$CONVERTER_SRC" $(pkg-config --libs gwyddion) -Wl,-rpath,"$PREFIX/lib"

echo "== Smoke test =="
# A build that lost its plugins still exits 0 and prints an empty list, so
# assert on the format count, not the exit status.
#
# PATH is prepended for Windows, where executables have no rpath and the
# -Wl,-rpath above therefore does nothing. libtool installs the
# dynamic-link libraries (DLLs) to $PREFIX/bin, and without them on PATH
# gwyconvert exits silently — which shows up here as a JSON decode error on
# empty input rather than as "DLL not found".
PATH="$PREFIX/bin:$PATH" "$GWYCONVERT_OUT" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'{len(d)} formats OK')"

echo "Built $GWYCONVERT_OUT"
echo "PREFIX=$PREFIX"
