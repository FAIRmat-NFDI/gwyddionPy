# gwyddionpy

Read any raw scanning probe microscopy (SPM) file that Gwyddion supports —
around 170 vendor formats — into Python as NumPy arrays plus metadata
dictionaries. Pure Python: the parsing is done by the `gwyconvert` helper
binary, run as a subprocess.

```python
import gwyddionpy

data = gwyddionpy.load("scan.spm")
data.channels["Height"].data      # numpy array, physical values
data.metadata                     # vendor metadata
data.to_hdf5("scan.h5")           # optional: pip install 'gwyddionpy[hdf5]'
```

`gwyconvert` is installed separately, most simply with
`pip install "gwyddionpy[converter]"`. See the
[repository README](https://github.com/FAIRmat-NFDI/gwyddionPy) for the other
options and for the licensing split (this package is Apache-2.0; the
converter is GPL-2.0-or-later).
