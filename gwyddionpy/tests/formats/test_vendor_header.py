"""Check the converter against the vendor's own text header, where a format
has one. This is what keeps the references honest: captured from a
conversion, they otherwise only show the converter agreeing with itself.

Both Bruker files have readable headers — NanoScope and SPMLab, read by
different modules. The other vendors' values still need review by someone who
knows the instrument.

A reader returns ``(xreal, yreal, (rows, columns))`` in metres and pixels, as
the file itself states it. X and Y are separate because a format may state
them on separate lines and they need not be equal.
"""
import re

import numpy as np
import pytest

import gwyddionpy
from helpers.requirements import require_specimen
from helpers.specimens import SPECIMENS, SPECIMENS_BY_ID

pytestmark = pytest.mark.formats

WITH_HEADER_CHECKS = [s for s in SPECIMENS if s.header_checks]

#: Length units as vendor headers spell them, in metres. Keyed by bytes: the
#: headers are matched as bytes, so no encoding has to be assumed. SPMLab
#: writes the micron sign as the single Latin-1 byte 0xB5, and Nanoscope
#: writes it as "~m".
_TO_METRES = {
    b"m": 1.0,
    b"mm": 1e-3,
    b"~m": 1e-6,
    b"um": 1e-6,
    b"\xb5m": 1e-6,
    b"nm": 1e-9,
    b"A": 1e-10,
    b"\xc5": 1e-10,
}

_UNITS = b"|".join(sorted(_TO_METRES, key=len, reverse=True))


# --- Bruker Nanoscope: ASCII lines inside an otherwise binary file ---------

_SCAN_SIZE = re.compile(rb"\\Scan Size:\s*([0-9.]+)\s*(" + _UNITS + rb")\b")
_SAMPS_LINE = re.compile(rb"\\Samps/line:\s*(\d+)")
_LINES = re.compile(rb"\\Lines:\s*(\d+)")


def _nanoscope_geometry(path):
    """Scan size in metres and (rows, columns), as the file itself states.

    Nanoscope states one scan size for both axes, so it is reported twice.
    """
    raw = path.read_bytes()
    size = _SCAN_SIZE.search(raw)
    samps = _SAMPS_LINE.search(raw)
    lines = _LINES.search(raw)
    if not (size and samps and lines):
        pytest.fail(f"could not read the scan geometry from {path.name}")
    metres = float(size.group(1)) * _TO_METRES[size.group(2)]
    return metres, metres, (int(lines.group(1)), int(samps.group(1)))


# --- SPMLab .FLT: an INI-style text header, then the float data -----------

#: End of the header. The data begins immediately after this line, which is
#: what DataOffset counts up to.
_FLT_DATA_MARKER = b"[Data]\r\n"

#: A length as the header writes it: "1.0000 µm".
_FLT_LENGTH = re.compile(rb"^([0-9.eE+-]+)\s*(" + _UNITS + rb")$")

#: A piezo calibration as the header writes it: "0.7731 µm/V".
_FLT_PER_VOLT = re.compile(rb"^([0-9.eE+-]+)\s*(" + _UNITS + rb")/V$")


def _flt_header(path):
    """The header block, cut at the marker that ends it.

    Bounding the search matters: the megabyte of float data that follows can
    contain any byte sequence, including something that looks like a key.
    """
    raw = path.read_bytes()
    end = raw.find(_FLT_DATA_MARKER)
    if end < 0:
        pytest.fail(f"{path.name} has no [Data] marker; not an SPMLab .FLT?")
    return raw[: end + len(_FLT_DATA_MARKER)]


def _flt_field(header, key):
    """The verbatim value of one `Key=value` line."""
    match = re.search(
        rb"^" + re.escape(key) + rb"=[ \t]*(.*?)[ \t]*\r?$", header, re.MULTILINE
    )
    if match is None:
        pytest.fail(f"the SPMLab header has no {key.decode()} line")
    return match.group(1)


def _flt_length(header, key):
    """A header value carrying a unit, converted to metres."""
    value = _flt_field(header, key)
    match = _FLT_LENGTH.match(value)
    if match is None:
        pytest.fail(f"{key.decode()}={value!r} is not a length this test knows")
    return float(match.group(1)) * _TO_METRES[match.group(2)]


def _flt_per_volt(header, key):
    """A header value in <length>/V, converted to metres per volt."""
    value = _flt_field(header, key)
    match = _FLT_PER_VOLT.match(value)
    if match is None:
        pytest.fail(f"{key.decode()}={value!r} is not a calibration this test knows")
    return float(match.group(1)) * _TO_METRES[match.group(2)]


