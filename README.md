# gwyddionPy

gwyddionPy reads any raw scanning probe microscopy (SPM) file that
[Gwyddion](http://gwyddion.net) supports — around 170 vendor formats — into
Python as NumPy arrays plus metadata dictionaries. Usable as a library
dependency in any Python software.


## How it works

`gwyconvert` (in `gwyddionpy-converter/`) is a C helper without a graphical user interface that links Gwyddion's libraries and converts any supported raw file to Gwyddion's
native `.gwy` format. The pure-Python package `gwyddionpy` (in
`gwyddionpy/`) runs it as a subprocess and parses the result into NumPy.


## Quick start

Create an environment, with `uv` or with `venv`:

```bash
uv venv && source .venv/bin/activate                    # uv
python3 -m venv .venv && source .venv/bin/activate      # or venv + pip
```

Install both halves:

```bash
uv pip install "gwyddionpy[converter]"      # uv
pip install "gwyddionpy[converter]"         # or pip
```

### Check it:

```bash
python3 -c "import gwyddionpy; print(len(gwyddionpy.list_formats()), 'formats')"
# 170 formats
```

Zero formats means the converter cannot find Gwyddion's plugins;
`ConverterNotFoundError` means no binary was found at all. Both are covered
in [how-to.md](docs/user/how-to.md#verify).

### Load a file

```python
import gwyddionpy

file = "path-to-file/example_file.flt"  # Bruker, JPK, WSxM, Igor, ...
data = gwyddionpy.load(file)
data.channels["Height"].data              # numpy array, physical values
data.channels["Height"].si_unit_z         # "m"
data.metadata                             # vendor metadata dict
data.to_json("scan.json")                 # metadata only, no pixel data
data.to_hdf5("scan.h5")                   # hierarchical HDF5 export
data.to_gwy("scan.gwy")                   # back to Gwyddion-native format
```

## Which package do I install?

| Install | Gets you | License |
|---|---|---|
| `gwyddionpy` | The Python package alone. Reads `.gwy`, but **no vendor format** — that needs the binary. | Apache-2.0 |
| `gwyddionpy-converter` | The prebuilt `gwyconvert` binary as package data, and nothing else worth importing. | GPL-2.0-or-later |
| **`gwyddionpy[converter]`** | **Both** — an extra on the first that depends on the second. Start here. | both |

`gwyddionpy[converter]` is not a third package; it is the same two
distributions, installed together with the version pin the release workflow
maintains. Choose plain `gwyddionpy` instead when you cannot have GPL code
in the environment, when you only ever read `.gwy` files, or when you are
depending on gwyddionpy from another library and want the application to
decide. The [installation guide](docs/user/how-to.md#which-package-do-i-install)
works through each case, plus the two other ways to get the binary: a
checksum-verified download from a GitHub Release (deprecated, linux-x86_64
only) and building it yourself against a local Gwyddion.

Converter wheels exist for Linux x86_64, macOS (Apple Silicon and Intel) and
Windows x86_64. Extras: `[converter]`, `[hdf5]`, `[test]`, `[dev]`.

## Tested platforms

`gwyddionpy[converter]` was verified on the following, via
[`PlatformCompatibility.md`](PlatformCompatibility.md):

| OS | Works |
|---|---|
| Arch Linux (rolling) | ✅ |
| Ubuntu 26.04 LTS | ✅ |
| Ubuntu 24.04 LTS | ✅ |
| Ubuntu 22.04 LTS | ✅ |
| Ubuntu 20.04 LTS | ❌ |
| Fedora 44 | ✅ |
| openSUSE Tumbleweed | ✅ |
| Debian 13 (trixie) | ✅ |
| Debian 12 (bookworm) | ✅ |
| AlmaLinux 10.2 | ✅ |
| AlmaLinux 8 | ✅ |
| Windows 11 | ✅ |

## What you get

`load()` detects the format from the file's contents — you never name it —
and returns a `GwyData`: channels by name, each an array of **physical
values in SI units** (`data`) with the scan dimensions (`xreal`, `yreal`)
and units (`si_unit_xy`, `si_unit_z`) needed to interpret them, plus the
vendor's metadata. From there, four exports sharing one layout:

| Call | Produces | Pixel data? |
|---|---|---|
| `to_dict()` | plain Python `dict` — the shape pynxtools-spm consumes | yes |
| `to_json(path)` | UTF-8 JSON metadata sidecar | no, shape only |
| `to_hdf5(path)` | plain HDF5, gzip-compressed (needs `h5py`) | yes |
| `to_gwy(path)` | Gwyddion-native `.gwy`, openable in the GUI | yes |

The JSON and dict exports parse vendor metadata as they go, so `"-2.44 V"`
arrives as `{"value": -2.44, "unit": "V"}` and nested vendor keys become
nested objects.

157 of the 170 bundled formats can be read. Bruker Nanoscope, JPK, WSxM,
Igor/Asylum and Nanonis are pinned by tests against committed measurement
files; the rest rely on Gwyddion's own coverage.
[usage.md](docs/user/usage.md) has worked examples on each.

## Documentation

- [How to install](docs/user/how-to.md) — environments with `uv` or `pip`,
  which package to choose, all three routes to the binary, and how to verify
  the result on a fresh machine.
- [Using gwyddionpy](docs/user/usage.md) — the data model, the four exports,
  format coverage, and worked examples on real vendor files.
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
