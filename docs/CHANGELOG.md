# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/); versions will
follow [SemVer](https://semver.org/) once the Python package exists.

## [Unreleased]

### Added
- 2026-07-08: project migrated from the `gwybridge/` subdirectory of the
  gwyddion-fork repository to the standalone **FAIRmat-NFDI/gwyddionPy**
  repository. Licensing settled: repository Apache-2.0, `converter/`
  GPL-2.0-or-later (links Gwyddion; see converter/COPYING). Gwyddion source
  available as optional submodule `vendor/gwyddion`. Package/import name
  stays `gwybridge` for now (rename decision still open).
- 2026-07-07: multi-vendor sample corpus (JPK, WSxM, Igor, Nanonis) fetched
  from open test suites into test-data/ (untracked; provenance in
  test-data/README.md) + tests/test_real_files.py. Suite: 27 tests.
  Known limitation surfaced: spectroscopy/graph data (e.g. Nanonis .dat)
  yields 0 channels — model extension tracked in TODO.md.
- 2026-07-07: `GwyData.to_gwy()` — export back to Gwyddion-native .gwy
  (user request); lossless round-trip verified on real Bruker data.
- 2026-07-07: hierarchical metadata layout in HDF5 export (default;
  `hierarchical_meta=False` for flat attrs). TODO.md added at project root.
  Test suite now 19 tests.
- 2026-07-07: Project started on branch `PythonWrapper`. Architecture decided
  (subprocess C converter + pure-Python wrapper over `.gwy`; see
  ../CONTEXT.md Decision record). CONTEXT.md and the docs/ set
  (ARCHITECTURE, BUILD, USAGE, MAINTENANCE, TROUBLESHOOTING, EXTENDING)
  created with initial content.
- 2026-07-07: docs/TESTING.md — three-tier test-data strategy (committed
  micro-fixtures / pooch-fetched corpus / golden snapshots).
- 2026-07-07: `converter/gwyconvert.c` + Makefile (convert + `--list-formats`;
  not yet compiled — awaiting libgwyddion20-dev).
- 2026-07-07: gwyconvert compiled and verified on Ubuntu 22.04: 170 formats
  registered; real Bruker .spm converted (module `nanoscope`) and loaded
  through the Python package — 8 channels, 512×512 float64, physical units,
  875 metadata entries, HDF5 export. Build gotchas documented in
  TROUBLESHOOTING.md (gtkglext headers avoided; `~/.local/bin/as` shadowing).
- 2026-07-07: Python package `gwybridge` 0.1.0.dev0 (src layout, hatchling):
  `load()`, `list_formats()`, `parse_gwy()`, `GwyData`/`Channel` model, typed
  exceptions, HDF5 export (`[hdf5]` extra). Native `.gwy` inputs bypass the
  converter. Test suite: 16 tests, all passing, mock-free (fixtures are real
  `.gwy` files written via `gwyfile`).
