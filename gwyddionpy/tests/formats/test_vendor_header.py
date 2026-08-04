"""Checking the converter against the vendor's own header.

Some formats write their scan geometry as plain text inside the file. Where
that is the case the geometry can be read straight out of the raw bytes and
compared with what gwyddionpy reports, which gives an account of the numbers
that comes from the instrument rather than from a previous conversion.

context part: the golden references are captured from a conversion, so on
their own they establish only that the converter still agrees with itself. If
a first capture had been wrong, every reference test would keep pinning the
wrong values. These checks are what break that circle, and they are the reason
the Bruker geometry can be trusted rather than merely repeated.

warning: only Bruker Nanoscope has a readable header today. The values for
JPK, WSxM, Igor and Nanonis rest on the captured conversion alone and still
need review by someone who knows the instrument better.
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

    # The registry records what was read out of the header by hand; checking
    # it here means a typo in the registry shows up as a failure instead of
    # quietly weakening the comparison below.
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
