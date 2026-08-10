#!/usr/bin/env bash
# macOS counterpart of bundle-linux.sh: turn a freshly-built gwyconvert plus
# its Gwyddion install prefix into a self-contained, relocatable bundle.
#
# Inputs (all required, via environment):
#   PREFIX            Gwyddion install prefix from build-gwyddion.sh
#   BUILT_GWYCONVERT  path to the gwyconvert binary just built against it
#   BUNDLE_DIR        destination; ends up holding `gwyconvert` and `lib/`.
#                     gwyddionpy_converter.binary_path() expects that name.
#
# Not a mechanical translation of the Linux script. Three things genuinely
# differ, and getting any of them wrong yields a bundle that works on the
# build machine and fails everywhere else.
#
# 1. `otool -L` lists direct dependencies only, where `ldd` gives the full
#    transitive closure, so this script walks the graph itself. A one-pass
#    copy would miss every second-level library.
# 2. There is no library-path escape hatch. System Integrity Protection
#    (SIP) strips DYLD_* variables when a protected binary spawns a child,
#    and /bin/sh, which runs the wrapper, is one. Every reference is
#    rewritten to @loader_path instead, which is what `delocate` does.
#    https://developer.apple.com/library/archive/documentation/Security/Conceptual/System_Integrity_Protection_Guide/RuntimeProtections/RuntimeProtections.html
# 3. Editing a binary invalidates its code signature, after which macOS
#    refuses to load it — a hard failure on Apple Silicon. Every file
#    rewritten here must be re-signed.
#
# Bundling policy mirrors Linux: ship everything except the operating
# system's own libraries, which on macOS means anything under /usr/lib or
# /System/Library. Homebrew's trees are what must travel.
set -euo pipefail

: "${PREFIX:?PREFIX must be set (Gwyddion install prefix)}"
: "${BUILT_GWYCONVERT:?BUILT_GWYCONVERT must be set (path to the built binary)}"
: "${BUNDLE_DIR:?BUNDLE_DIR must be set (bundle destination directory)}"

LIB_DIR="$BUNDLE_DIR/lib"

echo "== Laying out the bundle at $BUNDLE_DIR =="
rm -rf "$BUNDLE_DIR"
mkdir -p "$LIB_DIR"
cp "$BUILT_GWYCONVERT" "$LIB_DIR/gwyconvert.real"
# Gwyddion's loadable format plugins, for the same reason as on Linux: they
# are found through a path compiled into libgwyddion at its own build time,
# pointing at a temporary directory no user will have.
cp -R "$PREFIX/lib/gwyddion" "$LIB_DIR/gwyddion"

