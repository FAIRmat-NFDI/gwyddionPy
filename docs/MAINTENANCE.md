# Maintenance Guide

## Python version updates (e.g., 3.15)

The Python package is pure Python; nothing links CPython. Expected work for a
new Python release: bump the `requires-python` / classifier metadata and run
the test suite. Dependencies (`numpy`, `gwyfile`, `h5py` for export) are the
only realistic breakage points — all mainstream and quick to support new
Pythons. **There is deliberately no compiled Python extension; keep it that
way** (Decision D1 in ../CONTEXT.md).

## Gwyddion updates

`gwyconvert` uses only long-stable APIs (`gwy_file_load`, `gwy_file_save`,
GwyContainer serialization) that have not changed materially in 15+ years.
On a new Gwyddion release: rebuild the converter, run the test suite, done.
New file formats added upstream are inherited **for free** — no gwyddionpy
change needed.

## Dependency policy

- `gwyfile` (PyPI): small and rarely updated. If it ever becomes incompatible
  or unmaintained, vendor the needed subset (it is MIT-licensed) into
  `gwyddionpy/_gwyfile/` — note it in CHANGELOG.md.
- `numpy`: follow NEP 29 / SPEC 0 support windows; avoid private APIs.

## Licensing constraints (do not accidentally violate)

- Gwyddion and `gwyconvert` are **GPL-2.0-or-later**. Any code linked into the
  converter must be GPL-compatible.
- The Python package must **never** import or link Gwyddion code directly —
  the subprocess boundary is what keeps its licensing independent.

## Release checklist

1. Update CHANGELOG.md; bump version in `python/pyproject.toml`.
2. Run tests against real sample files on a clean venv.
3. Verify `gwyconvert --list-formats` output still parses.
4. Update ../CONTEXT.md (status + session log) and USAGE.md status marks.
5. Tag, build sdist/wheel (`python -m build`), publish.

## Health checks when something rots

- `pkg-config --list-all | grep -i gwy` — dev package still present?
- `gwyconvert --list-formats | python -m json.tool` — converter alive?
- `pip show gwyfile numpy` — dependency versions vs. pins.
- See TROUBLESHOOTING.md for the historical record of failures and fixes.
