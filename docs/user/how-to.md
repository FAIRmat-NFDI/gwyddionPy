# How to install gwyddionpy

gwyddionpy is two pieces:

- the **`gwyddionpy` Python package** — pure Python, Apache-2.0;
- the **`gwyconvert` helper binary** — GPL-2.0-or-later, because it links
  [Gwyddion](http://gwyddion.net); it does the actual format conversion.

The Python package never bundles the binary. You always install the two
separately, and there are three ways to get the binary:

1. **The companion wheel** — one `pip install`, nothing to build. Linux
   x86_64, macOS (Apple Silicon and Intel), Windows x86_64.
2. **A prebuilt binary from a GitHub Release** — no GPL package in your
   environment. linux-x86_64 only.
3. **Build it yourself** — any platform with Gwyddion available.

All three end with the same working install. Option 1 unless you have a
reason to prefer another.

> **TestPyPI note.** Both packages are published to TestPyPI only for now,
> so every `pip install` below carries two index flags. Drop them once the
> packages reach production PyPI.

## Option 1 — the companion wheel

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -i https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            "gwyddionpy[converter]"
```

That is all. The `[converter]` extra pulls `gwyddionpy-converter`, which
ships `gwyconvert` as package data; gwyddionpy finds it automatically, with
no environment variable to set. Skip to [Verify](#verify).

The extra is opt-in on purpose: a plain `pip install gwyddionpy` stays
entirely Apache-2.0, so requesting the GPL binary is always your explicit
choice.

## Option 2 — a prebuilt binary from a GitHub Release

Useful when you want the binary without a GPL package in your environment.

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -i https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            gwyddionpy

gwyddionpy-fetch-converter
```

`gwyddionpy-fetch-converter` downloads the binary for your platform,
verifies its checksum, and unpacks it into a per-user cache directory that
gwyddionpy searches automatically — again, no environment variable. It is
also callable from Python as `gwyddionpy.ensure_converter()`.

This step never runs on its own: not during `pip install`, not on
`import gwyddionpy`. It also never touches `apt`/`dnf`/`brew` and needs no
privileges — it is an HTTPS download.

Only `linux-x86_64` is published this way; on any other platform the command
exits with a clear error. Use option 1 or 3 there.

## Option 3 — build gwyconvert yourself

Works on any distribution that packages Gwyddion, and depends on no CI
artifact of this project.

```bash
# 1. Gwyddion + build tools.
#    `gwyddion` itself is required, not only the -dev package: Debian and
#    Ubuntu ship the file-format plugins in `gwyddion`, and without them
#    gwyconvert builds and runs but recognizes zero formats.
sudo apt install libgwyddion20-dev gwyddion libgtk2.0-dev libfftw3-dev \
                 build-essential pkg-config git

# 2. The repository, and the converter binary
git clone https://github.com/FAIRmat-NFDI/gwyddionPy.git
cd gwyddionPy
make -C gwyddionpy-converter

# 3. A Python environment with the gwyddionpy package
python3 -m venv .venv
source .venv/bin/activate
pip install -i https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            gwyddionpy

# 4. Point gwyddionpy at the binary you just built
export GWYDDIONPY_CONVERT=$PWD/gwyddionpy-converter/gwyconvert
```

Package names above are Debian's and Ubuntu's. On other distributions
install the equivalents (Fedora: `gwyddion` + `gwyddion-devel`) and continue
from step 2.

To avoid distribution packages entirely, build Gwyddion itself from its
official source tarball with `gwyddionpy-converter/ci/build-gwyddion.sh` —
the same script this project's CI and release builds use. It takes
`WORK_DIR`, `PREFIX` and `GWYCONVERT_OUT` from the environment and produces
a `gwyconvert` linked against its own Gwyddion.

## Verify

```bash
python3 -c "import gwyddionpy; print(len(gwyddionpy.list_formats()), 'formats')"
```

Expect a number well over 100; ~170 is typical.

**Zero is the failure mode to watch for.** A converter that cannot find
Gwyddion's format plugins still starts and exits cleanly — it simply
registers nothing. If you see zero after option 3, the `gwyddion` package
from step 1 is the first thing to check.

`ConverterNotFoundError` instead means no binary was found at all: check
that `GWYDDIONPY_CONVERT` points at a real file, or that step 2 actually
produced one.

Then try a real measurement file:

```bash
python3 -c "import gwyddionpy; d = gwyddionpy.load('your_scan_file'); print(list(d.channels))"
```
