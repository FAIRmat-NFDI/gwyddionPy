# gwyddionPy

gwyddionPy reads raw scanning probe microscopy (SPM) files into Python. It
supports every format that [Gwyddion](http://gwyddion.net) can read (about 170
vendor formats) and returns the data as NumPy arrays with a metadata
dictionary. You can use it as a dependency in any Python project.

## How it works

The project has two parts:

- `gwyconvert` (in `gwyddionpy-converter/`) is a small command-line program
  written in C. It uses the Gwyddion libraries to convert a raw file into
  Gwyddion's own `.gwy` format.
- `gwyddionpy` (in `gwyddionpy/`) is a pure-Python package. It runs
  `gwyconvert` as a subprocess and reads the `.gwy` result into NumPy.

## Quick start

Create a virtual environment with `uv` or `venv`:

```bash
uv venv && source .venv/bin/activate                    # uv
python3 -m venv .venv && source .venv/bin/activate      # or venv + pip
```

Install the package together with the converter:

```bash
uv pip install "gwyddionpy[converter]"      # uv
pip install "gwyddionpy[converter]"         # or pip
```

### Check the installation

```bash
python3 -c "import gwyddionpy; print(len(gwyddionpy.list_formats()), 'formats')"
# 170 formats
```

If it prints `0 formats`, the converter cannot find Gwyddion's plugins. If it
raises `ConverterNotFoundError`, no converter was found. The
[installation guide](docs/user/how-to.md#verify) explains both cases.

### Load a file

```python
import gwyddionpy

data = gwyddionpy.load("path/to/scan.spm")  # Bruker, JPK, WSxM, Igor, ...
data.channels["Height"].data                # NumPy array in physical units
data.channels["Height"].si_unit_z           # "m"
data.metadata                               # vendor metadata as a dict
data.to_json("scan.json")                   # metadata only, no pixel data
data.to_hdf5("scan.h5")                     # HDF5 export (needs h5py)
data.to_gwy("scan.gwy")                     # Gwyddion's own format
```

Channel names depend on the file. Use `list(data.channels)` to see them.

## Which package do I install?

| Install | Gets you | License |
|---|---|---|
| `gwyddionpy` | The Python package alone. Reads `.gwy` files only. Vendor formats need the converter. | Apache-2.0 |
| `gwyddionpy-converter` | The prebuilt `gwyconvert` binary as package data, and nothing else worth importing. | GPL-2.0-or-later |
| **`gwyddionpy[converter]`** | **Both.** An extra of `gwyddionpy` that also installs the matching `gwyddionpy-converter`. Recommended. | both |

Install plain `gwyddionpy` instead if you cannot have GPL code in your
environment, if you only read `.gwy` files, or if you are writing a library
and want to leave the choice to the application. The
[installation guide](docs/user/how-to.md#which-package-do-i-install) covers
each case. It also describes two other ways to get the converter: a download
from a GitHub release (deprecated, Linux x86_64 only) and building it
yourself.

Converter wheels exist for Linux x86_64, macOS (Apple Silicon and Intel) and
Windows x86_64. Extras: `[converter]`, `[hdf5]`, `[test]`, `[dev]`.

## Tested platforms

`gwyddionpy[converter]` was installed and tested on these systems:

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

`load()` detects the format from the file content, so you do not need to
name it. It returns a `GwyData` object with:

- the channels, by name. Each channel holds its values in SI units (`data`),
  the scan size (`xreal`, `yreal`) and the units (`si_unit_xy`, `si_unit_z`).
- the vendor metadata (`metadata`).

You can export it in four ways. All of them use the same layout:

| Call | Produces | Pixel data? |
|---|---|---|
| `to_dict()` | plain Python `dict`, the format used by pynxtools-spm | yes |
| `to_json(path)` | UTF-8 JSON metadata sidecar | no, shape only |
| `to_hdf5(path)` | plain HDF5, gzip-compressed (needs `h5py`) | yes |
| `to_gwy(path)` | Gwyddion-native `.gwy`, openable in the GUI | yes |

The JSON and dict exports also parse the metadata values. For example,
`"-2.44 V"` becomes `{"value": -2.44, "unit": "V"}`, and nested vendor keys
become nested objects.

Of the 170 formats in the converter, 157 can be read (the rest are
export-only). Bruker Nanoscope, JPK, WSxM, Igor/Asylum and Nanonis files are
tested in this repository with real measurement files. The other formats are
tested by Gwyddion itself. See [usage.md](docs/user/usage.md) for worked
examples.

## Documentation

- [How to install](docs/user/how-to.md): set up an environment, choose a
  package, get the converter, and check the installation.
- [Using gwyddionpy](docs/user/usage.md): the data model, the exports, the
  supported formats, and worked examples.
- [The `gwyconvert` command line](docs/user/gwyconvert-cli.md): use the
  converter directly, without Python.

## License

This repository is Apache-2.0 (see [`LICENSE`](LICENSE)), **except**
`gwyddionpy-converter/`, which is GPL-2.0-or-later (see
[`gwyddionpy-converter/COPYING`](gwyddionpy-converter/COPYING)) because
`gwyconvert` links the GPL-licensed Gwyddion libraries.

`gwyddionpy` only runs the converter as a separate process. It never
imports or links it, so `gwyddionpy` stays Apache-2.0. The same holds for the
`gwyddionpy-fetch-converter` helper: it contains no GPL code, and the binary
it downloads is never included in the `gwyddionpy` wheel.
