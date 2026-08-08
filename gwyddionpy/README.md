# gwyddionpy

Read any Gwyddion-supported SPM raw file (~170 vendor formats) into Python:
NumPy arrays plus metadata dictionaries. Pure Python — the file parsing is
done by the `gwyconvert` helper binary, which is run as a subprocess.

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
