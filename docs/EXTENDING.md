# Extending gwybridge

## Adding a new export format

Exports are methods/functions consuming a `GwyData` object — they never touch
the C side. Pattern: add `gwybridge/export/<format>.py` with a
`write(data: GwyData, path)` function, wire a thin `GwyData.to_<format>()`
method, add tests with a real sample file. Candidates: NeXus (via
pynxtools-spm, the priority), Zarr, plain NumPy `.npz`.

## NOMAD / NeXus integration (the strategic extension)

FAIRmat ships `pynxtools-spm`, the pynxtools reader plugin for SPM data
targeting the NXspm application definitions. The intended shape:

```
gwybridge.load(raw) → dict → pynxtools-spm reader adapter → NXspm .nxs → NOMAD
```

That adapter (a reader that accepts "whatever gwybridge emits") instantly
gives NOMAD ingestion of every Gwyddion-supported format. Keep the adapter in
the pynxtools-spm codebase, not here — gwybridge stays schema-agnostic.

## Supporting a new raw file format

Don't add parsers here. New formats belong upstream in Gwyddion
(`gwyddion/modules/file/*.c`) — then gwybridge inherits them automatically
via the module registry. This is the entire point of the architecture.
If upstreaming is too slow, a patched module in the submodule build
(BUILD.md Route 2, `vendor/gwyddion`) is the interim path.

## Converter features worth adding later

- `--meta-only`: dump metadata as JSON without reading image data (fast
  indexing/crawling use case for repositories).
- stdout streaming (`gwyconvert INPUT -` piping .gwy bytes) to skip the temp
  file.
- Batch mode (`gwyconvert *.spm --outdir d/`) amortizing process startup.
- Volume/spectra data: Gwyddion containers can hold `GwyBrick` (volume) and
  graph/spectra objects; `gwyfile` exposes them — extend `GwyData` beyond 2-D
  channels when a use case appears.

## Performance escape hatch

If subprocess-per-file ever becomes a bottleneck (thousands of files), the
design upgrade is a persistent converter process speaking length-prefixed
.gwy blobs over a pipe — **not** in-process bindings (see Decision D1).
