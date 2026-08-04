"""What "the content of a converted file" means, and how two of them compare.

The reference for each raw file is a JSON document listing the fields below.
JSON rather than a stored .gwy because it is readable in review and diffs
meaningfully when a value moves, and because it does not carry the incidental
binary differences that two Gwyddion releases produce for identical data.

The writer (make_golden.py) and the readers (the format tests) both go through
this module, so the schema has exactly one definition.
"""
from __future__ import annotations

import json
import math
from typing import Dict, List

import numpy as np

SCHEMA_VERSION = 1

#: Relative tolerance for float comparisons. Any real change in parsing — a
#: wrong scale factor, a shifted offset — is orders of magnitude larger than
#: this, while last-bit differences between compilers, libc versions and
#: Gwyddion releases fall below it and are not defects.
RTOL = 1e-9

_NONFINITE_TAGS = ("NaN", "Infinity", "-Infinity")


def _encode_float(value) -> object:
    """NaN and infinities are not valid JSON, and masked or saturated pixels
    do occur, so tag them as strings. Numeric fields only — metadata values
    are vendor strings and are never passed through here."""
    value = float(value)
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def _decode_float(value) -> float:
    return float(value)  # float() already parses the tags above


def pixel_positions(shape) -> List[tuple]:
    """Fixed positions to record for a given image shape.

    Corners catch row/column ordering and off-by-one errors; the interior
    fractions catch a scaling change that leaves the extremes looking right.
    Derived from the shape alone, so there is no seed or state to remember.
    """
    rows, cols = int(shape[0]), int(shape[1])
    positions = [
        (0, 0),
        (0, cols - 1),
        (rows - 1, 0),
        (rows - 1, cols - 1),
        (rows // 2, cols // 2),
        (rows // 3, cols // 4),
        (rows * 2 // 3, cols * 3 // 4),
    ]
    # Small images repeat positions; keep first-seen order and drop duplicates.
    return list(dict.fromkeys(positions))


def channel_content(channel) -> dict:
    """The comparable content of a single channel."""
    data = np.asarray(channel.data)
    return {
        "shape": list(data.shape),
        "size": int(data.size),
        "dtype": str(data.dtype),
        "xreal": _encode_float(channel.xreal),
        "yreal": _encode_float(channel.yreal),
        "si_unit_xy": channel.si_unit_xy,
        "si_unit_z": channel.si_unit_z,
        "pixels": {
            f"{row},{col}": _encode_float(data[row, col])
            for row, col in pixel_positions(data.shape)
        } if data.ndim == 2 else {},
        "meta": dict(channel.meta),
    }


def extract_content(data) -> dict:
    """The comparable content of a whole file."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source_format": data.source_format,
        "channel_names": list(data.channels),   # file order, and it matters
        "channels": {
            name: channel_content(channel) for name, channel in data.channels.items()
        },
    }


def dump_golden(content: dict, path) -> None:
    """Write a reference file: stable key order, trailing newline, valid JSON."""
    path.write_text(
        json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_golden(specimen) -> dict:
    return json.loads(specimen.golden_path.read_text(encoding="utf-8"))


def float_diffs(expected: dict, actual: dict, where: str = "") -> List[str]:
    """Compare a flat dict of floats, collecting every mismatch.

    Returns descriptions rather than asserting, so one test run reports all
    the fields that moved instead of stopping at the first.
    """
    diffs = []
    for key in sorted(set(expected) | set(actual)):
        if key not in expected:
            diffs.append(f"{where}{key}: unexpected (actual {actual[key]!r})")
            continue
        if key not in actual:
            diffs.append(f"{where}{key}: missing (expected {expected[key]!r})")
            continue
        exp, act = _decode_float(expected[key]), _decode_float(actual[key])
        if math.isnan(exp) and math.isnan(act):
            continue
        if not math.isclose(exp, act, rel_tol=RTOL, abs_tol=0.0):
            diffs.append(f"{where}{key}: expected {exp!r}, got {act!r}")
    return diffs


def meta_diffs(expected: Dict[str, str], actual: Dict[str, str]) -> List[str]:
    """Compare vendor metadata exactly — these are strings lifted from the
    file header, so any difference is a difference in how it was read."""
    diffs = []
    for key in sorted(set(expected) | set(actual)):
        if key not in expected:
            diffs.append(f"{key}: key not in reference (actual {actual[key]!r})")
        elif key not in actual:
            diffs.append(f"{key}: key missing from output (expected {expected[key]!r})")
        elif expected[key] != actual[key]:
            diffs.append(f"{key}: expected {expected[key]!r}, got {actual[key]!r}")
    return diffs


def format_diffs(diffs: List[str], limit: int = 20) -> str:
    """Render a diff list for an assertion message, capped so that a wholesale
    mismatch does not bury the terminal."""
    shown = diffs[:limit]
    rest = len(diffs) - len(shown)
    text = "\n".join(f"  - {line}" for line in shown)
    if rest > 0:
        text += f"\n  ... and {rest} more"
    return text
