# gwyddionPy

Read any [Gwyddion](http://gwyddion.net)-supported SPM raw file (~170 vendor
formats) into Python: NumPy arrays plus metadata dictionaries — usable as a
dependency of Python libraries and for NOMAD/FAIRmat data ingestion.

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

A small headless C helper, `gwyconvert` (in `gwyddionpy-converter/`), links Gwyddion's
libraries and converts any supported raw file to Gwyddion's native `.gwy`
format; the pure-Python package `gwyddionpy` (in `gwyddionpy/`) runs it as a
subprocess and parses the result into NumPy. No compiled Python extension —
Python version updates cannot break it.

## Installation

1. **Python package**: `pip install gwyddionpy` (extras: `[hdf5]`, `[test]`, `[dev]`).
   This stays 100% Apache-2.0 — it never pulls the GPL-licensed converter.
2. **Converter** (once per machine) — pick one:
   - **Install the companion wheel**: `pip install "gwyddionpy[converter]"`.
     Pulls `gwyddionpy-converter`, a separate GPL-2.0-or-later package that
     ships a prebuilt `gwyconvert` as package data — no download step and no
     build step. Opting in via the extra is what keeps the plain install
     above free of GPL artifacts. Linux x86_64 only for now, and not yet on
     real PyPI (TestPyPI only), so use one of the options below until it
     ships there.
   - **Fetch a prebuilt binary**: `gwyddionpy-fetch-converter`. Downloads
     `gwyconvert` from a GitHub Release into a local cache; gwyddionpy then
     finds it automatically. Never runs on its own (not on `pip install`,
     not on import), never touches apt/dnf/brew. Linux only for now — no
     release has shipped a binary yet, so this will fail with a clear error
     until one does; build it yourself (below) in the meantime.
   - **Build it yourself** (any platform, details in `docs/BUILD.md`):
     install Gwyddion dev headers
     (`sudo apt install libgwyddion20-dev libgtk2.0-dev libfftw3-dev`),
     then `make -C gwyddionpy-converter` and put `gwyconvert` on your `PATH`.

## Documentation

See `docs/`: USAGE, BUILD, ARCHITECTURE, TESTING, MAINTENANCE,
TROUBLESHOOTING, EXTENDING, CHANGELOG.

## License

Apache-2.0 (see `LICENSE`) for this repository, **except**
`gwyddionpy-converter/`, which is GPL-2.0-or-later (see
`gwyddionpy-converter/COPYING`) because it links the
GPL-licensed Gwyddion libraries. The Python package communicates with the
converter only via subprocess and stays Apache-2.0 — including the
`gwyddionpy-fetch-converter` helper itself, which is plain Apache-2.0
Python containing no GPL code. The prebuilt `gwyconvert` binary it
downloads is the actual GPL-2.0-or-later artifact; it's distributed
separately as a GitHub Release asset, never bundled into the PyPI wheel.
