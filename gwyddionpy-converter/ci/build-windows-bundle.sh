#!/usr/bin/env bash
# Windows: install deps, build Gwyddion + gwyconvert, stage the bundle into
# the wheel's package data. Runs in an MSYS2 MinGW64 shell (msys2/setup-msys2
# provides it in CI).
#
# Unlike Linux and macOS this is NOT a cibuildwheel `before-all`:
# cibuildwheel runs Windows commands under cmd, and threading a full MSYS2
# login shell through that is needless quoting fragility. build-converter.yml
# runs this script as its own msys2 step BEFORE cibuildwheel instead — the
# two must stay in that order, and setup.py's _check_bundle_present() turns
# a mistake into a loud failure rather than an empty wheel.
#
# Packages come from the MSYS2 mingw64 repo (mingw-w64-x86_64-gtk2 is GTK2
# 2.24.x): https://packages.msys2.org/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== Installing Gwyddion build dependencies (pacman) =="
# The toolchain group also supplies binutils, hence objdump, which
# bundle-windows.sh uses to walk PE import tables. python runs the
# format-count assertions in build-gwyddion.sh and bundle-windows.sh.
pacman -S --noconfirm --needed \
  mingw-w64-x86_64-toolchain \
  mingw-w64-x86_64-gtk2 \
  mingw-w64-x86_64-fftw \
  mingw-w64-x86_64-libxml2 \
  mingw-w64-x86_64-pkgconf \
  mingw-w64-x86_64-python \
  make gettext-devel

WORK_DIR="$(mktemp -d)"
export WORK_DIR
export PREFIX="$WORK_DIR/install"
export GWYCONVERT_OUT="$WORK_DIR/gwyconvert"

"$SCRIPT_DIR/build-gwyddion.sh"

export BUILT_GWYCONVERT="$GWYCONVERT_OUT"
export BUNDLE_DIR="$PROJECT_DIR/src/gwyddionpy_converter/bin"
"$SCRIPT_DIR/bundle-windows.sh"

echo "Staged bundle:"
ls "$BUNDLE_DIR" | head
ls "$PROJECT_DIR/src/gwyddionpy_converter/lib"
