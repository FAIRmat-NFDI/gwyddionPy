# gwyddionpy-converter

The GPL half of [`gwyddionpy`](https://github.com/FAIRmat-NFDI/gwyddionPy),
all in one place:

- `gwyconvert.c` + `Makefile` — the headless C converter that links
  Gwyddion's libraries. The Makefile builds against an already-installed
  Gwyddion, which is the local development path. Its command-line contract
  (usage, exit codes, what goes on each output stream) is written up in
  [`docs/user/gwyconvert-cli.md`](https://github.com/FAIRmat-NFDI/gwyddionPy/blob/main/docs/user/gwyconvert-cli.md).
  `gwyddionpy` depends on it and the two packages are released separately,
  so treat it as an interface, not an implementation detail.
- `ci/` — the release recipe: `build-gwyddion.sh` builds Gwyddion itself
  from its official source tarball, and the `bundle-*.sh` scripts turn the
  result into a portable, self-contained bundle per platform.
- `src/gwyddionpy_converter/` + `pyproject.toml`/`setup.py` — the Python
  packaging that ships that bundle as a platform wheel, so
  `pip install "gwyddionpy[converter]"` needs no download or build step.

## License

**GPL-2.0-or-later** — `gwyconvert` links Gwyddion's GPL-licensed
libraries, and the wheel bundles them plus their runtime dependencies
(GTK2, GLib, FFTW, Pango, libxml2, X11 client libraries). See `COPYING`.

`gwyddionpy` itself stays Apache-2.0: it only ever executes this package's
binary as a subprocess, never imports or links it. The
[repository README](https://github.com/FAIRmat-NFDI/gwyddionPy) describes
that boundary in full.

## Platforms

One wheel per platform, built by `.github/workflows/build-converter.yml`:

| Wheel tag | Runner | Built from |
|---|---|---|
| `manylinux_2_28_x86_64` (glibc ≥ 2.28) | `ubuntu-latest` | `ci/cibw-before-all-linux.sh` |
| `macosx_*_arm64` | `macos-15` | `ci/cibw-before-all-macos.sh` |
| `macosx_*_x86_64` | `macos-15-intel` | `ci/cibw-before-all-macos.sh` |
| `win_amd64` | `windows-latest` | `ci/build-windows-bundle.sh` |

All are tagged `py3-none-<platform>`. The payload is a standalone executable
with no dependency on a Python application binary interface (ABI), so one
wheel serves every Python version.

No source distribution is published, deliberately: it would let `pip` fall
back to building Gwyddion from source on a user's machine.
