# Using gwyddionpy

This page is about the Python package: what `load()` gives you, what you can
turn it into, and what to expect from a given vendor file. If you have not
installed anything yet, start at [how-to.md](how-to.md) and come back.

Everything here is run against the measurement files committed under
`gwyddionpy/tests/data/`, so you can paste any of it into a checkout and get
the same numbers.

## Contents

- [The one call that matters](#the-one-call-that-matters)
- [What you get back](#what-you-get-back)
- [Export formats](#export-formats)
- [Working with `.gwy`](#working-with-gwy)
- [Which formats are supported best](#which-formats-are-supported-best)
- [Three worked examples](#three-worked-examples)
- [When something fails](#when-something-fails)
- [What this buys you as a scientist](#what-this-buys-you-as-a-scientist)

## The one call that matters

```python
import gwyddionpy

data = gwyddionpy.load("gwyddionpy/tests/data/wsxm/sample_0.top")
```

`load()` takes a path to a raw file in any format Gwyddion can read, runs the
`gwyconvert` helper as a subprocess to turn it into Gwyddion's native `.gwy`,
parses that, and hands back a `GwyData`. The intermediate `.gwy` lives in a
temporary directory that is deleted on the way out — you never see it unless
you ask for one with [`to_gwy()`](#working-with-gwy).

You do not tell it the format. Gwyddion detects the format from the file's
own contents, so an unhelpful or wrong extension is not a problem.

Two keyword arguments, both rarely needed:

```python
data = gwyddionpy.load(
    "scan.spm",
    converter="/opt/gwyconvert",   # a specific binary, instead of the discovered one
    timeout=600,                   # seconds; default 300
)
```

`timeout` is a hang guard rather than a performance budget — raise it only if
a genuinely huge file is being cut off.

## What you get back

`GwyData` holds channels by name, plus the name of the Gwyddion module that
read the file:

```python
>>> data.source_format
'wsxmfile'
>>> list(data.channels)
['Topography']
```

Each entry is a `Channel` — a NumPy array with the physical dimensions and
units needed to interpret it:

```python
>>> channel = data.channels["Topography"]
>>> channel.data.shape, channel.data.dtype
((512, 512), dtype('float64'))
>>> channel.xreal, channel.yreal      # physical width and height
(5e-07, 5e-07)
>>> channel.si_unit_xy, channel.si_unit_z
('m', 'm')
```

| Attribute | Meaning |
|---|---|
| `name` | The channel name as the vendor wrote it |
| `data` | `numpy.ndarray`, shape `(rows, cols)`, **physical values** — not raw counts |
| `xreal`, `yreal` | Physical width and height of the scanned area, in `si_unit_xy` |
| `si_unit_xy` | Unit of the lateral dimensions, e.g. `"m"` |
| `si_unit_z` | Unit of the values in `data`, e.g. `"m"`, `"V"`, `"deg"` |
| `meta` | That channel's vendor metadata, as a flat `dict[str, str]` |

Values are already in SI base units, which is why a 500 nm scan reports
`xreal` as `5e-07` and heights come out around `1e-08`. Nothing is scaled for
display; multiply by `1e9` yourself when you want nanometres.

### Metadata

`channel.meta` is one channel's metadata. `data.metadata` is the union across
all channels, which is what you usually want when a file's channels share one
instrument header:

```python
>>> len(data.metadata)
89
>>> data.metadata["Control::Set Point"]
'-2.44 V'
>>> data.metadata["General Info::Acquisition channel"]
'Topography'
```

At this level every value is the vendor's own string, unparsed. The
[exports](#export-formats) are where `"-2.44 V"` becomes a number and a unit.

> On a key collision between channels, the first channel in file order wins.
> Per-channel values always stay intact in `channel.meta`.

## Export formats

Four exports, all reached from `GwyData`. They share one layout, so moving
between them costs nothing:

| Call | Produces | Pixel data? | Needs |
|---|---|---|---|
| `to_dict()` | plain Python `dict` | yes, as `ndarray` | — |
| `to_json(path)` | UTF-8 JSON file | no, shape only | — |
| `to_hdf5(path)` | HDF5 file | yes, gzip-compressed | `h5py` |
| `to_gwy(path)` | Gwyddion-native `.gwy` | yes | — |

### `to_dict()` — the in-memory form

No file I/O, no extra dependencies, and the shape downstream readers such as
pynxtools-spm consume:

```python
>>> payload = data.to_dict()
>>> list(payload)
['source_format', 'channels']
>>> list(payload["channels"]["Topography"])
['name', 'xreal', 'yreal', 'si_unit_xy', 'si_unit_z', 'data', 'meta']
```

`meta` here is no longer flat strings. Keys that encode structure are
unfolded into nested dicts, and a value written as `"<number> <unit>"` is
split into `{"value": ..., "unit": ...}`:

```python
>>> payload["channels"]["Topography"]["meta"]["Control::Set Point"]
{'value': -2.44, 'unit': 'V'}
>>> payload["channels"]["Topography"]["meta"]["Control::Signal Gain"]
1
```

Pass `hierarchical_meta=False` to skip all of that and get the vendor's flat
keys and raw strings instead — the right choice when you are matching against
an instrument manual rather than computing with the values.

### `to_json()` — the metadata sidecar

Same layout as `to_dict()`, with each channel's `data` array replaced by its
`shape`. The result describes a measurement without being a second copy of
it, so it stays small enough to read, diff and commit:

```python
data.to_json("sample_0.top.json")
```

```json
{
  "source_format": "wsxmfile",
  "channels": {
    "Topography": {
      "name": "Topography",
      "xreal": 5e-07,
      "yreal": 5e-07,
      "si_unit_xy": "m",
      "si_unit_z": "m",
      "shape": [512, 512],
      "meta": {
        "Control::Set Point": { "value": -2.44, "unit": "V" },
        "Control::X-Frequency": { "value": 1.085, "unit": "Hz" },
        "Control::Signal Gain": 1
      }
    }
  }
}
```

Written as UTF-8 with `ensure_ascii=False`, because vendor metadata is full
of µ, ° and Å. `NaN` and the infinities have no JSON literal, so they are
written as the strings `"NaN"`, `"Infinity"` and `"-Infinity"`; `float()`
parses each one back.

**If you want the arrays too, use HDF5** — `to_json` deliberately drops them.

### `to_hdf5()` — everything, in one portable file

```bash
pip install "gwyddionpy[hdf5]"     # or: uv pip install "gwyddionpy[hdf5]"
```

```python
data.to_hdf5("sample.h5")
```

One group per channel under `/channels`, the image as a compressed `data`
dataset, dimensions and units as attributes, vendor metadata under `meta`:

```
/                          source_format = "wsxmfile"
/channels/Topography       name, xreal, yreal, si_unit_xy, si_unit_z
/channels/Topography/data              (512, 512) float64, gzip
/channels/Topography/meta/Control::Set Point   = -2.44, attrs: unit = "V"
```

This is plain HDF5, not NeXus — mapping to a NeXus application definition is
pynxtools-spm's job. `compression="gzip"` by default; pass `compression=None`
to turn it off, or `hierarchical_meta=False` for flat string attributes.

A channel named `A/B` is stored as `A_B`, since `/` cannot appear in an HDF5
group name. The `name` attribute always keeps the original.

## Working with `.gwy`

`.gwy` is Gwyddion's own container format, and gwyddionpy handles it at both
ends.

**Getting one.** `to_gwy()` writes the parsed data back out as `.gwy`:

```python
data = gwyddionpy.load("gwyddionpy/tests/data/wsxm/sample_0.top")
data.to_gwy("sample.gwy")           # now open it in Gwyddion's GUI
```

That is the practical route from a vendor format Gwyddion's GUI opens
awkwardly, or from a batch job, into a file you can inspect by hand. You can
also produce one without Python at all — `gwyconvert scan.spm scan.gwy`, see
[gwyconvert-cli.md](gwyconvert-cli.md).

**Reading one.** Pass it to `load()` like anything else:

```python
>>> back = gwyddionpy.load("sample.gwy")
>>> list(back.channels)
['Topography']
>>> np.array_equal(back.channels["Topography"].data, data.channels["Topography"].data)
True
```

Two things worth knowing about the round trip:

- **The converter is not involved.** A `.gwy` input is parsed directly, so
  reading one works even with no `gwyconvert` installed at all. This is the
  one case where gwyddionpy is useful on its own.
- **`source_format` comes back as `None`**, precisely because no converter
  module claimed the file. The pixel data and units survive; that one
  provenance field does not. Keep the original raw file, or the JSON
  sidecar, if provenance matters to you.

If you already hold a `.gwy` path and want to skip the extension check,
`gwyddionpy.parse_gwy(path)` is the same code `load()` dispatches to.

## Which formats are supported best

```python
>>> len(gwyddionpy.list_formats())
170
```

`list_formats()` returns one dict per format, with `name`, `description`,
`can_load`, `can_save` and `detectable`. Of the 170 in the current bundle,
**157 can be read** — the rest are export-only.

```python
>>> [f for f in gwyddionpy.list_formats() if f["name"] == "jpkscan"]
[{'name': 'jpkscan', 'description': 'JPK image scans (.jpk, .jpk-qi-image)',
  'can_load': True, 'can_save': False, 'detectable': True}]
```

Support comes in tiers. Everything Gwyddion reads, gwyddionpy reads — but
only some of it is pinned by tests in this repository:

**Tier 1 — covered by the test suite.** A committed measurement file, a
committed reference of everything reading it should produce, and a test that
compares the two on every CI run. Regressions in these are caught before you
see them:

| Vendor | Module | Specimen | Yields |
|---|---|---|---|
| Bruker Nanoscope | `nanoscope` | `.spm` | 8 channels, 512×512 |
| JPK | `jpkscan` | `.jpk`, `.jpk-qi-image` | 10 channels, 256×256 |
| WSxM | `wsxmfile` | `.top`, `.stp` | 1 channel, 512×512 |
| Igor / Asylum | `igorfile` | `.ibw` | 8 channels, 512×512 |
| Nanonis spectroscopy | `nanonis_spec` | `.dat` | reads, but see below |

**Tier 2 — everything else Gwyddion reads.** Around 150 further formats,
exercised by Gwyddion's own test suite rather than by this project. They work;
they are just not guarded here. Bringing one up to tier 1 costs a file and an
entry in `gwyddionpy/tests/helpers/specimens.py`, and contributions of vendor
files are welcome.

**A known limit: image channels only.** The data model is 2-D channels, so a
file carrying spectra or curves rather than images loads successfully and
reports **zero channels**:

```python
>>> spec = gwyddionpy.load("gwyddionpy/tests/data/nanonis/Bias-Spectroscopy002.dat")
>>> spec.source_format, list(spec.channels)
('nanonis_spec', [])
```

Nothing failed there. Gwyddion parsed the file into graph data, which this
data model does not yet represent. Check `if not data.channels:` before you
assume a file gave you images.

## Three worked examples

### 1. WSxM — a single-channel topography scan

The simplest shape a file comes in: one image, one set of units.

```python
import numpy as np
import gwyddionpy

data = gwyddionpy.load("gwyddionpy/tests/data/wsxm/sample_0.top")
topo = data.channels["Topography"]

heights_nm = topo.data * 1e9                       # si_unit_z is "m"
pixel_nm = topo.xreal / topo.data.shape[1] * 1e9

print(f"module         {data.source_format}")
print(f"image          {topo.data.shape[0]}x{topo.data.shape[1]} px")
print(f"pixel size     {pixel_nm:.3f} nm")
print(f"peak-to-valley {np.ptp(heights_nm):.1f} nm")
print(f"RMS roughness  {heights_nm.std():.2f} nm")
print(f"setpoint       {data.metadata['Control::Set Point']}")
```

```
module         wsxmfile
image          512x512 px
pixel size     0.977 nm
peak-to-valley 59.7 nm
RMS roughness  15.94 nm
setpoint       -2.44 V
```

Note the two conversions doing real work: `si_unit_z` tells you the array is
in metres, and `xreal / shape[1]` is the pixel size — the file never stores
that number directly.

### 2. Bruker Nanoscope — many channels, 875 metadata keys

Multi-channel files are where naming matters. Bruker repeats channel names
across scan passes, so gwyddionpy disambiguates with a ` (n)` suffix:

```python
data = gwyddionpy.load(
    "gwyddionpy/tests/data/bruker_nanoscope/VGEP-15m-.0_00000.spm"
)

print(data.source_format)          # nanoscope
print(list(data.channels))
# ['ZSensor', 'AmplitudeError', 'Phase', 'ZSensor (2)',
#  'AmplitudeError (2)', 'Phase (2)', 'AmplitudeActual', 'DeflectionActual']

for name, ch in data.channels.items():
    print(f"{name:22} {ch.data.shape}  z in {ch.si_unit_z!r}")

print(len(data.metadata), "metadata keys")     # 875
```

With 875 keys, the flat form is unusable by hand. The hierarchical export
groups them the way the instrument wrote them — Nanoscope's `N:` prefixes
become `group N`:

```python
from gwyddionpy.export.json import to_metadata_dict

meta = to_metadata_dict(data)["channels"]["ZSensor"]["meta"]
print(list(meta)[:5])
# ['group 1', 'group 2', 'group 3', 'group 4', 'group 5']
print(meta["group 2"]["AFMSetDeflection"])
# {'value': 0.5, 'unit': 'V'}
```

`to_metadata_dict()` is the same payload `to_json()` writes, without touching
the disk — useful when you are feeding a database rather than a file.

### 3. JPK — batch conversion to JSON sidecars

The shape of most ingestion jobs: walk a directory, convert what loads, keep
going past what does not.

```python
from pathlib import Path
import gwyddionpy

raw_dir = Path("gwyddionpy/tests/data/jpk")
out_dir = Path("converted")
out_dir.mkdir(exist_ok=True)

for path in sorted(raw_dir.glob("sample_0.jpk*")):
    if path.suffix == ".json":
        continue
    try:
        data = gwyddionpy.load(path)
    except gwyddionpy.UnsupportedFormatError:
        print(f"skip  {path.name}: no Gwyddion module reads this")
        continue
    except gwyddionpy.ConversionError as exc:
        print(f"fail  {path.name}: {exc}")
        continue

    # Named off path.name, not path.stem: ".jpk-qi-image" is one suffix, so
    # both specimens share the stem "sample_0" and would collide.
    data.to_json(out_dir / f"{path.name}.json")     # metadata sidecar
    data.to_gwy(out_dir / f"{path.name}.gwy")       # openable in Gwyddion
    print(f"ok    {path.name}: {data.source_format}, "
          f"{len(data.channels)} channels")
```

```
ok    sample_0.jpk: jpkscan, 10 channels
ok    sample_0.jpk-qi-image: jpkscan, 6 channels
```

Catching `UnsupportedFormatError` before `ConversionError` matters: the first
is a subclass of the second, so the general clause would otherwise swallow
both and you would lose the distinction between "not a format we read" and
"something actually went wrong".

## When something fails

Every exception subclasses `GwyddionPyError`, so one `except` clause catches
the lot when you do not care which:

| Exception | Means | Do |
|---|---|---|
| `ConverterNotFoundError` | No `gwyconvert` binary found | `pip install "gwyddionpy[converter]"`, or set `GWYDDIONPY_CONVERT` |
| `UnsupportedFormatError` | No Gwyddion module claimed the file | Check the file is complete and is what its name says |
| `ConversionError` | The converter ran and failed | Read the message; it carries the converter's stderr |
| `ConverterFetchError` | Downloading a prebuilt binary failed | Network or checksum problem; see [how-to.md](how-to.md) |
| `FileNotFoundError` | The path does not exist | Standard library, raised before anything else runs |

`UnsupportedFormatError` is deliberately a subclass of `ConversionError` —
order your `except` clauses narrowest first.

One failure mode is not an exception: **`list_formats()` returning zero**. A
converter that cannot find Gwyddion's format plugins starts and exits
cleanly, having registered nothing. If you see 0 instead of ~170, the
installation is at fault, not the file — see
[how-to.md § Verify](how-to.md#verify).

## What this buys you as a scientist

The unglamorous part of SPM analysis is that every instrument writes its own
format, and the reader you find for one vendor rarely agrees with the reader
for the next about units, orientation or what the metadata keys mean.
Gwyddion has spent two decades absorbing that problem across ~170 formats;
gwyddionpy is a way to reach it from Python without leaving NumPy.

In practice that means:

- **One code path for a mixed dataset.** Files from four instruments read
  through the same `load()` and arrive as arrays in SI units, so a roughness
  or grain analysis written once runs over all of them.
- **Metadata you can compute with.** `"-2.44 V"` becomes `-2.44` and `"V"`,
  which is the difference between a value you can filter a dataset on and a
  string you have to eyeball.
- **Batch work Gwyddion's GUI is not for.** Hundreds of files, converted,
  summarised and archived without a window opening.
- **A path to FAIR archival.** The `to_json()` sidecar and the HDF5 export
  are structured records of a measurement, and pynxtools-spm consumes the
  `to_dict()` layout on its way to NeXus.
- **An exit back to the GUI.** `to_gwy()` means the interactive tools —
  levelling, grain marking, step-height fitting — stay available for the
  files that turn out to need a human eye.

What it does not do is analyse anything for you. There is no levelling, no
plane correction, no grain detection here; those live in Gwyddion itself or
in whatever you write on top of the arrays. This package's job ends where
NumPy's begins.

## See also

- [how-to.md](how-to.md) — installing gwyddionpy and the converter.
- [gwyconvert-cli.md](gwyconvert-cli.md) — the helper binary on its own, for
  shell scripts and workflows with no Python in them.
