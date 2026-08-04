#!/usr/bin/env python3
"""Capture the golden references that the format tests compare against.

    python gwyddionpy/tests/make_golden.py                       # all files
    python gwyddionpy/tests/make_golden.py jpk/sample_0.jpk       # one file
    python gwyddionpy/tests/make_golden.py sample_0.jpk           # same, short

Each reference is written beside the raw file it describes. Run this when a
change in output is understood and intended, then read the resulting diff:
that diff is what shows exactly which values moved and is the thing worth
reviewing.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Run as a script rather than under pytest, so put tests/ on the path the way
# the pythonpath setting does during a test run.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gwyddionpy  # noqa: E402
from helpers import content as content_mod  # noqa: E402
from helpers.specimens import SPECIMENS, find_specimen  # noqa: E402


def capture(specimen) -> str:
    if not specimen.exists():
        return f"SKIP  {specimen.relpath}: not present in tests/data/"
    data = gwyddionpy.load(specimen.path)
    content = content_mod.extract_content(data)
    content_mod.dump_golden(content, specimen.golden_path)
    return (
        f"WROTE {specimen.golden_path.relative_to(specimen.path.parents[1])}: "
        f"{content['source_format']}, {len(content['channels'])} channel(s)"
    )


def main(argv) -> int:
    if argv:
        selected = []
        for name in argv:
            specimen = find_specimen(name)
            if specimen is None:
                print(f"error: {name!r} is not in the registry "
                      f"(helpers/specimens.py)", file=sys.stderr)
                return 2
            selected.append(specimen)
    else:
        selected = SPECIMENS

    for specimen in selected:
        print(capture(specimen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
