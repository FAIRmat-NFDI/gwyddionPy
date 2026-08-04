"""The golden-reference schema: what "the content of a converted file" means,
how it is serialized to JSON, and how a fresh conversion is compared to it.

One module owns all three so the writer (make_golden.py) and the readers
(formats/test_golden.py) can never drift apart.

Why JSON of extracted fields rather than a checked-in reference .gwy: it is
readable in review, diffs meaningfully when a value changes, and is immune to
incidental binary differences between Gwyddion versions. The cost is that it
pins the fields listed here and nothing else — full pixel arrays are
represented by statistics plus fixed spot samples, not stored verbatim.
"""
from __future__ import annotations

import json
import math
from typing import Dict, List

import numpy as np

SCHEMA_VERSION = 1

#: Relative tolerance for every float comparison. Tight enough that any real
#: parsing change (a wrong scale factor, a shifted offset) fails loudly, loose
#: enough to absorb last-bit differences between compilers, libc versions and
#: Gwyddion releases — which are not bugs and must not fail CI.
RTOL = 1e-9


# --------------------------------------------------------------------------
# Non-finite floats: NaN/Infinity are not valid JSON. Masked or saturated
# pixels are a real possibility in SPM data, so tag them as strings and
# decode symmetrically. Applied only to numeric fields — never to metadata,
# whose values are vendor strings that may legitimately read "NaN".
# --------------------------------------------------------------------------
def _encode_float(value) -> object:
    value = float(value)
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def _decode_float(value) -> float:
    return float(value)  # float() already parses "NaN"/"Infinity"/"-Infinity"


def spot_indices(shape) -> List[tuple]:
    """Fixed, shape-derived pixel positions to sample.

    Deterministic by construction (no RNG, no seed to remember): corners and
    interior fractions. Corners catch row/column-order and off-by-one errors,
    the interior points catch scaling errors that leave the extremes intact.
    """
    rows, cols = int(shape[0]), int(shape[1])
    candidates = [
        (0, 0),
        (0, cols - 1),
        (rows - 1, 0),
        (rows - 1, cols - 1),
        (rows // 2, cols // 2),
        (rows // 3, cols // 4),
        (rows * 2 // 3, cols * 3 // 4),
    ]
    # dict.fromkeys keeps first-seen order while dropping duplicates, which
    # tiny images (1x1, 2x2) produce.
    return list(dict.fromkeys(candidates))


def channel_content(channel) -> dict:
    """Extract the comparable content of one Channel."""
    data = np.asarray(channel.data)
    finite = data[np.isfinite(data)]
    return {
        "shape": list(data.shape),
        "dtype": str(data.dtype),
        "xreal": _encode_float(channel.xreal),
        "yreal": _encode_float(channel.yreal),
        "si_unit_xy": channel.si_unit_xy,
        "si_unit_z": channel.si_unit_z,
        "stats": {
            # Computed over finite values only, so one NaN pixel does not
            # collapse every statistic to NaN and hide the rest of the array.
            "finite_count": int(finite.size),
            "min": _encode_float(finite.min()) if finite.size else "NaN",
            "max": _encode_float(finite.max()) if finite.size else "NaN",
            "mean": _encode_float(finite.mean()) if finite.size else "NaN",
            "std": _encode_float(finite.std()) if finite.size else "NaN",
        },
        "samples": {
            f"{row},{col}": _encode_float(data[row, col])
            for row, col in spot_indices(data.shape)
        },
        "meta": dict(channel.meta),
    }


def extract_content(data) -> dict:
    """Extract the full comparable content of a parsed file."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source_format": data.source_format,
        "channel_names": list(data.channels),   # order is file order, and matters
        "channels": {
            name: channel_content(channel) for name, channel in data.channels.items()
        },
    }


def dump_golden(content: dict, path) -> None:
    """Write a golden file: stable key order, trailing newline, no NaN."""
    path.write_text(
        json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_golden(sample) -> dict:
    return json.loads(sample.golden_path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Comparison helpers. Each returns a list of human-readable differences
# instead of asserting, so a test can report every mismatched field at once
# rather than dying on the first one.
# --------------------------------------------------------------------------
def float_diffs(expected: dict, actual: dict, where: str = "") -> List[str]:
    """Compare a flat dict of floats within RTOL."""
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
    """Compare vendor metadata exactly — these are strings straight out of the
    file header, and any change is a parsing change worth seeing."""
    diffs = []
    for key in sorted(set(expected) | set(actual)):
        if key not in expected:
            diffs.append(f"{key}: key not in golden (actual {actual[key]!r})")
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
