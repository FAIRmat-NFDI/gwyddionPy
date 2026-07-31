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
# Windows makes the *relocation* part trivial and the *discovery* part the
# whole job:
#   - No RPATH/install-name machinery exists. The loader searches the
#     executable's own directory first, so DLLs beside the .exe simply work.
#     Nothing is patched, so nothing needs re-signing either.
#   - Discovery walks each PE's import table via objdump -p, recursively
#     (see collect_deps below). System DLLs are excluded implicitly: they
#     never resolve under BUNDLE_DIR, PREFIX/bin, or /mingw64/bin, so only
#     genuine MinGW64-toolchain DLLs travel.
#   - As on the other platforms, the dlopen()'d format modules are walked
#     too: their own DLL deps (libxml2 & co.) appear in no other file's
#     import table.
#
# LAYOUT — grounded in Gwyddion 2.71's actual source (libgwyddion/gwyutils.c,
# read 2026-07-30, gwy_find_self_dir() G_OS_WIN32 branch + ensure_topdir()):
# on Windows, modules resolve as GWYDDION_LIBDIR + "gwyddion\modules" if the
# env var is set (same semantics as Unix), else as topdir + "lib" +
# "gwyddion\modules", where topdir comes from GLib's
# g_win32_get_package_installation_directory_of_module() on the libgwyddion
# DLL — which strips a trailing `bin` or `lib` path component. Our DLLs sit
# in the wheel's bin/, so topdir = the gwyddionpy_converter package dir, and
# the modules must live at <package>/lib/gwyddion/modules — a SIBLING of
# bin/, exactly like Gwyddion's own Windows installs. That fallback path is
# the one that matters: at user runtime nothing sets GWYDDION_LIBDIR (there
# is no wrapper on Windows; binary_path() returns the exe directly), so the
# verification below runs WITHOUT the env var, exercising the same lookup a
# user's machine will.
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
# Switched from `ntldd -R`: across two rounds of environment fixes to the
# verification below (full env wipe, then just PATH/GWYDDION_LIBDIR, then a
# bash builtin exec with PATH="") gwyconvert.exe kept exiting 127 with zero
# output — an instant, silent CreateProcess failure, the signature of a
# required DLL that can't be found — while ntldd -R kept reporting nothing
# missing, both here and in the post-failure diagnostic below, which share
# the same resolution logic. That agreement is exactly what you'd see if
# ntldd -R has a recursion blind spot rather than the bundle being correct.
# objdump reads each PE's import directory straight off disk, so walking is
# authoritative and never depends on ntldd's own ability to load/resolve a
# hop in order to keep recursing past it.
list_imports() {
  objdump -p "$1" 2>/dev/null | awk '/DLL Name:/ {print $3}'
}

# Where a dependency could actually live before bundling copies it in:
# already-bundled, Gwyddion's own install (PREFIX/bin — libtool's Windows
# convention for shared libs), then the MinGW64 toolchain itself. System
# DLLs (kernel32, msvcrt, ntdll, ...) never resolve under any of these three,
# so they drop out on their own — no path-string filtering needed, unlike
# the old grep -Ei 'mingw64' approach.
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
# Neither `env -i` (full wipe) nor `env -u PATH -u GWYDDION_LIBDIR` worked:
# both made gwyconvert.exe exit 127 with zero output, and the collect_deps
# diagnostic below confirmed every recursively-walked dependency is already
# present in BUNDLE_DIR — so this isn't a missing-DLL defect. The common
# factor in both failing attempts was deleting the PATH *key* outright via
# the external `env` binary. Two changes at once to isolate that:
#   - exec via a bash subshell instead of the separate `env` binary, so
#     there's no second MSYS-linked process involved in the fork/exec;
#     bash never consults PATH to run a name containing a slash anyway.
#   - set PATH="" (present but empty) instead of unsetting the key. This
#     still proves DLL search doesn't depend on PATH (empty adds no search
#     directories), without exercising whatever "PATH has no value at all"
#     path CreateProcess/CRT startup may handle differently.
# GWYDDION_LIBDIR is still genuinely unset, so module discovery must still
# succeed via the topdir fallback documented above.
set +e
OUTPUT="$(
  unset GWYDDION_LIBDIR
  PATH="" "$BUNDLE_DIR/gwyconvert.exe" --list-formats 2>&1
)"
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ] || [ -z "$OUTPUT" ]; then
  # Still broken: re-walk with the same objdump-based collect_deps used for
  # bundling above and report anything not actually present in BUNDLE_DIR by
  # basename — this is the authoritative check now, not a best-effort retry.
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
