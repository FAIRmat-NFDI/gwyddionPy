"""End-to-end tests against real vendor files in the repo's test-data/.

Need gwyconvert (see gwyddionpy._run.find_converter for how it is located)
and the sample files, whose provenance and re-fetch commands are listed in
test-data/README.md. Both are skipped cleanly when absent, so the offline
unit suite stays green without them.
"""
from pathlib import Path

import numpy as np
import pytest

import gwyddionpy
from gwyddionpy._errors import ConverterNotFoundError
from gwyddionpy._run import find_converter

TEST_DATA = Path(__file__).resolve().parents[2] / "test-data"

try:
    find_converter()
    HAVE_CONVERTER = True
except ConverterNotFoundError:
    HAVE_CONVERTER = False

pytestmark = [
    pytest.mark.converter,
    pytest.mark.skipif(not HAVE_CONVERTER, reason="gwyconvert not available"),
]

# (filename, expected Gwyddion module, expected channel count)
REAL_FILES = [
    ("VGEP-15m-.0_00000.spm", "nanoscope", 8),
    ("sample_0.jpk", "jpkscan", 10),
    ("sample_0.jpk-qi-image", "jpkscan", 6),
    ("sample_0.stp", "wsxmfile", 1),
    ("sample_0.top", "wsxmfile", 1),
    ("sample_0.ibw", "igorfile", 8),
]


@pytest.mark.parametrize("name,module,nchannels", REAL_FILES)
def test_real_file_parses(name, module, nchannels):
    path = TEST_DATA / name
    if not path.is_file():
        pytest.skip(f"sample file missing: {path} (see test-data/README.md)")

    data = gwyddionpy.load(path)
    assert data.source_format == module
    assert len(data.channels) == nchannels
    for channel in data.channels.values():
        assert channel.data.ndim == 2
        assert channel.data.size > 0
        assert np.isfinite(channel.data).all()
        assert channel.xreal > 0 and channel.yreal > 0


def test_spectroscopy_file_loads_with_zero_channels():
    # Nanonis .dat holds graph/spectra objects. The gwyddionpy model covers
    # image channels only, so the file loads and yields none — asserted here
    # so that adding spectra support shows up as a deliberate test change.
    path = TEST_DATA / "Bias-Spectroscopy002.dat"
    if not path.is_file():
        pytest.skip(f"sample file missing: {path}")
    data = gwyddionpy.load(path)
    assert data.source_format == "nanonis_spec"
    assert data.channels == {}


def test_unsupported_format_raises():
    bogus = TEST_DATA / "README.md"  # text file, no module claims it
    if not bogus.is_file():
        pytest.skip("test-data/README.md missing")
    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(bogus)
