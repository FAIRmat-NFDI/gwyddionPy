"""Cross-check converter output against the vendor's *own* header.

The golden references in test_golden.py were captured from a conversion, so on
their own they only prove the converter still agrees with itself: if the very
first capture had been wrong, every golden test would happily pin the wrong
values forever. These tests break that circularity for formats whose header is
plain-text readable, by parsing the scan geometry straight out of the raw file
and comparing it to what gwyddionpy reports.

Only Bruker Nanoscope qualifies today (its header is ASCII key/value text).
Binary-header formats carry no `header_checks` in the registry and are skipped
— tracked in FullTestPlan §2.1 as the reason golden capture still needs review
by someone who knows the instrument.
"""
import re

import pytest

import gwyddionpy
from helpers.requirements import require_sample
from helpers.samples import SAMPLES

pytestmark = [pytest.mark.converter, pytest.mark.formats]

WITH_HEADER_CHECKS = [s for s in SAMPLES if s.header_checks]

# Nanoscope headers are ASCII lines like "\Scan Size: 20000 nm" embedded in an
# otherwise binary file, so read bytes and decode leniently.
_SCAN_SIZE = re.compile(rb"\\Scan Size:\s*([0-9.]+)\s*(nm|~m|um|A)\b")
_SAMPS_LINE = re.compile(rb"\\Samps/line:\s*(\d+)")
_LINES = re.compile(rb"\\Lines:\s*(\d+)")

_TO_METRES = {b"nm": 1e-9, b"~m": 1e-6, b"um": 1e-6, b"A": 1e-10}


def _bruker_header_geometry(path):
    """Scan size in metres and (rows, cols) as the file's own header states."""
    raw = path.read_bytes()
    size = _SCAN_SIZE.search(raw)
    samps = _SAMPS_LINE.search(raw)
    lines = _LINES.search(raw)
    if not (size and samps and lines):
        pytest.fail(f"could not read scan geometry from the header of {path.name}")
    metres = float(size.group(1)) * _TO_METRES[size.group(2)]
    return metres, (int(lines.group(1)), int(samps.group(1)))


HEADER_READERS = {"nanoscope": _bruker_header_geometry}


@pytest.mark.parametrize("sample", WITH_HEADER_CHECKS, ids=lambda s: s.id)
def test_geometry_matches_vendor_header(sample):
    require_sample(sample)
    reader = HEADER_READERS[sample.module]
    header_size, header_shape = reader(sample.path)

    # The registry records what a human read out of the header; assert the
    # parser agrees, so a typo in the registry surfaces here and not as a
    # silently weakened check.
    assert header_size == pytest.approx(sample.header_checks["xreal"], rel=1e-12)
    assert header_shape == tuple(sample.header_checks["shape"])

    data = gwyddionpy.load(sample.path)
    for name, channel in data.channels.items():
        assert channel.data.shape == header_shape, (
            f"{name}: header says {header_shape}, converter produced "
            f"{channel.data.shape}"
        )
        assert channel.xreal == pytest.approx(header_size, rel=1e-9), (
            f"{name}: header says scan size {header_size} m, converter "
            f"reports xreal {channel.xreal} m"
        )
        assert channel.yreal == pytest.approx(header_size, rel=1e-9)
