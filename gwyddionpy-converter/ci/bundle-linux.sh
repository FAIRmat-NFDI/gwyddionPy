#!/usr/bin/env bash
# Turn a freshly built gwyconvert plus its Gwyddion install prefix into a
# self-contained, relocatable bundle directory. macOS and Windows have their
# own counterparts: bundle-macos.sh, bundle-windows.sh.
#
# One recipe, two callers. Keep it that way; two copies would drift.
#   - build-linux.sh           -> bundle to a temp dir, tar it as the
#                                 GitHub Release asset.
#   - cibw-before-all-linux.sh -> bundle straight into the wheel's package
#                                 data.
#
# Inputs (all required, via environment):
#   PREFIX            Gwyddion install prefix from build-gwyddion.sh
#   BUILT_GWYCONVERT  the gwyconvert executable just built against it
#   BUNDLE_DIR        destination; ends up holding `gwyconvert` (a wrapper
#                     script) and `lib/`.
#                     gwyddionpy_converter.binary_path() looks for that
#                     wrapper name.
#
# Bundling policy: ship everything gwyconvert loads at run time except the
# C library itself (libc, libm, libpthread, libdl, librt and the dynamic
# linker). Those are tied to the host and must never travel in a
# redistributable bundle; pinning a baseline instead is the point of
# manylinux. Everything else errs toward bundling more, including the X11
# client libraries, so the converter also works in minimal container images.
set -euo pipefail

: "${PREFIX:?PREFIX must be set (Gwyddion install prefix)}"
: "${BUILT_GWYCONVERT:?BUILT_GWYCONVERT must be set (path to the built binary)}"
: "${BUNDLE_DIR:?BUNDLE_DIR must be set (bundle destination directory)}"

echo "== Bundling runtime dependencies into $BUNDLE_DIR =="
# Layout: gwyconvert (wrapper script), lib/gwyconvert.real (the binary),
# lib/*.so (its bundled dependencies) and lib/gwyddion/ (Gwyddion's own
# file-format plugins). The binary's library search path is set to $ORIGIN,
# its own directory, so everything in lib/ resolves wherever the bundle
# ends up.
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/lib"
cp "$BUILT_GWYCONVERT" "$BUNDLE_DIR/lib/gwyconvert.real"

# gwyconvert finds its format plugins through Gwyddion's
# gwy_find_self_dir(), which returns a path compiled into libgwyddion at
# Gwyddion's own build time — here $PREFIX/lib, a temporary directory that
# will not exist on a user's machine — unless GWYDDION_LIBDIR overrides it.
# So the plugins are copied out here and the wrapper below points
# GWYDDION_LIBDIR at the copy. Skip either and gwyconvert exits 0 while
# reporting zero formats.
cp -r "$PREFIX/lib/gwyddion" "$BUNDLE_DIR/lib/gwyddion"

# The C library's own pieces: never bundled, per the policy note above.
EXCLUDE_RE='^(linux-vdso\.so|ld-linux|libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|libresolv\.so|libnsl\.so|libutil\.so)'

# Walk the executable and every loadable module. The modules pull in
# libraries that appear in no other file's dependency list — libxml2, for
# the anasys_xml, spml and zyvex parsers. Miss them and those formats vanish
# from --list-formats on any machine lacking the library, which is invisible
# on the build machine where system packages fill the gap.
#
# LD_LIBRARY_PATH lets ldd resolve the modules against the fresh build: the
# executable has an explicit search path, the modules do not.
{
  ldd "$BUILT_GWYCONVERT"
  find "$PREFIX/lib/gwyddion/modules" -name '*.so' \
    -exec env LD_LIBRARY_PATH="$PREFIX/lib" ldd {} \;
} | awk '$2 == "=>" {print $1, $3}' | sort -u | while read -r name path; do
  [[ -z "$path" ]] && continue          # the kernel vdso and the loader: no file
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
# Needed for the loadable modules' own dependencies, such as libxml2. An
# executable's library search path does not apply to libraries required by
# a module it loads at run time, so without this only libraries already in
# the process (the core Gwyddion and GTK ones) would resolve.
export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Keep stderr for real diagnostics. Otherwise GTK loads its accessibility
# modules and GdkPixbuf hunts for a loader cache at a path baked in by the
# build container, warning on every run including successful ones. Neither
# is needed: gwyconvert draws nothing and the bundle ships no pixmap
# module. Clearing both leaves the format list and every conversion
# unchanged.
export GTK_MODULES=""
export GDK_PIXBUF_MODULE_FILE=/dev/null
exec "$here/lib/gwyconvert.real" "$@"
WRAPPER
chmod +x "$BUNDLE_DIR/gwyconvert"

echo "== Verifying the bundle is actually self-contained (env cleared) =="
# `env -i` matters: it strips LD_LIBRARY_PATH and GWYDDION_LIBDIR, so the
# check exercises what a user gets rather than what the builder has set.
env -i "$BUNDLE_DIR/gwyconvert" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"
