#!/usr/bin/env bash
# cibuildwheel `before-all` for macOS: install Gwyddion's build
# dependencies via Homebrew, build Gwyddion + gwyconvert, and stage the
# bundle into the wheel's package data.
#
# Runs natively on whichever architecture the runner has — arm64 on
# `macos-15`, x86_64 on `macos-15-intel`. Never a cross-build: Homebrew
# ships bottles for the host architecture only, so an arm64 wheel built on
# an Intel runner would have no arm64 GTK2/GLib/FFTW to link against. Both
# architectures are covered by using two runners instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== Installing Gwyddion build dependencies (Homebrew) =="
# `gtk+` is GTK2; GTK3 is `gtk+3` and GTK4 is `gtk4`. The name is a
# historical artifact, and the wrong choice silently yields a toolkit
# Gwyddion 2.x cannot build against.
# https://formulae.brew.sh/formula/gtk+
#
# `libzip` is what gives Gwyddion its zip-container readers: without it
# configure reports no zip library and silently builds eight fewer file
# modules — apedaxfile, nanoobserver, nanoscantech, opengps, scnxfile,
# sensofarx, spmxfile and zonfile. Installed explicitly because relying on
# it being present already is exactly what went wrong: the x86_64 runner
# has it on a default search path under /usr/local and found it, while
# arm64's /opt/homebrew is not a default, so the two architectures shipped
# wheels that could read different numbers of formats.
brew install gtk+ fftw libxml2 libzip gettext pkg-config

# Homebrew's keg-only libraries are off the default search paths — and on
# Apple Silicon so is $BREW_PREFIX itself, since /opt/homebrew is not a
# compiler default the way Intel's /usr/local is. PKG_CONFIG_PATH alone is
# therefore not enough on arm64: parts of Gwyddion's configure and build
# look for headers (fftw3.h among them) through plain CPPFLAGS compiles
# rather than pkg-config, and fail with "fftw3.h file not found".
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
