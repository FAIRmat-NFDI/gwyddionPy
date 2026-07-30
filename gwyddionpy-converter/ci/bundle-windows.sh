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
#   - Discovery uses ntldd -R (MSYS2's recursive PE dependency walker).
#     System DLLs are excluded by path: anything resolving outside the
#     MinGW prefix (KERNEL32, msvcrt, ntdll, ... live in C:\Windows) stays
#     out; everything from /mingw64 travels.
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

echo "== Walking DLL dependencies (ntldd -R) =="
# ntldd -R prints "NAME => PATH (address)" recursively. Keep only deps that
# resolved inside the MinGW prefix (both /mingw64/... and the Windows-style
# C:\msys64\mingw64\... spellings appear depending on version); everything
# else is an OS DLL and must not travel.
collect_deps() {
  ntldd -R "$1" 2>/dev/null | awk '$2 == "=>" {print $3}' |
    grep -Ei '([/\\]|^)mingw64[/\\]' || true
}

{
  collect_deps "$BUNDLE_DIR/gwyconvert.exe"
  find "$MODULES_PARENT/gwyddion" \( -name '*.dll' -o -name '*.so' \) -type f |
    while read -r m; do collect_deps "$m"; done
} | sort -u | while read -r dll; do
  # Normalize C:\msys64\mingw64\bin\foo.dll to a copyable POSIX path.
  p="$(cygpath -u "$dll" 2>/dev/null || printf '%s' "$dll")"
  [ -f "$p" ] && cp -n "$p" "$BUNDLE_DIR/" || echo "warning: dep not found: $dll" >&2
done
echo "bundled $(find "$BUNDLE_DIR" -maxdepth 1 -name '*.dll' | wc -l | tr -d ' ') DLLs beside gwyconvert.exe"

echo "== Verifying the bundle (clean env, NO GWYDDION_LIBDIR — the user path) =="
# env -i clears PATH too, which on Windows doubles as the DLL search path,
# so this proves the exe runs on its bundled DLLs alone. SYSTEMROOT must
# survive (OS DLLs require it). GWYDDION_LIBDIR is deliberately NOT set:
# module discovery must succeed via the topdir fallback documented above,
# because that is all a user's machine has.
env -i SYSTEMROOT="${SYSTEMROOT:-C:\\Windows}" \
  "$BUNDLE_DIR/gwyconvert.exe" --list-formats | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert len(d) > 100, d; print(f'bundle OK: {len(d)} formats')"
