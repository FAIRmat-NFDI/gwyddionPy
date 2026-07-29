#!/usr/bin/env bash
# Build a self-contained, releasable gwyconvert tarball for linux-x86_64.
#
# Two thin steps on top of the shared recipes:
#   1. build-gwyddion.sh — build Gwyddion from source (--without-gl) and
#      gwyconvert against it. Shared with pytest.yml.
#   2. bundle-linux.sh   — make the result relocatable. Shared with
#      cibw-before-all-linux.sh (V1d-2).
# Everything specific to *this* script is the packaging below: producing
# the `gwyconvert-linux-x86_64.tar.gz` GitHub Release asset that
# gwyddionpy's _fetch_converter.py downloads. The wheel path does not go
# through here — it bundles straight into package data.
#
# `--without-gl` (in build-gwyddion.sh) drops the OpenGL/GLX/gtkglext
# dependency entirely (verified 2026-07-21 by hand — see
# V1_IMPLEMENTATION.md: the system package's gwyddion.pc Requires
# gtkglext, the tarball build's doesn't, and a real conversion of a Bruker
# sample file through gwyddionpy.load() produces identical output either
# way), which matters specifically here because a *released* binary needs
# to be minimal and portable, not just working in-place.
#
# Produces $OUT_DIR/gwyconvert-linux-x86_64.tar.gz + a matching .sha256.
set -euo pipefail

OUT_DIR="${OUT_DIR:-$PWD/dist-converter}"
ASSET_NAME="gwyconvert-linux-x86_64.tar.gz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
export WORK_DIR
PREFIX="$WORK_DIR/install"
export PREFIX
BUILT_GWYCONVERT="$WORK_DIR/gwyconvert"
export GWYCONVERT_OUT="$BUILT_GWYCONVERT"

"$SCRIPT_DIR/build-gwyddion.sh"

BUNDLE_DIR="$WORK_DIR/bundle"
export BUILT_GWYCONVERT BUNDLE_DIR
"$SCRIPT_DIR/bundle-linux.sh"

echo "== Packaging =="
mkdir -p "$OUT_DIR"
tar czf "$OUT_DIR/$ASSET_NAME" -C "$BUNDLE_DIR" gwyconvert lib
(cd "$OUT_DIR" && sha256sum "$ASSET_NAME") > "$OUT_DIR/$ASSET_NAME.sha256"
cp "$SCRIPT_DIR/../COPYING" "$OUT_DIR/COPYING" 2>/dev/null || true

echo "Wrote $OUT_DIR/$ASSET_NAME"
