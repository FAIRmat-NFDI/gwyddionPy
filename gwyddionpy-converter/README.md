# gwyddionpy-converter

The GPL half of [`gwyddionpy`](https://github.com/FAIRmat-NFDI/gwyddionPy),
all in one place:

- `gwyconvert.c` + `Makefile` — the headless C converter that links
  Gwyddion's libraries (see the main repo's docs for build instructions).
- `ci/` — the scripts that build Gwyddion from its official source tarball
  and bundle a portable, self-contained `gwyconvert` for releases.
- `src/gwyddionpy_converter/` + `pyproject.toml`/`setup.py` — the Python
  packaging that wraps the prebuilt bundle as a platform wheel, so
  `pip install "gwyddionpy[converter]"` needs no post-install download step.

## License

**GPL-2.0-or-later** — `gwyconvert` links Gwyddion's GPL-licensed
libraries, and the wheel bundles them plus their runtime dependencies
(GTK2, GLib, FFTW, Pango, libxml2, X11 client libraries). See `COPYING`.

`gwyddionpy` itself stays Apache-2.0: it only ever executes this package's
binary as a subprocess, never imports or links it. See
[`license_discussion.md`](https://github.com/FAIRmat-NFDI/gwyddionPy/blob/main/license_discussion.md)
in the main repo for the full reasoning.

## Platforms

Linux x86_64 (`manylinux_2_28`-equivalent, glibc >= 2.28) only, for now.
macOS/Windows wheels are planned once those platform legs of
`build-converter.yml` exist.
