#!/usr/bin/env bash
# Build a self-contained, releasable gwyconvert for linux-x86_64.
#
# Deliberately NOT the system package build (the system libgwyddion20-dev
# package, docs/BUILD.md) even though that's what pytest.yml uses to run
# the test suite. This builds Gwyddion itself from its official
# SourceForge release tarball with --without-gl, which drops the
# OpenGL/GLX/gtkglext dependency
# entirely (verified 2026-07-21 by hand — see V1_IMPLEMENTATION.md for the
# full investigation: the system package's gwyddion.pc Requires gtkglext,
# the tarball build's doesn't, and a real conversion of a Bruker sample
# file through gwyddionpy.load() produces identical output either way).
# That matters here specifically because a *released* binary needs to be
# minimal and portable; the local dev/test converter does not.
#
# Produces $OUT_DIR/gwyconvert-linux-x86_64.tar.gz + a matching .sha256,
# self-contained via a bundled lib/ dir and patchelf-rewritten RPATHs.
#
# Bundling policy: bundle everything gwyconvert links against at runtime
# EXCEPT glibc itself (libc/libm/libpthread/libdl/librt/the dynamic linker)
# — glibc must never travel in a redistributable bundle, it's tied to the
# host by design (that's the entire reason manylinux pins a baseline
# instead of bundling it). Deliberately erring toward bundling *more* of
# everything else (the X11 client library family included) rather than
# less: the point of a "headless converter" is to also work inside minimal
# server/container images that won't have any of this preinstalled.
set -euo pipefail

GWYDDION_VERSION="${GWYDDION_VERSION:-2.71}"
OUT_DIR="${OUT_DIR:-$PWD/dist-converter}"
ASSET_NAME="gwyconvert-linux-x86_64.tar.gz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERTER_SRC="$SCRIPT_DIR/../gwyconvert.c"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
PREFIX="$WORK_DIR/install"

echo "== Downloading Gwyddion $GWYDDION_VERSION source =="
curl -Ls --retry 6 --retry-delay 3 -o "$WORK_DIR/gwyddion.tar.xz" \
  "https://sourceforge.net/projects/gwyddion/files/gwyddion/${GWYDDION_VERSION}/gwyddion-${GWYDDION_VERSION}.tar.xz/download"
tar xf "$WORK_DIR/gwyddion.tar.xz" -C "$WORK_DIR"

echo "== Configuring (--without-gl) =="
cd "$WORK_DIR/gwyddion-${GWYDDION_VERSION}"
./configure --prefix="$PREFIX" --without-gl \
  --disable-gtk-doc --disable-desktop-file-update
make -j"$(nproc)"
make install

echo "== Building gwyconvert against the fresh install =="
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
BUILD_DIR="$WORK_DIR/converter-build"
mkdir -p "$BUILD_DIR"
gcc -O2 -Wall $(pkg-config --cflags gwyddion) -o "$BUILD_DIR/gwyconvert" \
  "$CONVERTER_SRC" $(pkg-config --libs gwyddion)

echo "== Smoke test (unbundled) =="
"$BUILD_DIR/gwyconvert" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'{len(d)} formats OK')"

echo "== Bundling runtime dependencies =="
# Layout: gwyconvert (wrapper script) + lib/gwyconvert.real (the ELF) +
# lib/*.so (bundled runtime deps, siblings of the ELF) + lib/gwyddion/
# (Gwyddion's own file-format module plugins). The ELF's RPATH is $ORIGIN,
# which now resolves correctly since everything lives in the same lib/ dir.
BUNDLE_DIR="$BUILD_DIR/bundle"
mkdir -p "$BUNDLE_DIR/lib"
cp "$BUILD_DIR/gwyconvert" "$BUNDLE_DIR/lib/gwyconvert.real"

# gwyconvert.c finds its format-parser plugins via gwy_find_self_dir(),
# which on Unix uses a path *compiled into libgwyddion at Gwyddion's own
# build time* (or the GWYDDION_LIBDIR env var, which overrides it — see
# gwy_find_self_dir() in libgwyddion/gwyutils.c). That compiled-in path is
# $PREFIX/lib, i.e. this script's own temporary build directory — which
# won't exist once this script's trap deletes $WORK_DIR, let alone on
# whoever downloads this tarball. Confirmed by hand (V1_IMPLEMENTATION.md):
# without bundling this directory and pointing GWYDDION_LIBDIR at it,
# gwyconvert runs fine (exit 0) and silently reports zero formats — the
# "broken build could still exit 0" case test_run.py's
# test_list_formats_reports_known_formats exists to catch.
cp -r "$PREFIX/lib/gwyddion" "$BUNDLE_DIR/lib/gwyddion"

# glibc's own pieces: never bundle these (see policy note above).
EXCLUDE_RE='^(linux-vdso\.so|ld-linux|libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|libresolv\.so|libnsl\.so|libutil\.so)'

ldd "$BUILD_DIR/gwyconvert" | awk '{print $1, $3}' | while read -r name path; do
  [[ -z "$path" ]] && continue          # vdso / the dynamic linker itself: no real file
  [[ "$name" =~ $EXCLUDE_RE ]] && continue
  cp -n "$path" "$BUNDLE_DIR/lib/"
done

patchelf --set-rpath '$ORIGIN' "$BUNDLE_DIR/lib/gwyconvert.real"
for lib in "$BUNDLE_DIR"/lib/*.so*; do
  patchelf --set-rpath '$ORIGIN' "$lib"
done

cat > "$BUNDLE_DIR/gwyconvert" <<'WRAPPER'
#!/bin/sh
# Sets GWYDDION_LIBDIR so gwyconvert.real finds the bundled modules in
# lib/gwyddion/modules/file/ instead of the (nonexistent, post-extraction)
# path compiled in at CI build time. See build-linux.sh for the full story.
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export GWYDDION_LIBDIR="$here/lib"
exec "$here/lib/gwyconvert.real" "$@"
WRAPPER
chmod +x "$BUNDLE_DIR/gwyconvert"

echo "== Verifying the bundle is actually self-contained (env cleared) =="
env -i "$BUNDLE_DIR/gwyconvert" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"

echo "== Packaging =="
mkdir -p "$OUT_DIR"
tar czf "$OUT_DIR/$ASSET_NAME" -C "$BUNDLE_DIR" gwyconvert lib
(cd "$OUT_DIR" && sha256sum "$ASSET_NAME") > "$OUT_DIR/$ASSET_NAME.sha256"
cp "$SCRIPT_DIR/../COPYING" "$OUT_DIR/COPYING" 2>/dev/null || true

echo "Wrote $OUT_DIR/$ASSET_NAME"
