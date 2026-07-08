# Requires Gwyddion development headers: see ../docs/BUILD.md
#
# Preferred flags come from pkg-config's gwyddion module. On Ubuntu that
# fails unless libgtkglext1-dev is also installed (gwyddion.pc Requires
# gtkglext-1.0), so there is a manual fallback that links the Gwyddion
# libraries directly — sufficient because gwyconvert uses no GL widgets.
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
