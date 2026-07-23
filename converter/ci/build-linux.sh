#!/usr/bin/env bash
# Build a self-contained, releasable gwyconvert for linux-x86_64.
#
# Calls build-gwyddion.sh for the actual "build Gwyddion from source, then
# gwyconvert" work (shared with pytest.yml — see that script's header for
# why), then bundles the result into a portable tarball. This bundling
# step is what's specific to this script: `--without-gl` (in
# build-gwyddion.sh) drops the OpenGL/GLX/gtkglext dependency entirely
# (verified 2026-07-21 by hand — see V1_IMPLEMENTATION.md: the system
# package's gwyddion.pc Requires gtkglext, the tarball build's doesn't,
# and a real conversion of a Bruker sample file through
# gwyddionpy.load() produces identical output either way), which matters
# specifically here because a *released* binary needs to be minimal and
# portable, not just working in-place.
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

OUT_DIR="${OUT_DIR:-$PWD/dist-converter}"
ASSET_NAME="gwyconvert-linux-x86_64.tar.gz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
export WORK_DIR
PREFIX="$WORK_DIR/install"
export PREFIX
BUILT_GWYCONVERT="$WORK_DIR/gwyconvert"
export GWYCONVERT_OUT="$BUILT_GWYCONVERT"

"$SCRIPT_DIR/build-gwyddion.sh"

echo "== Bundling runtime dependencies =="
# Layout: gwyconvert (wrapper script) + lib/gwyconvert.real (the ELF) +
# lib/*.so (bundled runtime deps, siblings of the ELF) + lib/gwyddion/
# (Gwyddion's own file-format module plugins). The ELF's RPATH is $ORIGIN,
# which now resolves correctly since everything lives in the same lib/ dir.
BUNDLE_DIR="$WORK_DIR/bundle"
mkdir -p "$BUNDLE_DIR/lib"
cp "$BUILT_GWYCONVERT" "$BUNDLE_DIR/lib/gwyconvert.real"

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

# ldd the executable AND every dlopen()-loaded module: the modules have
# their own NEEDED libraries that never appear in the executable's ldd
# output (e.g. libxml2 for the anasys_xml/spml/zyvex parsers). Confirmed
# by hand (2026-07-22): without this, those formats silently vanish from
# --list-formats on any target lacking the library — the builder itself
# masked the gap because its dnf/apt-installed system libs filled in.
# LD_LIBRARY_PATH makes the modules' deps on the fresh Gwyddion build
# resolvable during ldd (the executable got an explicit RPATH; the
# libtool-built modules' install RPATH is not guaranteed).
{
  ldd "$BUILT_GWYCONVERT"
  find "$PREFIX/lib/gwyddion/modules" -name '*.so' \
    -exec env LD_LIBRARY_PATH="$PREFIX/lib" ldd {} \;
} | awk '$2 == "=>" {print $1, $3}' | sort -u | while read -r name path; do
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
# Required for the dlopen()-loaded modules' OWN dependencies (libxml2 &
# co.): an executable's RUNPATH does not apply to libraries needed by a
# dlopen()'d object, so without this only deps that happen to be already
# loaded into the process (the core Gwyddion/GTK libs) would resolve.
export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
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
