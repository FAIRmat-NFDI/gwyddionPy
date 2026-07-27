# How to install gwyddionpy

gwyddionpy is two pieces: the `gwyddionpy` Python package (pure Python,
Apache-2.0) and the `gwyconvert` helper binary (GPL-2.0-or-later, since it
links Gwyddion) that does the actual file-format conversion. The Python
package never bundles the binary — you always get it separately, one of
two ways:

1. **Build everything yourself** on a fresh Linux machine — works on any
   distro with Gwyddion packaged, no dependency on this project's own CI.
2. **Download a prebuilt binary** from this project's GitHub Releases —
   faster, no C toolchain needed, currently Linux-only.

Pick whichever fits; both end with the same working `gwyddionpy` install.

## 1. Installation on a fresh Linux distro (build it yourself)

### a. Installation

```bash
# 1. Gwyddion + build tools. `gwyddion` itself is required, not just the
#    -dev package — the actual file-format module plugins are packaged
#    under `gwyddion`, not libgwyddion20-dev (see docs/BUILD.md).
sudo apt install libgwyddion20-dev gwyddion libgtk2.0-dev libfftw3-dev \
                  build-essential pkg-config git

# 2. This repository, and the converter binary
git clone https://github.com/FAIRmat-NFDI/gwyddionPy.git
cd gwyddionPy
make -C gwyddionpy-converter

# 3. A Python environment with the gwyddionpy package
python3 -m venv .venv
source .venv/bin/activate
pip install -i https://test.pypi.org/simple/ \
             --extra-index-url https://pypi.org/simple/ \
             gwyddionpy
# (gwyddionpy is on TestPyPI only for now — drop the two -i/--extra-index-url
# flags above once it's on production PyPI; docs/MAINTENANCE.md tracks that)

# 4. Point gwyddionpy at the binary you just built
export GWYDDIONPY_CONVERT=$PWD/gwyddionpy-converter/gwyconvert
```

Not on Debian/Ubuntu? Install Gwyddion via your distro's package manager
(the package names above are Debian/Ubuntu's; e.g. Fedora's is `gwyddion`
+ `gwyddion-devel`) instead of `apt`, then continue from step 2 — or use
the **source tarball build** in `docs/BUILD.md` to build Gwyddion itself
from its official release tarball instead of relying on any distro
package at all.

### b. Check the installation works

```bash
python3 -c "import gwyddionpy; formats = gwyddionpy.list_formats(); print(len(formats), 'formats')"
```

Expect a number well over 100 (170+ is typical). **Zero is the specific
failure mode to watch for** — a broken build can link and run perfectly
fine while silently registering no formats at all (this project hit that
exact bug twice; see `V1_IMPLEMENTATION.md` if you're curious). If you get
`ConverterNotFoundError` instead, `GWYDDIONPY_CONVERT` isn't set correctly
or `make -C gwyddionpy-converter` didn't produce a binary — re-check step 2/4 above.

Once that works, try it on a real file:

```bash
python3 -c "import gwyddionpy; d = gwyddionpy.load('your_scan_file'); print(list(d.channels))"
```

## 2. Installation from the prebuilt GitHub binary

No C toolchain, no Gwyddion system packages — `gwyddionpy` fetches an
already-built `gwyconvert` for you.

**Status — this doesn't work yet, on either side:** the `gwyddionpy`
package currently published on TestPyPI (`0.0.0`) predates the fetch-helper
code itself — `gwyddionpy-fetch-converter` isn't in it at all yet (verified
by hand: installing that exact package and running the command gives "No
such file"). Separately, `.github/workflows/build-converter.yml` hasn't
completed a real run either, so there's no binary on a GitHub Release to
fetch even once a new package version ships it. This section describes the
intended flow for once both catch up; use option 1 until then.

### a. Installation

```bash
# 1. A Python environment with the gwyddionpy package
python3 -m venv .venv
source .venv/bin/activate
pip install -i https://test.pypi.org/simple/ \
             --extra-index-url https://pypi.org/simple/ \
             gwyddionpy
# (same TestPyPI note as option 1 — drop those two flags once it's on
# production PyPI)

# 2. Download the prebuilt gwyconvert for your platform
gwyddionpy-fetch-converter
```

That's it — no environment variable to set. `gwyddionpy-fetch-converter`
downloads the binary (checksum-verified) into a per-user cache directory,
and `gwyddionpy` finds it there automatically from then on. It's also
callable from Python directly: `gwyddionpy.ensure_converter()`.

This step never runs on its own — not during `pip install`, not on
`import gwyddionpy` — you always trigger it explicitly. It also never
touches `apt`/`dnf`/`brew`; it's a plain HTTPS download.

### b. Check the installation works

Same check as option 1:

```bash
python3 -c "import gwyddionpy; formats = gwyddionpy.list_formats(); print(len(formats), 'formats')"
```

Expect well over 100 formats, not zero, and no `ConverterNotFoundError`.
If `gwyddionpy-fetch-converter` reported a download error, re-run it with
`--force` after checking your network, or fall back to option 1.
