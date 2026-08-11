#!/usr/bin/env bash
# Windows counterpart of bundle-linux.sh / bundle-macos.sh. Runs under an
# MSYS2 MinGW64 shell (see build-windows-bundle.sh), NOT cmd/PowerShell.
#
# Inputs (all required, via environment):
#   PREFIX            Gwyddion install prefix from build-gwyddion.sh
#   BUILT_GWYCONVERT  path to the gwyconvert PE just built (with or without
#                     the .exe suffix — MinGW gcc appends it)
#   BUNDLE_DIR        the wheel's bin/ package-data dir; receives
#                     gwyconvert.exe + *.dll. Modules land in ../lib — see
#                     the layout note, the location is load-bearing.
#
# On Windows relocation is trivial and discovery is the whole job:
#   - There is no RPATH or install-name machinery, and the loader searches
#     the executable's own directory first, so DLLs placed beside the .exe
#     simply work. Nothing is patched, so nothing needs re-signing.
#   - Dependencies are found by walking each PE's import table with
#     objdump -p, recursively (collect_deps below). System DLLs drop out on
#     their own: they never resolve under BUNDLE_DIR, PREFIX/bin or
#     /mingw64/bin, so only MinGW64-toolchain DLLs travel.
#   - As on the other platforms the dlopen()'d format modules are walked
#     too; their own DLL dependencies (libxml2 and co.) appear in no other
#     file's import table.
#
# LAYOUT, from Gwyddion's own source (libgwyddion/gwyutils.c,
# gwy_find_self_dir() G_OS_WIN32 branch + ensure_topdir()): modules resolve
# as GWYDDION_LIBDIR + "gwyddion\modules" when that variable is set, and
# otherwise as topdir + "lib" + "gwyddion\modules", where topdir comes from
# GLib's g_win32_get_package_installation_directory_of_module() on the
# libgwyddion DLL — which strips a trailing `bin` or `lib` component.
#
# The DLLs sit in the wheel's bin/, so topdir is the gwyddionpy_converter
# package directory and the modules must live at
# <package>/lib/gwyddion/modules, a SIBLING of bin/ — the same layout as
# Gwyddion's own Windows installs, and the reason MANIFEST.in ships that
# second directory. The fallback branch is the one that matters here:
# nothing sets GWYDDION_LIBDIR at user run time (Windows has no wrapper
# script; binary_path() returns the .exe directly), which is why the
# verification below deliberately runs without it.
set -euo pipefail

: "${PREFIX:?PREFIX must be set (Gwyddion install prefix)}"
: "${BUILT_GWYCONVERT:?BUILT_GWYCONVERT must be set}"
: "${BUNDLE_DIR:?BUNDLE_DIR must be set}"

# MinGW gcc appends .exe; normalize so the rest of the script has one name.
EXE="$BUILT_GWYCONVERT"
[ -f "$EXE" ] || EXE="$BUILT_GWYCONVERT.exe"
[ -f "$EXE" ] || { echo "error: $BUILT_GWYCONVERT(.exe) not found" >&2; exit 1; }

PKG_DIR="$(dirname "$BUNDLE_DIR")"
MODULES_PARENT="$PKG_DIR/lib"

echo "== Laying out the bundle: exe+DLLs in bin/, modules in sibling lib/ =="
rm -rf "$BUNDLE_DIR" "$MODULES_PARENT"
mkdir -p "$BUNDLE_DIR" "$MODULES_PARENT"
cp "$EXE" "$BUNDLE_DIR/gwyconvert.exe"
cp -r "$PREFIX/lib/gwyddion" "$MODULES_PARENT/gwyddion"

echo "== Walking DLL dependencies (objdump -p import tables) =="
# objdump, not `ntldd -R`: objdump reads each PE's import directory straight
# off disk, so the walk is authoritative and never depends on a tool's
# ability to LOAD a library in order to recurse past it — which is where
# ntldd -R proved to have a blind spot, reporting a complete bundle while
# the executable died at startup on a missing DLL.
list_imports() {
  objdump -p "$1" 2>/dev/null | awk '/DLL Name:/ {print $3}'
}

# The three places a dependency can live before bundling copies it in:
# already bundled, Gwyddion's own install (PREFIX/bin, libtool's Windows
# convention for shared libraries), or the MinGW64 toolchain. System DLLs
# (kernel32, msvcrt, ntdll, ...) resolve under none of them, so they drop
# out without any name-based filtering.
find_dll() {
  local name="$1" dir
  for dir in "$BUNDLE_DIR" "$PREFIX/bin" /mingw64/bin; do
    [ -f "$dir/$name" ] && { printf '%s\n' "$dir/$name"; return 0; }
  done
  return 1
}

# BFS over the transitive import closure of every path given.
collect_deps() {
  local -a queue=("$@")
  local -A seen=()
  local path name found
  while [ "${#queue[@]}" -gt 0 ]; do
    path="${queue[0]}"
    queue=("${queue[@]:1}")
    while read -r name; do
      [ -n "${seen[$name]:-}" ] && continue
      seen[$name]=1
      found="$(find_dll "$name")" || continue
      printf '%s\n' "$found"
      queue+=("$found")
    done < <(list_imports "$path")
  done
}

mapfile -t MODULE_FILES < <(find "$MODULES_PARENT/gwyddion" \( -name '*.dll' -o -name '*.so' \) -type f)
collect_deps "$BUNDLE_DIR/gwyconvert.exe" "${MODULE_FILES[@]}" | sort -u | while read -r dll; do
  case "$dll" in "$BUNDLE_DIR"/*) continue ;; esac  # already in place
  cp -n "$dll" "$BUNDLE_DIR/"
done
echo "bundled $(find "$BUNDLE_DIR" -maxdepth 1 -name '*.dll' | wc -l | tr -d ' ') DLLs beside gwyconvert.exe"

echo "== Verifying the bundle (no PATH, no GWYDDION_LIBDIR — the user path) =="
# The env is reduced in a specific way. PATH is set to EMPTY rather than
# unset, and the exec goes through a bash subshell rather than the external
# `env` binary: removing the PATH key outright made gwyconvert.exe exit 127
# with no output even with a demonstrably complete bundle. An empty PATH
# still proves DLL search does not depend on it (it contributes no search
# directories) without exercising that behaviour.
#
# GWYDDION_LIBDIR is genuinely unset, so module discovery must succeed
# through the topdir fallback documented above — the same lookup a user's
# machine performs.
set +e
OUTPUT="$(
  unset GWYDDION_LIBDIR
  PATH="" "$BUNDLE_DIR/gwyconvert.exe" --list-formats 2>&1
)"
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ] || [ -z "$OUTPUT" ]; then
  # Diagnostic: re-walk with the same objdump-based collect_deps used for
  # bundling and report anything missing from BUNDLE_DIR by basename.
  echo "gwyconvert.exe exited $STATUS; output was:" >&2
  echo "$OUTPUT" >&2
  echo "-- dependencies missing from the bundle directory --" >&2
  collect_deps "$BUNDLE_DIR/gwyconvert.exe" "${MODULE_FILES[@]}" | sort -u | while read -r dll; do
    [ -f "$BUNDLE_DIR/$(basename "$dll")" ] || echo "missing: $dll" >&2
  done
  exit 1
fi
printf '%s' "$OUTPUT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"
