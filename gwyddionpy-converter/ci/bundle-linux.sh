#!/usr/bin/env bash
# Turn a freshly-built gwyconvert + its Gwyddion install prefix into a
# self-contained, relocatable bundle directory.
#
# Extracted from build-linux.sh (2026-07-29, V1d-2) so there is exactly one
# bundling recipe with two callers, the same way build-gwyddion.sh is one
# build recipe with two callers:
#   - build-linux.sh          -> bundles into a temp dir, then tars it up as
#                                the GitHub Release asset _fetch_converter.py
#                                downloads.
#   - cibw-before-all-linux.sh -> bundles straight into the wheel's package
#                                data directory.
# Splitting these apart matters because the bundling logic is where four of
# this project's bugs have lived (V1_IMPLEMENTATION.md: the missing modules
# dir, the dlopen'd modules' own deps, the missing RPATH, the glibc floor).
# Two copies of it would eventually disagree.
#
# Inputs (all required, via environment):
#   PREFIX            Gwyddion install prefix from build-gwyddion.sh
#   BUILT_GWYCONVERT  path to the gwyconvert ELF just built against it
#   BUNDLE_DIR        destination; created if absent, must end up holding
#                     `gwyconvert` (wrapper) + `lib/`
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

: "${PREFIX:?PREFIX must be set (Gwyddion install prefix)}"
: "${BUILT_GWYCONVERT:?BUILT_GWYCONVERT must be set (path to the built ELF)}"
: "${BUNDLE_DIR:?BUNDLE_DIR must be set (bundle destination directory)}"

echo "== Bundling runtime dependencies into $BUNDLE_DIR =="
# Layout: gwyconvert (wrapper script) + lib/gwyconvert.real (the ELF) +
# lib/*.so (bundled runtime deps, siblings of the ELF) + lib/gwyddion/
# (Gwyddion's own file-format module plugins). The ELF's RPATH is $ORIGIN,
# which resolves correctly since everything lives in the same lib/ dir.
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/lib"
cp "$BUILT_GWYCONVERT" "$BUNDLE_DIR/lib/gwyconvert.real"

# gwyconvert.c finds its format-parser plugins via gwy_find_self_dir(),
# which on Unix uses a path *compiled into libgwyddion at Gwyddion's own
# build time* (or the GWYDDION_LIBDIR env var, which overrides it — see
# gwy_find_self_dir() in libgwyddion/gwyutils.c). That compiled-in path is
# $PREFIX/lib, i.e. a temporary build directory — which won't exist on
# whoever installs this. Confirmed by hand (V1_IMPLEMENTATION.md):
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
# path compiled in at CI build time. See bundle-linux.sh for the full story.
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
# `env -i` matters: it strips LD_LIBRARY_PATH/GWYDDION_LIBDIR so the check
# exercises what an end user gets, not what the builder happens to have set.
env -i "$BUNDLE_DIR/gwyconvert" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"
