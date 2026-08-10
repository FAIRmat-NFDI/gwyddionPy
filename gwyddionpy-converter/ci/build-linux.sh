#!/usr/bin/env bash
# Build the self-contained gwyconvert tarball released for linux-x86_64.
#
# Two shared steps plus packaging:
#   1. build-gwyddion.sh — Gwyddion from source, then gwyconvert.
#   2. bundle-linux.sh   — make the result relocatable.
#   3. tar + sha256      — the only part unique to this script.
#
# Output: $OUT_DIR/gwyconvert-linux-x86_64.tar.gz and a matching .sha256,
# attached to the GitHub Release by .github/workflows/build-converter.yml
# and downloaded by gwyddionpy's _fetch_converter.py. Renaming ASSET_NAME
# means updating _fetch_converter._asset_name() to match.
#
# The wheels do not go through this script. cibw-before-all-linux.sh calls
# bundle-linux.sh directly, straight into the wheel's package data.
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
