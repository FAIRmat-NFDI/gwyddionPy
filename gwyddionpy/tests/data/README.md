# Test data — provenance and licenses

Raw measurement files grouped by vendor, each with its reference
(`<file>.json`) beside it. Both are committed, so a fresh checkout can run
the format tests without fetching anything.

This is the test suite's only data source.

To add a file: drop it into the vendor directory, add an entry to
`helpers/specimens.py` with its SHA-256 checksum, capture the reference with
`python gwyddionpy/tests/make_reference.py <vendor>/<file>`, and record its
provenance below.

| File | Format / Gwyddion module | Source | License |
|------|--------------------------|--------|---------|
| `bruker_nanoscope/VGEP-15m-.0_00000.spm` | Bruker Nanoscope / `nanoscope` | own measurement (recovered from branch `FileParserInPython`) | project-internal |
| `bruker_spmlab/B3320_13_061726074638.SIG_TOPO_BKW.FLT` | Bruker SPMLab `.FLT` / `spmlabf` — same vendor as the file above, different format and different module | own measurement, Bruker Dimension Edge | project-internal |
| `jpk/sample_0.jpk` | JPK / `jpkscan` | github.com/AFM-SPM/AFMReader `tests/resources` | GPL-3.0 (repo) |
| `jpk/sample_0.jpk-qi-image` | JPK quantitative imaging / `jpkscan` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `wsxm/sample_0.stp` | WSxM / `wsxmfile` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `wsxm/sample_0.top` | WSxM / `wsxmfile` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `igor_asylum/sample_0.ibw` | Igor/Asylum / `igorfile` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `nanonis/Bias-Spectroscopy002.dat` | Nanonis spectroscopy / `nanonis_spec` — reads, but carries graph data rather than image channels | github.com/underchemist/nanonispy `tests/` | MIT |

Re-fetch AFMReader files:
`curl -sLO https://raw.githubusercontent.com/AFM-SPM/AFMReader/main/tests/resources/<name>`

**Redistribution note:** before uploading third-party files to a public
Zenodo record, confirm the data licenses (repo license ≠ data license in
general); own measurements are unproblematic.
