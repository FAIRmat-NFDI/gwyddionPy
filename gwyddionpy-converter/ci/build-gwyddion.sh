#!/usr/bin/env bash
# Build Gwyddion from its official SourceForge source tarball
# (--without-gl) and then build gwyconvert against it.
#
# Shared by build-linux.sh (produces the portable release tarball) and
# pytest.yml (just needs a working gwyconvert to test against) — there is
# exactly one "build Gwyddion from source" recipe, not two that can
# silently drift apart. That drift is exactly what bit this project twice
# (V1_IMPLEMENTATION.md, 2026-07-22): pytest.yml used to apt-install
# libgwyddion20-dev instead, which turned out to depend only on the
# runtime .so's, not the `gwyddion` package that actually owns the
# file-format module plugins — a gap invisible on a dev machine that
# happened to have `gwyddion` installed already, but real on a fresh CI
# runner. Building from source ourselves removes that whole class of
# "guess which Debian package split owns what" risk, for both callers.
#
# Leaves everything in place under $PREFIX — no cleanup here, that's the
# caller's job (see build-linux.sh's trap). The compiled-in module search
# path only stays valid for as long as $PREFIX exists, which is exactly
# why build-linux.sh has to bundle lib/gwyddion/ separately once this
# script's own work dir eventually gets deleted.
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
# -Wl,-rpath is required, not cosmetic: pkg-config's -L flag only affects
# *link-time* resolution. Without an RPATH, the *runtime* loader resolves
# each dependency by soname via the standard system search path — and if
# a same-soname Gwyddion happens to also be installed system-wide (as on
# a machine that's also done the system-package build), it silently picks
# that one up instead, defeating the entire point of building our own.
# Caught by hand (V1_IMPLEMENTATION.md 2026-07-22) via `ldd`: without this
# flag the resulting binary reported the *system* package's format count,
# not this build's, despite having linked successfully against ours.
# -Wl,-rpath is a GNU ld / ld64 flag understood by both gcc and clang, so the
# same line serves Linux and macOS. $CC lets the caller pick the compiler
# (macOS resolves `gcc` to clang, which is fine, but being explicit avoids
# surprises if a real gcc is also on PATH via Homebrew).
"${CC:-gcc}" -O2 -Wall $(pkg-config --cflags gwyddion) -o "$GWYCONVERT_OUT" \
  "$CONVERTER_SRC" $(pkg-config --libs gwyddion) -Wl,-rpath,"$PREFIX/lib"

echo "== Smoke test =="
"$GWYCONVERT_OUT" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'{len(d)} formats OK')"

echo "Built $GWYCONVERT_OUT"
echo "PREFIX=$PREFIX"
