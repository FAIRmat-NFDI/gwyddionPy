"""Broad checks that hold for every registered file, whatever its vendor.

These assertions are true of any correct reading, so a newly added file is
covered the moment it enters the registry — before anyone has captured a
reference for it. Everything is driven from the registry and the paths under
tests/data/, so adding a vendor, a format version or a whole new directory
costs an entry rather than a test.
"""
import pytest

import gwyddionpy
from helpers.requirements import require_specimen
from helpers.specimens import DATA_DIR, SPECIMENS, SPECIMENS_BY_ID

pytestmark = pytest.mark.formats

IDS = lambda specimen: specimen.id  # noqa: E731 — parametrize id callback


@pytest.mark.parametrize("specimen", SPECIMENS, ids=IDS)
def test_format_detected(specimen):
    """The expected module claims the file and finds the expected number of
    image channels."""
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)
    assert data.source_format == specimen.module
    assert len(data.channels) == specimen.channels


@pytest.mark.parametrize("specimen", SPECIMENS, ids=IDS)
def test_channels_carry_data(specimen):
    """Channels are non-empty and physically dimensioned.

    context part: no assumption is made about dimensionality here — some
    measurements are recorded as a single line rather than an image — so this
    checks only that a channel carries values and a positive extent.
    """
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)
    for name, channel in data.channels.items():
        assert channel.data.size > 0, f"{name} carries no values"
        assert channel.xreal > 0, f"{name} has a non-positive width"
        assert channel.yreal > 0, f"{name} has a non-positive height"


@pytest.mark.parametrize("specimen", SPECIMENS, ids=IDS)
def test_specimen_file_is_present(specimen):
    """The registry and the files on disk agree."""
    require_specimen(specimen)
    assert specimen.path.is_file()


def test_spectroscopy_file_has_no_image_channels():
    """Spectroscopy files read successfully but carry graph data, which the
    data model does not expose as image channels."""
    specimen = SPECIMENS_BY_ID["nanonis/Bias-Spectroscopy002.dat"]
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)
    assert data.source_format == "nanonis_spec"
    assert data.channels == {}


def test_unreadable_file_raises():
    """A text file that no module claims is rejected rather than half-read."""
    text_file = DATA_DIR / "README.md"
    assert text_file.is_file(), f"{text_file} is missing"
    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(text_file)
