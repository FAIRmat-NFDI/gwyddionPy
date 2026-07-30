#!/usr/bin/env bash
# cibuildwheel `before-all` for macOS: install the Gwyddion build
# dependencies via Homebrew, build Gwyddion + gwyconvert, and stage the
# finished bundle into the wheel's package data.
#
# Runs natively on whichever architecture the runner is — arm64 on
# `macos-15`, x86_64 on `macos-15-intel`. Deliberately NOT a cross-build:
# Homebrew only ships bottles for the host architecture, so building an
# arm64 wheel on an Intel runner would have no arm64 GTK2/GLib/FFTW to link
# against. Two runners, each building its own wheel, is the same shape matid
# uses.
#
# Package facts confirmed 2026-07-29 via the Homebrew API: the `gtk+`
# formula is GTK2 2.24.33 and is neither deprecated nor disabled, and it
# pulls in glib, cairo, pango, gdk-pixbuf and at-spi2-core as dependencies.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== Installing Gwyddion build dependencies (Homebrew) =="
# `gtk+` is GTK2 (GTK3 is `gtk+3`, GTK4 is `gtk4`) — the name is a historical
# artifact and picking the wrong one silently gets you a toolkit Gwyddion
# 2.x cannot build against.
brew install gtk+ fftw libxml2 gettext pkg-config

# Homebrew's keg-only libraries are not on the default search paths.
BREW_PREFIX="$(brew --prefix)"
export PKG_CONFIG_PATH="$BREW_PREFIX/lib/pkgconfig:$BREW_PREFIX/opt/libxml2/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
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
