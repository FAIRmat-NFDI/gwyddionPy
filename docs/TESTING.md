# Testing Strategy — real raw files, no mocks

Goal: full parsing tests of the Python package against **real vendor raw
files**, deterministic, runnable offline for the common case, without bloating
git history with binaries. (Project rule: no mocks — a fake parser proves
nothing about parsing.)

## Where raw files come from

**The Gwyddion source tree ships none** (verified 2026-07-07: no vendor raw
files anywhere in `gwyddion/`). Sources we use instead:

1. **Own measurements** — Bruker `.spm` files in `test-data/` (untracked;
   provenance and re-fetch instructions in `test-data/README.md`).
2. **gwyddion.net sample downloads** — mostly native `.gwy` samples; useful
   for testing the Python-side `.gwy` parsing, not the vendor modules.
3. **Test suites of open-source SPM readers** (check each license before
   copying). Best found so far: **AFM-SPM/AFMReader** `tests/resources`
   (JPK, WSxM, Igor, Bruker, Asylum .asd — used 2026-07-07, see
   ../test-data/README.md); also nanonispy (Nanonis `.dat`), pySPM (Bruker
   headers), spym (RHK), NSFopen (Nanosurf `.nid`).
4. **Zenodo / materials-science repositories** — published AFM/STM datasets
   with DOIs; the FAIR-friendly source for corpus growth.

## Three tiers of test data

### Tier 1 — committed micro-fixtures (always run, offline, fast)
Tiny files (< ~1 MB total) in `python/tests/data/`: the smallest real vendor
files we can find or truncate while remaining parseable, plus intentionally
broken files for error-path tests (garbage bytes, empty file, wrong magic).

### Tier 2 — fetched corpus (real, full-size files)
Full-size real files are **not committed**. They are downloaded on demand with
[`pooch`](https://www.fatiando.org/pooch/) — the standard scientific-Python
test-data fetcher (used by SciPy, scikit-image): a registry in the test suite
maps `filename → SHA256 → URL`, downloads verify the hash, and files cache in
`~/.cache/gwybridge-tests/` so each machine downloads once.

Hosting: upload the corpus (starting with our two 16 MB Bruker files) to a
**Zenodo record** (DOI, permanent, versioned — fits the NOMAD/FAIR ethos) or,
interim, to a GitHub Release asset of this fork. Growing the corpus = upload
file + add one registry line.

### Tier 3 — golden expectations (committed, small)
For every corpus file, a committed YAML/JSON snapshot of what parsing must
yield: channel names, array shapes, dtypes, SI units, physical extents, and
array statistics (mean/std/min/max to ~6 significant digits), plus selected
metadata keys. Tests parse the real file and compare against the snapshot —
deterministic, mock-free regression protection. A helper script
(`tests/make_golden.py`) regenerates snapshots when a change is *intended*;
diffs then show up in code review.

## Test layout (Phase 4)

```
python/tests/
├── data/                  # Tier 1 micro-fixtures (committed)
├── golden/                # Tier 3 expectation snapshots (committed)
├── registry.txt           # Tier 2 pooch registry: name  sha256  url
├── conftest.py            # fixtures: converter discovery, pooch fetching
├── test_load.py           # happy paths per format
├── test_errors.py         # unsupported format, missing file, corrupt data,
│                          #   converter missing (skip vs. typed error)
└── test_exports.py        # HDF5 round-trip checks
```

Markers: `@pytest.mark.corpus` for Tier-2 tests — auto-skipped when the
converter is missing or the network/cache is unavailable, with a clear skip
reason. CI runs Tier 1 on every push; the corpus job runs on a schedule or
label, with the pooch cache saved between runs.
