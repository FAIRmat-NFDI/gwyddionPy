# Building gwyddionpy

Two things get built/installed: the C converter `gwyconvert` and the Python
package. The Python package is pure Python — only the converter needs a C
toolchain.

## Prerequisites

- C compiler + make + pkg-config (`sudo apt install build-essential pkg-config`)
- Gwyddion development headers — **Route 1** below (default) or **Route 2**
- Python ≥ 3.9 with `venv`

## Route 1 (default): system Gwyddion dev package

```bash
# libgwyddion20-dev alone is NOT enough: its .pc file Requires glib/gtk2/fftw3
# dev files that Ubuntu does not pull in automatically (see TROUBLESHOOTING.md)
sudo apt install libgwyddion20-dev libgtk2.0-dev libfftw3-dev
# verify:
pkg-config --print-errors --exists gwyddion && echo OK
```

This matches the Gwyddion 2.60 runtime already installed on the dev machine
(verified 2026-07-07). The dev package pulls the GTK2/GLib dev chain as
dependencies. No display/X server is needed to *run* the converter.

## Route 2 (fallback): build Gwyddion from the source submodule

Only needed if we must patch file modules or the distro package is too old.

```bash
git submodule update --init vendor/gwyddion   # one-time fetch (large)
cd vendor/gwyddion/gwyddion/
./autogen.sh --prefix=$HOME/.local --disable-gtk-doc --disable-desktop-file-update
make -j$(nproc) && make install
export PKG_CONFIG_PATH=$HOME/.local/lib/pkgconfig:$PKG_CONFIG_PATH
```

Expect to install GTK2 dev packages first (`libgtk2.0-dev`, `libxml2-dev`,
`libfftw3-dev`, ...). Record any additional packages you needed in
TROUBLESHOOTING.md.

## Building the converter

```bash
cd converter/
make            # produces ./gwyconvert
make check      # smoke test: --list-formats runs and prints JSON
```

## Installing the Python package (pip venv)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e python/                    # editable, for development
export GWYDDIONPY_CONVERT=$PWD/converter/gwyconvert   # if not on PATH
```

For end users the sequence is: install Gwyddion (apt/conda/installer), install
`gwyconvert` somewhere on `$PATH`, then `pip install gwyddionpy`.

## Verifying the full pipeline

```bash
python -c "import gwyddionpy; d = gwyddionpy.load('sample.spm'); print(list(d.channels))"
```

Sample files: see `test-data/README.md` (provenance + re-fetch commands).
