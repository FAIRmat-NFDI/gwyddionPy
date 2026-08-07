#!/usr/bin/env bash
# Turn a freshly-built gwyconvert plus its Gwyddion install prefix into a
# self-contained, relocatable bundle directory. (macOS and Windows have
# their own counterparts: bundle-macos.sh, bundle-windows.sh.)
#
# One recipe, two callers — keep it that way, two copies would drift:
#   - build-linux.sh           -> bundle to a temp dir, tar it as the
#                                 GitHub Release asset.
#   - cibw-before-all-linux.sh -> bundle straight into the wheel's package
#                                 data.
#
# Inputs (all required, via environment):
#   PREFIX            Gwyddion install prefix from build-gwyddion.sh
#   BUILT_GWYCONVERT  the gwyconvert ELF just built against it
#   BUNDLE_DIR        destination; ends up holding `gwyconvert` (wrapper)
#                     + `lib/`. gwyddionpy_converter.binary_path() looks
#                     for that wrapper name.
#
# Bundling policy: ship everything gwyconvert loads at run time EXCEPT
# glibc (libc/libm/libpthread/libdl/librt and the dynamic linker). glibc is
# tied to the host by design and must never travel in a redistributable
# bundle — pinning a baseline instead of bundling it is the whole point of
# manylinux. Everything else errs toward bundling MORE (the X11 client
# libraries included), because a headless converter should also work inside
# minimal server and container images.
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

# gwyconvert.c locates its format-parser plugins through
# gwy_find_self_dir(), which on Unix returns a path compiled into
# libgwyddion at Gwyddion's build time — here $PREFIX/lib, a temporary
# directory that will not exist on a user's machine — unless the
# GWYDDION_LIBDIR environment variable overrides it (see
# libgwyddion/gwyutils.c upstream). So the plugins must be copied out, and
# the wrapper below must point GWYDDION_LIBDIR at the copy. Skip either and
# gwyconvert exits 0 while reporting zero formats.
cp -r "$PREFIX/lib/gwyddion" "$BUNDLE_DIR/lib/gwyddion"

# glibc's own pieces: never bundle these (see policy note above).
EXCLUDE_RE='^(linux-vdso\.so|ld-linux|libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|libresolv\.so|libnsl\.so|libutil\.so)'

# ldd the executable AND every dlopen()'d module. The modules have their
# own NEEDED libraries that appear in no other file's ldd output (libxml2,
# for the anasys_xml/spml/zyvex parsers). Miss them and those formats
# vanish from --list-formats on any machine lacking the library — invisible
# on the build machine, whose system packages fill the gap.
# LD_LIBRARY_PATH lets ldd resolve the modules' deps against the fresh
# build: the executable has an explicit RPATH, the libtool-built modules
# do not necessarily.
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
# Points GWYDDION_LIBDIR at the bundled modules, replacing the build-time
# path compiled into libgwyddion. See bundle-linux.sh for the full story.
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export GWYDDION_LIBDIR="$here/lib"
# Needed for the dlopen()'d modules' OWN dependencies (libxml2 and co.):
# an executable's RUNPATH does not apply to libraries required by a
# dlopen()'d object, so without this only libraries already loaded into the
# process (the core Gwyddion/GTK ones) would resolve.
export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Keep stderr for real diagnostics. GTK otherwise tries to load the
# accessibility modules (gail, atk-bridge) and GdkPixbuf looks for a loader
# cache at the path baked in by the build container, which exists on no
# user's machine — three warnings on every run, successful ones included,
# ending in advice to run a command as root that would not help. None of it
# is needed: gwyconvert draws nothing and the bundle ships no pixmap module.
# Verified that clearing both leaves the format list and every conversion
# unchanged.
export GTK_MODULES=""
export GDK_PIXBUF_MODULE_FILE=/dev/null
exec "$here/lib/gwyconvert.real" "$@"
WRAPPER
chmod +x "$BUNDLE_DIR/gwyconvert"

echo "== Verifying the bundle is actually self-contained (env cleared) =="
# `env -i` matters: it strips LD_LIBRARY_PATH/GWYDDION_LIBDIR so the check
# exercises what an end user gets, not what the builder happens to have set.
env -i "$BUNDLE_DIR/gwyconvert" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"
