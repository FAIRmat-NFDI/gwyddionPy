"""What "the content of a converted file" means, and how two compare.

JSON rather than a stored .gwy, so a reference reads in review and diffs
meaningfully. make_reference.py and the format tests both go through here,
so the schema has one definition.
"""
from __future__ import annotations

import json
import math
from typing import Dict, List

import numpy as np

SCHEMA_VERSION = 1

#: Relative tolerance for floats. A real parsing change is orders of
#: magnitude larger; last-bit build differences fall below it.
RTOL = 1e-9

_NONFINITE_TAGS = ("NaN", "Infinity", "-Infinity")


def _encode_float(value) -> object:
    """Tag NaN and the infinities as strings, since JSON has no literal for
    them. Numeric fields only: metadata stays vendor text."""
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

    Corners catch ordering and off-by-one errors; interior points catch a
    scaling change. Derived from the shape alone, so there is no seed.
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


def dump_reference(content: dict, path) -> None:
    """Write a reference file: stable key order, trailing newline, valid JSON."""
    path.write_text(
        json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_reference(specimen) -> dict:
    return json.loads(specimen.reference_path.read_text(encoding="utf-8"))


def float_diffs(expected: dict, actual: dict, where: str = "") -> List[str]:
    """Compare a flat dict of floats, collecting every mismatch. Returns
    descriptions instead of asserting, so one run reports every field that
    moved rather than stopping at the first."""
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
    """Compare vendor metadata exactly. These are strings lifted from the
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
    """Render a diff list for an assertion message, capped so a wholesale
    mismatch does not bury the terminal."""
    shown = diffs[:limit]
    rest = len(diffs) - len(shown)
    text = "\n".join(f"  - {line}" for line in shown)
    if rest > 0:
        text += f"\n  ... and {rest} more"
    return text
