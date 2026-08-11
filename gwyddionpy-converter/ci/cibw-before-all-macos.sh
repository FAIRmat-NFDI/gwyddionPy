#!/usr/bin/env bash
# cibuildwheel `before-all` for macOS: install Gwyddion's build
# dependencies with Homebrew, build Gwyddion and gwyconvert, and stage the
# bundle into the wheel's package data.
#
# Runs natively on whichever architecture the runner has: arm64 on
# `macos-15`, x86_64 on `macos-15-intel`. Never a cross-build, because
# Homebrew ships bottles for the host architecture only, so an arm64 wheel
# built on an Intel runner would have no arm64 libraries to link against.
# Two runners cover both architectures instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== Installing Gwyddion build dependencies (Homebrew) =="
# `gtk+` is GTK2; GTK3 is `gtk+3` and GTK4 is `gtk4`. The naming is
# historical, and the wrong choice quietly yields a toolkit Gwyddion 2.x
# cannot build against. https://formulae.brew.sh/formula/gtk+
#
# `libzip` gives Gwyddion its zip-container readers. Without it, configure
# reports no zip library and silently builds eight fewer file modules:
# apedaxfile, nanoobserver, nanoscantech, opengps, scnxfile, sensofarx,
# spmxfile and zonfile. Installed explicitly because assuming it was
# already present is what shipped arm64 and x86_64 wheels that could read
# different numbers of formats.
brew install gtk+ fftw libxml2 libzip gettext pkg-config

# Homebrew's keg-only libraries are off the default search paths, and on
# Apple Silicon so is the Homebrew prefix itself: /opt/homebrew is not a
# compiler default the way Intel's /usr/local is. PKG_CONFIG_PATH alone is
# therefore not enough on arm64, because parts of Gwyddion's configure look
# for headers such as fftw3.h through plain compiles rather than
# pkg-config, and fail with "fftw3.h file not found".
BREW_PREFIX="$(brew --prefix)"
export PKG_CONFIG_PATH="$BREW_PREFIX/lib/pkgconfig:$BREW_PREFIX/opt/libxml2/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export CPPFLAGS="-I$BREW_PREFIX/include -I$BREW_PREFIX/opt/libxml2/include ${CPPFLAGS:-}"
export LDFLAGS="-L$BREW_PREFIX/lib -L$BREW_PREFIX/opt/libxml2/lib ${LDFLAGS:-}"
export PATH="$BREW_PREFIX/opt/gettext/bin:$PATH"

WORK_DIR="$(mktemp -d)"
export WORK_DIR
export PREFIX="$WORK_DIR/install"
export GWYCONVERT_OUT="$WORK_DIR/gwyconvert"

"$SCRIPT_DIR/build-gwyddion.sh"

export BUILT_GWYCONVERT="$GWYCONVERT_OUT"
export BUNDLE_DIR="$PROJECT_DIR/src/gwyddionpy_converter/bin"
"$SCRIPT_DIR/bundle-macos.sh"

echo "Staged bundle at $BUNDLE_DIR"
ls -la "$BUNDLE_DIR"