# System libraries: present on every macOS, never bundled.
is_system_lib() {
  case "$1" in
    /usr/lib/*|/System/Library/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Direct dependencies of one binary, as absolute paths. Skips otool's first
# line (the filename), the file's own identity entry, and anything already
# expressed relative to the loader.
direct_deps() {
  otool -L "$1" | tail -n +2 | awk '{print $1}' | while read -r dep; do
    case "$dep" in
      @*|"") continue ;;
    esac
    [ "$dep" = "$1" ] && continue
    printf '%s\n' "$dep"
  done
}

echo "== Resolving the transitive dependency closure =="
# Worklist over every binary shipped: the executable plus every loadable
# module. The modules matter for the same reason as on Linux — their own
# dependencies, such as libxml2 for the anasys_xml, spml and zyvex parsers,
# appear in no other file's dependency list.
WORK="$(mktemp)"; SEEN="$(mktemp)"; trap 'rm -f "$WORK" "$SEEN"' EXIT
{
  printf '%s\n' "$LIB_DIR/gwyconvert.real"
  find "$LIB_DIR/gwyddion" -type f \( -name '*.so' -o -name '*.dylib' \) 2>/dev/null || true
} > "$WORK"

while [ -s "$WORK" ]; do
  current="$(head -n 1 "$WORK")"
  sed -i.bak '1d' "$WORK" && rm -f "$WORK.bak"
  [ -f "$current" ] || continue
  direct_deps "$current" | while read -r dep; do
    is_system_lib "$dep" && continue
    base="$(basename "$dep")"
    if ! grep -qxF "$base" "$SEEN" 2>/dev/null; then
      printf '%s\n' "$base" >> "$SEEN"
      if [ -f "$dep" ]; then
        cp -f "$dep" "$LIB_DIR/$base"
        chmod u+w "$LIB_DIR/$base"
        # Newly copied library may itself pull in more: queue it.
        printf '%s\n' "$LIB_DIR/$base" >> "$WORK"
      else
        echo "warning: dependency not found on disk, skipping: $dep" >&2
      fi
    fi
  done
done
echo "bundled $(find "$LIB_DIR" -maxdepth 1 -name '*.dylib' | wc -l | tr -d ' ') libraries"

echo "== Rewriting install names to @loader_path =="
# For a binary at <dir>, the bundle's lib/ is reached by going up as many
# levels as <dir> is below it. lib/gwyconvert.real -> "." ;
# lib/gwyddion/modules/file/x.so -> "../../..".
rel_to_lib() {
  local dir rel
  dir="$(cd "$(dirname "$1")" && pwd)"
  rel="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$LIB_DIR" "$dir")"
  printf '%s' "$rel"
}

find "$LIB_DIR" -type f \( -name '*.dylib' -o -name '*.so' -o -name 'gwyconvert.real' \) |
while read -r macho; do
  chmod u+w "$macho"
  rel="$(rel_to_lib "$macho")"
  prefix="@loader_path"
  [ "$rel" != "." ] && prefix="@loader_path/$rel"

  # A library's own install name is what dependents record, so point it at
  # the bundle and anything linking it later resolves inside the bundle too.
  case "$macho" in
    *.dylib) install_name_tool -id "$prefix/$(basename "$macho")" "$macho" 2>/dev/null || true ;;
  esac

  direct_deps "$macho" | while read -r dep; do
    is_system_lib "$dep" && continue
    base="$(basename "$dep")"
    # Rewrite only references to things actually bundled. Anything else
    # keeps pointing where it did, so a missing rewrite fails loudly at
    # load time rather than quietly resolving to a host copy.
    [ -f "$LIB_DIR/$base" ] || continue
    install_name_tool -change "$dep" "$prefix/$base" "$macho" 2>/dev/null || true
  done

  # Re-sign: the edits above invalidate the existing signature, and macOS
  # refuses to load an invalidly signed binary — a hard failure on arm64.
  # An ad-hoc signature (`-`) is enough outside the App Store.
  codesign --force --sign - --timestamp=none "$macho" 2>/dev/null || true
done

cat > "$BUNDLE_DIR/gwyconvert" <<'WRAPPER'
#!/bin/sh
# Sets GWYDDION_LIBDIR so gwyconvert.real finds the bundled format modules
# instead of the nonexistent path compiled in at build time.
#
# Deliberately does not export DYLD_LIBRARY_PATH: System Integrity
# Protection strips DYLD_* variables when a protected binary spawns a child,
# so it would be dropped. The @loader_path install names that
# bundle-macos.sh rewrote handle library resolution instead.
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export GWYDDION_LIBDIR="$here/lib"
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

echo "== Verifying the bundle is self-contained (env cleared) =="
env -i "$BUNDLE_DIR/gwyconvert" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"

echo "== Checking no bundled file still points outside the bundle =="
# A surviving reference to /opt/homebrew, /usr/local or the build PREFIX
# means the rewrite missed something. It would work here and fail on every
# user's machine, so fail the build rather than ship it.
#
# Results go to a file, not a shell variable: the `while` below is the
# right-hand side of a pipe and runs in a subshell, where an assignment
# would be discarded and the check would always pass.
LEAKS="$(mktemp)"
find "$LIB_DIR" -type f \( -name '*.dylib' -o -name '*.so' -o -name 'gwyconvert.real' \) |
while read -r macho; do
  direct_deps "$macho" | grep -E "^(/opt/homebrew|/usr/local|$PREFIX)" |
    sed "s|^|$macho -> |" >> "$LEAKS" || true
done

if [ -s "$LEAKS" ]; then
  echo "LEAK: bundled files still reference build-machine paths:" >&2
  cat "$LEAKS" >&2
  rm -f "$LEAKS"
  exit 1
fi
rm -f "$LEAKS"
echo "no build-machine paths leaked into the bundle"