def _spmlab_geometry(path):
    """Scan ranges in metres and (rows, columns), as the file itself states."""
    header = _flt_header(path)
    return (
        _flt_length(header, b"ScanRangeX"),
        _flt_length(header, b"ScanRangeY"),
        (int(_flt_field(header, b"ResolutionY")),
         int(_flt_field(header, b"ResolutionX"))),
    )


HEADER_READERS = {"nanoscope": _nanoscope_geometry, "spmlabf": _spmlab_geometry}


@pytest.mark.parametrize("specimen", WITH_HEADER_CHECKS, ids=lambda s: s.id)
def test_geometry_matches_the_file_header(specimen):
    require_specimen(specimen)
    header_x, header_y, header_shape = HEADER_READERS[specimen.module](specimen.path)

    # The registry records what was read out of the header by hand. Checking
    # it here turns a typo there into a failure, rather than a quietly
    # weakened comparison below.
    assert header_x == pytest.approx(specimen.header_checks["xreal"], rel=1e-12)
    assert header_y == pytest.approx(specimen.header_checks["yreal"], rel=1e-12)
    assert header_shape == tuple(specimen.header_checks["shape"])

    data = gwyddionpy.load(specimen.path)
    for name, channel in data.channels.items():
        assert channel.data.shape == header_shape, (
            f"{name}: the header states {header_shape}, the converter "
            f"produced {channel.data.shape}"
        )
        assert channel.xreal == pytest.approx(header_x, rel=1e-9), (
            f"{name}: the header states a scan width of {header_x} m, the "
            f"converter reports {channel.xreal} m"
        )
        assert channel.yreal == pytest.approx(header_y, rel=1e-9), (
            f"{name}: the header states a scan height of {header_y} m, the "
            f"converter reports {channel.yreal} m"
        )


def test_spmlab_data_block_confirms_the_stated_resolution():
    """The .FLT header is checked against the file's own size.

    ResolutionX/Y and DataOffset are three numbers the header states about
    itself; the file length is not. If they agree — offset plus
    rows x columns x 4 bytes of float32 lands exactly on the end of the file
    — then the shape is established from the bytes rather than from anything
    the converter did.
    """
    specimen = SPECIMENS_BY_ID["bruker_spmlab/B3320_13_061726074638.SIG_TOPO_BKW.FLT"]
    require_specimen(specimen)
    header = _flt_header(specimen.path)

    offset = int(_flt_field(header, b"DataOffset"))
    rows = int(_flt_field(header, b"ResolutionY"))
    columns = int(_flt_field(header, b"ResolutionX"))

    # The marker ends the header, so DataOffset must count up to just past it.
    assert offset == len(header), (
        f"DataOffset states {offset}, but the header runs to {len(header)}"
    )
    assert offset + rows * columns * 4 == specimen.path.stat().st_size, (
        f"{rows}x{columns} float32 values after byte {offset} do not fill "
        f"the file ({specimen.path.stat().st_size} bytes)"
    )
    assert (rows, columns) == tuple(specimen.header_checks["shape"])


def test_spmlab_values_are_the_raw_block_scaled_by_the_header_coefficient():
    """Every pixel checked against the raw bytes and the vendor's own scale.

    The stored block is float32 volts; the header's ZTransferCoefficient says
    what a volt is in metres. Reading the block here and applying that
    ourselves reproduces the whole array, so the reference rests on the file
    rather than on a previous conversion — and it covers all 262144 values,
    not the seven positions the reference samples.

    It also pins the row order. The block is stored bottom row first, and the
    converter turns it the right way up; a reference captured from a flipped
    reading would look perfectly consistent, so nothing else here would
    notice if that changed.
    """
    specimen = SPECIMENS_BY_ID["bruker_spmlab/B3320_13_061726074638.SIG_TOPO_BKW.FLT"]
    require_specimen(specimen)
    header = _flt_header(specimen.path)

    offset = int(_flt_field(header, b"DataOffset"))
    rows = int(_flt_field(header, b"ResolutionY"))
    columns = int(_flt_field(header, b"ResolutionX"))
    metres_per_volt = _flt_per_volt(header, b"ZTransferCoefficient")

    # The format writes little-endian float32 regardless of the reading
    # machine, so say so rather than taking the native order.
    volts = np.fromfile(
        specimen.path, dtype="<f4", offset=offset, count=rows * columns
    ).reshape(rows, columns)
    expected = volts[::-1].astype(np.float64) * metres_per_volt

    channel = gwyddionpy.load(specimen.path).channels["Height"]
    # Bit-exact in practice; compared at the suite's tolerance so a different
    # compiler's last digit is not a failure.
    np.testing.assert_allclose(channel.data, expected, rtol=1e-9, atol=0.0)
