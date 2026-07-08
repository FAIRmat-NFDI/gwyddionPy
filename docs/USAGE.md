# Using gwybridge

> Status note: sections are marked *(implemented)* / *(planned)* and the
> marks are updated as work lands.

## Command line — `gwyconvert` *(implemented; 170 formats on Ubuntu 22.04 / Gwyddion 2.60)*

```bash
gwyconvert INPUT OUTPUT.gwy      # convert any supported raw file to .gwy
gwyconvert --list-formats        # JSON list of supported formats on stdout
```

Exit codes: `0` success, `1` unsupported/unreadable file (details on stderr),
`2` bad invocation.

## Python API *(implemented; 16/16 tests + real Bruker .spm verified end-to-end)*

Native `.gwy` files load directly without the converter. All other formats
go through `gwyconvert`.

```python
import gwybridge

data = gwybridge.load("scan.spm")     # any of ~148 Gwyddion-supported formats
```

`load()` returns a `GwyData` object:

| Attribute | Meaning |
|-----------|---------|
| `data.channels` | dict: channel name → `Channel` |
| `data.metadata` | dict: vendor metadata as flat string key–value pairs |
| `data.source_format` | name of the Gwyddion module that parsed the file |

Each `Channel`:

| Attribute | Meaning |
|-----------|---------|
| `ch.data` | `numpy.ndarray` (float64, shape `(rows, cols)`), physical values |
| `ch.xreal`, `ch.yreal` | physical extents of the scan |
| `ch.si_unit_xy`, `ch.si_unit_z` | SI unit strings, e.g. `"m"`, `"V"` |
| `ch.meta` | per-channel metadata dict |

Capability query:

```python
gwybridge.list_formats()   # [{"name": "nanoscope", "description": ..., "extensions": [...]}, ...]
```

Errors are typed: `ConverterNotFoundError` (gwyconvert not installed/found),
`UnsupportedFormatError`, `ConversionError` (parser failed; carries stderr).
The converter is located via the `GWYBRIDGE_CONVERT` environment variable
first, then `$PATH`.

## Exports *(HDF5 + .gwy implemented; NeXus planned)*

```python
data.to_hdf5("scan.h5")    # plain HDF5: channels as compressed datasets,
                           # dims/units as attributes
data.to_hdf5("scan.h5", hierarchical_meta=False)   # flat metadata attrs
data.to_gwy("scan.gwy")    # Gwyddion-native file; opens in the Gwyddion GUI
```

HDF5 metadata is hierarchical by default: vendor keys with numeric group
prefixes (`2:AmplitudeLimit`) or `/`-paths (`Samps/line`) become nested
groups (`meta/group 2/…`, `meta/Samps/…`); plain keys stay as attributes of
`meta` itself.

NeXus/NXspm output is produced through the pynxtools-spm reader adapter, not
by gwybridge itself — gwybridge supplies the dict, pynxtools writes the .nxs
(which is itself an HDF5 file with the NeXus hierarchy).
