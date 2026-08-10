# gwyddionPy

Read any raw scanning probe microscopy (SPM) file that
[Gwyddion](http://gwyddion.net) supports — around 170 vendor formats — into
Python as NumPy arrays plus metadata dictionaries. Usable as a library
dependency and for NOMAD/FAIRmat data ingestion.

```python
import gwyddionpy

data = gwyddionpy.load("scan.spm")         # Bruker, JPK, WSxM, Igor, ...
data.channels["Height"].data              # numpy array, physical values
data.channels["Height"].si_unit_z         # "m"
data.metadata                             # vendor metadata dict
data.to_hdf5("scan.h5")                   # hierarchical HDF5 export
data.to_gwy("scan.gwy")                   # back to Gwyddion-native format
```

## How it works

A small headless C helper, `gwyconvert` (in `gwyddionpy-converter/`), links
Gwyddion's libraries and converts any supported raw file to Gwyddion's
native `.gwy` format. The pure-Python package `gwyddionpy` (in
`gwyddionpy/`) runs it as a subprocess and parses the result into NumPy.

There is no compiled Python extension anywhere, so a new Python release
cannot break the package. That subprocess boundary is also the license
boundary — see [License](#license).

## Installation

Two pieces, installed separately.

**1. The Python package**

```bash
pip install gwyddionpy            # extras: [hdf5], [test], [dev]
```

Stays 100% Apache-2.0; it never pulls the GPL-licensed converter on its own.

**2. The converter**, once per machine — pick one:

- **The companion wheel** (recommended):
  `pip install "gwyddionpy[converter]"` pulls `gwyddionpy-converter`, a
  separate GPL-2.0-or-later distribution shipping a prebuilt `gwyconvert` as
  package data. Nothing to download or build afterwards, and gwyddionpy finds
  it automatically. Wheels exist for Linux x86_64, macOS (Apple Silicon and
  Intel) and Windows x86_64.
- **A prebuilt binary from a GitHub Release** (deprecated):
  `gwyddionpy-fetch-converter` downloads and checksum-verifies `gwyconvert`
  into a per-user cache, which gwyddionpy then searches automatically.
  Useful when you want the binary without adding a GPL package to the
  environment. Published for linux-x86_64 only. It never runs by itself —
  not on `pip install`, not on import — and never touches apt, dnf or brew.
- **Build it yourself**, on any platform: install Gwyddion's development
  headers, run `make -C gwyddionpy-converter`, and put the resulting
  `gwyconvert` on your `PATH`.

Both packages are currently published to **TestPyPI** only, which needs
extra index flags on every `pip install`.

## Documentation

- [How to install](docs/user/how-to.md) — all three routes, and how to
  verify the result on a fresh machine.
- [The `gwyconvert` command line](docs/user/gwyconvert-cli.md) — using the
  helper binary directly, from a shell script or a workflow with no Python
  in it.

## License

This repository is Apache-2.0 (see [`LICENSE`](LICENSE)), **except**
`gwyddionpy-converter/`, which is GPL-2.0-or-later (see
[`gwyddionpy-converter/COPYING`](gwyddionpy-converter/COPYING)) because
`gwyconvert` links the GPL-licensed Gwyddion libraries.

The two never mix in one process. `gwyddionpy` only ever executes the
converter as a subprocess, never imports or links it, so it stays
Apache-2.0. That includes the `gwyddionpy-fetch-converter` helper: it is
plain Apache-2.0 Python with no GPL code in it, and the binary it downloads
is distributed separately — as a GitHub Release asset or as the
`gwyddionpy-converter` wheel — never bundled into the `gwyddionpy` wheel.
