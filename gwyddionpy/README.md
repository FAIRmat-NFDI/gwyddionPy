# gwyddionpy

Read any Gwyddion-supported SPM raw file (~148 vendor formats) into Python:
NumPy arrays + metadata dicts. Uses the `gwyconvert` helper binary (built
from Gwyddion's libraries) via a subprocess — pure Python otherwise. Get
`gwyconvert` via `gwyddionpy-fetch-converter` (downloads a prebuilt binary,
Linux only for now) or by building it yourself (`../docs/BUILD.md`).

```python
import gwyddionpy

data = gwyddionpy.load("scan.spm")
data.channels["Height"].data      # numpy array, physical values
data.metadata                     # vendor metadata
data.to_hdf5("scan.h5")           # optional: pip install 'gwyddionpy[hdf5]'
```

Full documentation: `../docs/` (USAGE.md, BUILD.md, TESTING.md).
