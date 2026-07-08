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

A small headless C helper, `gwyconvert` (in `converter/`), links Gwyddion's
libraries and converts any supported raw file to Gwyddion's native `.gwy`
format; the pure-Python package `gwyddionpy` (in `python/`) runs it as a
subprocess and parses the result into NumPy. No compiled Python extension —
Python version updates cannot break it.

## Installation

Two parts (details in `docs/BUILD.md`):

1. **Converter** (once per machine): install Gwyddion dev headers
   (`sudo apt install libgwyddion20-dev libgtk2.0-dev libfftw3-dev`),
   then `make -C converter` and put `gwyconvert` on your `PATH`.
2. **Python package**: `pip install ./python` (extras: `[hdf5]`, `[test]`).

## Documentation

See `docs/`: USAGE, BUILD, ARCHITECTURE, TESTING, MAINTENANCE,
TROUBLESHOOTING, EXTENDING, CHANGELOG.

## License

Apache-2.0 (see `LICENSE`) for this repository, **except** `converter/`,
which is GPL-2.0-or-later (see `converter/COPYING`) because it links the
GPL-licensed Gwyddion libraries. The Python package communicates with the
converter only via subprocess and stays Apache-2.0.
