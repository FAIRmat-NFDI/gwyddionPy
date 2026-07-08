# gwybridge Architecture

gwybridge makes Gwyddion's ~148 SPM file-format parsers usable from Python.
It deliberately contains **two small components on either side of a process
boundary**, instead of one big binding layer.

## Components

### 1. `gwyconvert` (C, `converter/`)

A headless command-line program linking Gwyddion's libraries:

- `libgwyddion` — core types (GwyContainer, GwySIUnit, serialization)
- `libprocess` — GwyDataField (the 2-D data array type)
- `libgwymodule` — the module registry that owns all file-format parsers

It does exactly one job: `gwyconvert INPUT OUTPUT.gwy` loads any supported raw
file through `gwy_file_load(..., GWY_RUN_NONINTERACTIVE, ...)` and serializes
the resulting `GwyContainer` to a `.gwy` file via `gwy_file_save()`. A second
mode, `gwyconvert --list-formats`, prints the registered formats as JSON.

Headless operation follows the pattern of
`vendor/gwyddion/gwyddion/thumbnailer/gwyddion-thumbnailer.c` (in the
optional source submodule), which already performs
GUI-less file loading (GTK libraries must be installed, but no display is
required).

### 2. `gwybridge` (Python, `python/`)

A pure-Python package (no compiled extension) that:

1. locates `gwyconvert` (env var `GWYBRIDGE_CONVERT`, then `$PATH`),
2. runs it as a subprocess into a temporary `.gwy` file,
3. parses that file with the PyPI [`gwyfile`](https://pypi.org/project/gwyfile/)
   package into NumPy arrays,
4. presents a `GwyData` object: `channels` (name → array + physical dims +
   SI units) and `metadata` (flat string dict, as stored by Gwyddion under
   `/N/meta`),
5. offers exports: `to_hdf5()` now, a pynxtools-spm/NeXus adapter later.

## Data flow

```
scan.spm ──gwyconvert──► /tmp/xxx.gwy ──gwyfile──► GwyData(channels, metadata)
                                                        │
                                                        ├─ .to_hdf5("scan.h5")
                                                        └─ pynxtools-spm → scan.nxs
```

## Why a subprocess and not bindings?

- **Python-version immunity.** Nothing links CPython; Python 3.15 will not
  break anything. The old `pygwy` bindings died exactly because they were
  welded to Python 2 + PyGTK.
- **Fault isolation.** A crashing vendor parser kills the subprocess, not the
  host Python process (relevant: these parsers ingest untrusted binary files).
- **License isolation.** Gwyddion is GPL-2.0+. Only `gwyconvert` links it;
  the Python package communicates via files/pipes and can carry its own license.
- **No GLib type-system gymnastics** in Python (module registry init, GObject
  ownership) that made Option B (ctypes/cffi) fragile.

The cost — one process spawn and one temp file per load — is negligible
against SPM file sizes (KBs to a few MBs).

## Why `.gwy` as the wire format?

It is Gwyddion's native serialization of `GwyContainer`: stable for ~20 years,
documented, lossless (data fields, physical dimensions, SI units, per-channel
metadata all survive), and already parseable in Python by `gwyfile`. Inventing
a JSON/msgpack schema would mean maintaining a second format for zero gain.

## Relation to the Gwyddion source

The full Gwyddion source tree is available as the **optional** git submodule
`vendor/gwyddion` (pinned to a known commit of the project's git mirror of
upstream; fetch with `git submodule update --init vendor/gwyddion`). v1 links
against the *system-installed* Gwyddion dev package; the submodule source is
the API reference and the fallback build route if patches to file modules
become necessary. Normal users never need to initialize it.
