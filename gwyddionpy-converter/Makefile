# Builds gwyconvert against an already-installed Gwyddion, which is the
# local development path (see ../docs/user/how-to.md). Release artifacts
# are not built this way: ci/build-gwyddion.sh builds Gwyddion itself from
# source first, so the result is portable.
#
# Flags come from pkg-config where available. On Debian and Ubuntu that
# lookup fails unless libgtkglext1-dev is installed, because gwyddion.pc
# requires gtkglext-1.0. Hence the fallback, which links the Gwyddion
# libraries directly. That is enough, since gwyconvert uses no OpenGL
# widgets.
CC      ?= gcc
CFLAGS  ?= -O2 -Wall

HAVE_GWY_PC := $(shell pkg-config --exists gwyddion && echo yes)
ifeq ($(HAVE_GWY_PC),yes)
GWY_CFLAGS := $(shell pkg-config --cflags gwyddion)
GWY_LIBS   := $(shell pkg-config --libs gwyddion)
else
GWY_CFLAGS := -I/usr/include/gwyddion $(shell pkg-config --cflags gtk+-2.0)
GWY_LIBS   := -lgwyapp2 -lgwymodule2 -lgwydgets2 -lgwydraw2 -lgwyprocess2 \
              -lgwyddion2 $(shell pkg-config --libs gtk+-2.0) -lm
endif

gwyconvert: gwyconvert.c
	$(CC) $(CFLAGS) $(GWY_CFLAGS) -o $@ $< $(GWY_LIBS)

check: gwyconvert
	./gwyconvert --list-formats | head -c 200 && echo && echo "check: OK"

clean:
	rm -f gwyconvert

.PHONY: check clean
