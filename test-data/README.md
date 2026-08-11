# Test data — provenance and licenses

These files are **not committed to git** (size); this README is. Re-fetching
is documented per file. Long-term plan: host on Zenodo with a pooch registry
(docs/TESTING.md). Verified results: tests/test_real_files.py.

| File | Format / Gwyddion module | Source | License |
|------|--------------------------|--------|---------|
| `VGEP-15m-.0_00000.spm` | Bruker Nanoscope / `nanoscope` | own measurement (recovered from branch `FileParserInPython`) | project-internal |
| `SB04-MG1.0_00000.spm.txt` | Bruker header dump (text) | own measurement | project-internal |
| `sample_0.jpk` | JPK / `jpkscan` | github.com/AFM-SPM/AFMReader `tests/resources` | GPL-3.0 (repo) |
| `sample_0.jpk-qi-image` | JPK QI / `jpkscan` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `sample_0.stp` | WSxM / `wsxmfile` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `sample_0.top` | WSxM / `wsxmfile` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `sample_0.ibw` | Igor/Asylum / `igorfile` | github.com/AFM-SPM/AFMReader | GPL-3.0 (repo) |
| `Bias-Spectroscopy002.dat` | Nanonis spectroscopy / `nanonis_spec` — loads, but 0 image channels (graph data; not yet in the gwyddionpy model) | github.com/underchemist/nanonispy `tests/` | MIT |

Re-fetch AFMReader files:
`curl -sLO https://raw.githubusercontent.com/AFM-SPM/AFMReader/main/tests/resources/<name>`

**Redistribution note:** before uploading third-party files to a public
Zenodo record, confirm the data licenses (repo license ≠ data license in
general); own measurements are unproblematic.
