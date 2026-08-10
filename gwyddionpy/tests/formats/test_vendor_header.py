"""Check the converter against the vendor's own text header, where a format
has one. This is what keeps the references honest: captured from a
conversion, they otherwise only show the converter agreeing with itself.

Only Bruker Nanoscope has a readable header today; the other vendors' values
still need review by someone who knows the instrument.
"""
import re

import pytest

import gwyddionpy
from helpers.requirements import require_specimen
from helpers.specimens import SPECIMENS

pytestmark = pytest.mark.formats

WITH_HEADER_CHECKS = [s for s in SPECIMENS if s.header_checks]

# Nanoscope files carry ASCII header lines inside an otherwise binary file,
# so match on bytes and convert the stated unit explicitly.
_SCAN_SIZE = re.compile(rb"\\Scan Size:\s*([0-9.]+)\s*(nm|~m|um|A)\b")
_SAMPS_LINE = re.compile(rb"\\Samps/line:\s*(\d+)")
_LINES = re.compile(rb"\\Lines:\s*(\d+)")

_TO_METRES = {b"nm": 1e-9, b"~m": 1e-6, b"um": 1e-6, b"A": 1e-10}


def _nanoscope_geometry(path):
    """Scan size in metres and (rows, columns), as the file itself states."""
    raw = path.read_bytes()
    size = _SCAN_SIZE.search(raw)
    samps = _SAMPS_LINE.search(raw)
    lines = _LINES.search(raw)
    if not (size and samps and lines):
        pytest.fail(f"could not read the scan geometry from {path.name}")
    metres = float(size.group(1)) * _TO_METRES[size.group(2)]
    return metres, (int(lines.group(1)), int(samps.group(1)))


HEADER_READERS = {"nanoscope": _nanoscope_geometry}


@pytest.mark.parametrize("specimen", WITH_HEADER_CHECKS, ids=lambda s: s.id)
def test_geometry_matches_the_file_header(specimen):
    require_specimen(specimen)
    header_size, header_shape = HEADER_READERS[specimen.module](specimen.path)

    # The registry records what was read out of the header by hand. Checking
    # it here turns a typo there into a failure, rather than a quietly
    # weakened comparison below.
    assert header_size == pytest.approx(specimen.header_checks["xreal"], rel=1e-12)
    assert header_shape == tuple(specimen.header_checks["shape"])

    data = gwyddionpy.load(specimen.path)
    for name, channel in data.channels.items():
        assert channel.data.shape == header_shape, (
            f"{name}: the header states {header_shape}, the converter "
            f"produced {channel.data.shape}"
        )
        assert channel.xreal == pytest.approx(header_size, rel=1e-9), (
            f"{name}: the header states a scan size of {header_size} m, the "
            f"converter reports {channel.xreal} m"
        )
        assert channel.yreal == pytest.approx(header_size, rel=1e-9)
