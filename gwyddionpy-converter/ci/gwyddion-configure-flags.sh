# Gwyddion `configure` flags for every build that ships: the wheels
# (ci/build-gwyddion.sh) and the conda package (recipe/build.sh). Both
# scripts source this file, so a change here reaches both.
#
# gwyconvert only needs the file modules, so OpenGL, docs, translations and
# the Python bindings are left out.
GWYDDION_CONFIGURE_FLAGS=(
  --without-gl
  --disable-gtk-doc
  --disable-desktop-file-update
  --disable-pygwy
)

# On MinGW, LC_MESSAGES comes only from libintl.h, which --disable-nls drops,
# so Gwyddion's utils/dump-modules.c fails to compile. Keep translations there.
case "$(uname -s)" in
  MINGW* | MSYS*) ;;
  *) GWYDDION_CONFIGURE_FLAGS+=(--disable-nls) ;;
esac
