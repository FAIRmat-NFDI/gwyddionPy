# gwybridge

Read any Gwyddion-supported SPM raw file (~148 vendor formats) into Python:
NumPy arrays + metadata dicts. Uses the `gwyconvert` helper binary (built
from Gwyddion's libraries) via a subprocess — pure Python otherwise.

```python
import gwybridge

data = gwybridge.load("scan.spm")
data.channels["Height"].data      # numpy array, physical values
data.metadata                     # vendor metadata
data.to_hdf5("scan.h5")           # optional: pip install 'gwybridge[hdf5]'
```

Full documentation: `../docs/` (USAGE.md, BUILD.md, TESTING.md).
