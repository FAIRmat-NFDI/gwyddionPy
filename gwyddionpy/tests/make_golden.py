#!/usr/bin/env python3
"""Regenerate the golden reference JSON in tests/golden/.

    python gwyddionpy/tests/make_golden.py                  # every sample
    python gwyddionpy/tests/make_golden.py sample_0.jpk ...  # named samples

Run this only when a change in output is *understood and intended*, then read
the resulting git diff: that diff is the review artifact showing exactly what
moved. Regenerating to make a failing test pass is how a golden suite quietly
stops testing anything.

Needs a working gwyconvert (GWYDDIONPY_CONVERT or PATH) and the sample files
in test-data/.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Standalone script: pytest's `pythonpath` ini option isn't in effect here,
# so put tests/ on the path the same way pytest would.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gwyddionpy  # noqa: E402
from helpers import content as content_mod  # noqa: E402
from helpers.samples import GOLDEN_DIR, SAMPLES, find_sample  # noqa: E402


def regenerate(sample) -> str:
    if not sample.exists():
        return f"SKIP {sample.filename}: not in test-data/"
    data = gwyddionpy.load(sample.path)
    content = content_mod.extract_content(data)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    content_mod.dump_golden(content, sample.golden_path)
    return (
        f"WROTE {sample.golden_path.name}: {content['source_format']}, "
        f"{len(content['channels'])} channel(s)"
    )


def main(argv) -> int:
    if argv:
        selected = []
        for name in argv:
            sample = find_sample(name)
            if sample is None:
                print(f"error: {name!r} is not in the sample registry "
                      f"(helpers/samples.py)", file=sys.stderr)
                return 2
            selected.append(sample)
    else:
        selected = SAMPLES

    for sample in selected:
        print(regenerate(sample))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
