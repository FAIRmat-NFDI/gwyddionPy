# How to install gwyddionpy

gwyddionpy is two pieces:

- the **`gwyddionpy` Python package** — pure Python, Apache-2.0;
- the **`gwyconvert` helper binary** — GPL-2.0-or-later, because it links
  [Gwyddion](http://gwyddion.net). It does the actual format conversion.

The Python package never bundles the binary, so you always install the two
separately. There are three ways to get the binary:

1. **The companion wheel** — one `pip install`, nothing to build. Linux
   x86_64, macOS (Apple Silicon and Intel), Windows x86_64.
2. **A prebuilt binary from a GitHub Release** — no GPL package in your
   environment. linux-x86_64 only.
3. **Build it yourself** — any platform with Gwyddion available.

All three end with the same working install. Option 1 unless you have a
reason to prefer another.

## Which package do I install?

Three names come up, and only two of them are actual packages:

| Name | What it is | License |
|---|---|---|
| `gwyddionpy` | The Python package. Pure Python: the data model, the parser, the exports. **Reads no vendor format on its own** — it needs the binary. | Apache-2.0 |
| `gwyddionpy-converter` | A separate distribution whose only payload is a prebuilt `gwyconvert` binary plus the Gwyddion libraries it links, shipped as package data. No Python API to speak of. | GPL-2.0-or-later |
| `gwyddionpy[converter]` | **Not a third package** — an [extra](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras) on the first that declares a dependency on the second. Installing it gets you both. | both of the above |

So `pip install "gwyddionpy[converter]"` and
`pip install gwyddionpy gwyddionpy-converter` install the same two
distributions. The extra is simply the form that keeps the version pin
correct — the release workflow rewrites it to pin the matching converter
version, which typing the two names yourself does not do.

**Install `gwyddionpy[converter]`** unless one of the following applies:

- **You cannot have GPL code in the environment.** Install plain
  `gwyddionpy` and get the binary by [option 2](#option-2--a-prebuilt-binary-from-a-github-release-deprecated)
  or [option 3](#option-3--build-gwyconvert-yourself). The binary then lives
  outside your site-packages, and the licenses stay separated.
- **You only ever read `.gwy` files.** Plain `gwyddionpy` is enough: a `.gwy`
  input is parsed directly and never touches the converter.
- **You are on a platform with no converter wheel** — anything other than
  Linux x86_64, macOS, and Windows x86_64. Use option 3.
- **You are packaging gwyddionpy as a library dependency.** Depend on plain
  `gwyddionpy` and let the application decide about the GPL binary. This is
  why the converter is an extra and never a hard dependency.

Installing `gwyddionpy-converter` **alone** is a valid thing to do, but it
gets you only the binary — there is no `import` in it worth having. Do that
when you want `gwyconvert` for [shell use](gwyconvert-cli.md) and nothing else.

## Setting up an environment

Either tool works; pick one and use it for the rest of this page. `uv` is a
drop-in, much faster replacement for `venv`+`pip` and is what this project's
own tooling uses.

**With `uv`:**

```bash
uv venv                     # creates .venv using a suitable Python
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

`uv venv --python 3.12` pins a specific interpreter, downloading it if it is
not already on the machine. gwyddionpy needs **Python 3.9 or newer**.

**With `venv` and `pip`:**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python3 -m pip install --upgrade pip
```

Activating is optional under `uv` — `uv pip install` finds `./.venv` by
itself — but it does mean a bare `python` is the right one afterwards.

## Option 1 — the companion wheel

**With `uv`:**

```bash
uv pip install "gwyddionpy[converter]"
```

**With `pip`:**

```bash
pip install "gwyddionpy[converter]"
```

That is all. The `[converter]` extra pulls `gwyddionpy-converter`, which
ships `gwyconvert` as package data; gwyddionpy finds it automatically, with
no environment variable to set. Skip to [Verify](#verify).

Add more extras in the same brackets — `"gwyddionpy[converter,hdf5]"` also
gets you `h5py` for the HDF5 export. The full set is `converter`, `hdf5`,
`test` and `dev`.

The extra is opt-in on purpose: a plain `pip install gwyddionpy` stays
entirely Apache-2.0, so requesting the GPL binary is always your explicit
choice.

## Option 2 — a prebuilt binary from a GitHub Release (deprecated)

> **Deprecated.** This route still works and is still tested, but it will
> be removed in a future release. Option 1 is the supported way to get a
> converter. If you are choosing now, choose option 1. If you already rely
> on this, the command prints a notice and you have until the removal to
> move across.

Useful when you want the binary without a GPL package in your environment.
With an environment already [set up](#setting-up-an-environment):

```bash
pip install gwyddionpy      # uv: uv pip install gwyddionpy

gwyddionpy-fetch-converter
```

Note the plain `gwyddionpy` here, with no `[converter]`: this route installs
the Apache-2.0 package only, and the binary lands outside site-packages.

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
python3 -m venv .venv          # or: uv venv
source .venv/bin/activate
pip install gwyddionpy

# 4. Point gwyddionpy at the binary you just built
export GWYDDIONPY_CONVERT=$PWD/gwyddionpy-converter/gwyconvert
```

Set `GWYDDIONPY_CONVERT` in your shell profile to make step 4 stick across
sessions; it is the first place `find_converter()` looks after an explicit
`converter=` argument.

Package names above are Debian's and Ubuntu's. On other distributions
install the equivalents (Fedora: `gwyddion` + `gwyddion-devel`) and continue
from step 2.

To avoid distribution packages entirely, build Gwyddion itself from its
official source tarball with
[`gwyddionpy-converter/ci/build-gwyddion.sh`](../../gwyddionpy-converter/ci/build-gwyddion.sh),
the same script this project's continuous integration and release builds
use. It takes `WORK_DIR`, `PREFIX` and `GWYCONVERT_OUT` from the
environment and produces a `gwyconvert` linked against its own Gwyddion.

## Verify

```bash
python3 -c "import gwyddionpy; print(len(gwyddionpy.list_formats()), 'formats')"
```

Expect a number well over 100; ~170 is typical.

**Zero is the failure to watch for.** A converter that cannot find
Gwyddion's format plugins still starts and exits cleanly; it simply
registers nothing. If you see zero after option 3, check the `gwyddion`
package from step 1 first.

`ConverterNotFoundError` instead means no binary was found at all: check
that `GWYDDIONPY_CONVERT` points at a real file, or that step 2 actually
produced one.

Then try a real measurement file:

```bash
python3 -c "import gwyddionpy; d = gwyddionpy.load('your_scan_file'); print(list(d.channels))"
```

## Next steps

[`usage.md`](usage.md) picks up here: what `load()` returns, exporting to
JSON, HDF5, a Python `dict` or `.gwy`, and worked examples on real vendor
files.

## Using `gwyconvert` on its own

The helper binary is a normal command-line program, so a shell script or a
workflow with no Python in it can convert files directly. Its usage, exit
codes and output are described in
[`gwyconvert-cli.md`](gwyconvert-cli.md).
