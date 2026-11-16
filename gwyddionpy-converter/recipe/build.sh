#!/bin/bash
# Mirrors gwyddionpy-converter/ci/build-gwyddion.sh, but installs into $PREFIX.
set -euxo pipefail

# Newer config.guess/config.sub, so configure knows osx-arm64 and linux-aarch64.
cp "${BUILD_PREFIX}"/share/gnuconfig/config.* gwyddion/

cd gwyddion
# No OpenGL, docs, translations or Python bindings: gwyconvert only needs the file modules.
./configure --prefix="${PREFIX}" \
  --without-gl \
  --disable-gtk-doc \
  --disable-desktop-file-update \
  --disable-nls \
  --disable-pygwy
make -j"${CPU_COUNT}"
make install
cd ..

# gwyconvert finds the file modules relative to its own path, so it goes in $PREFIX/bin.
"${CC}" ${CFLAGS} ${CPPFLAGS} $(pkg-config --cflags gwyddion) \
  -o "${PREFIX}/bin/gwyconvert" gwyddionpy/gwyddionpy-converter/gwyconvert.c \
  ${LDFLAGS} $(pkg-config --libs gwyddion)
