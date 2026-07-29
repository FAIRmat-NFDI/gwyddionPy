#!/usr/bin/env bash
# cibuildwheel `before-all` for Linux: install the Gwyddion build
# dependencies, build Gwyddion + gwyconvert, and stage the finished bundle
# into the wheel's package data.
#
# Runs inside the manylinux container, once per platform, before any wheel
# is built. cibuildwheel copies the project into the container and runs
# this with the project root as CWD, so writing into
# src/gwyddionpy_converter/bin/ is what the subsequent `setup.py` build
# picks up as package data.
#
# Why the bundle is assembled here rather than in `repair-wheel-command`:
# the default repair tools walk a binary's build-time link graph, which
# never reaches Gwyddion's dlopen()'d format plugins or *their* own
# dependencies (see docs/gwyddionpy-build-as-matid.md). bundle-linux.sh
# already solves that correctly and its output is self-contained and
# RPATH-patched, so there is nothing left for a repair step to do —
# pyproject.toml sets repair-wheel-command to a plain copy.
#
# The dnf lines mirror .github/workflows/build-converter.yml's Rocky Linux 8
# recipe. The official manylinux_2_28 image is AlmaLinux 8 — same RHEL 8
# family, same glibc 2.28 floor, same package names — which is exactly why
# this transfers (V1_IMPLEMENTATION.md V1d, approach C). Repo notes:
# fftw-devel lives in PowerTools (CRB), patchelf in EPEL.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== Installing Gwyddion build dependencies =="
dnf -y install dnf-plugins-core
# The CRB/PowerTools repo is named differently across EL8 rebuilds; try
# both rather than assuming the image's vendor.
dnf config-manager --set-enabled powertools 2>/dev/null \
  || dnf config-manager --set-enabled crb 2>/dev/null \
  || echo "note: neither powertools nor crb repo found; fftw-devel may already be available"
dnf -y install epel-release
dnf -y install \
  gcc-toolset-12 make pkgconf-pkg-config curl xz tar gzip bzip2 \
  python3 patchelf gawk file findutils diffutils \
  gtk2-devel fftw-devel libxml2-devel gettext

# gcc-toolset-12 is required, not optional: EL8's default GCC 8.5 rejects
# Gwyddion 2.71's OpenMP shared() clauses ("predetermined 'shared'"); the
# toolset compiler still targets glibc 2.28.
# shellcheck disable=SC1091
source /opt/rh/gcc-toolset-12/enable

WORK_DIR="$(mktemp -d)"
export WORK_DIR
export PREFIX="$WORK_DIR/install"
export GWYCONVERT_OUT="$WORK_DIR/gwyconvert"

"$SCRIPT_DIR/build-gwyddion.sh"

# Straight into package data — no tarball round-trip. setup.py's
# _check_bundle_present() guard fails the build if this step didn't run.
export BUILT_GWYCONVERT="$GWYCONVERT_OUT"
export BUNDLE_DIR="$PROJECT_DIR/src/gwyddionpy_converter/bin"
"$SCRIPT_DIR/bundle-linux.sh"

echo "Staged bundle at $BUNDLE_DIR"
ls -la "$BUNDLE_DIR"
