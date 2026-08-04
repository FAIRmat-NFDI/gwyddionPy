"""Broad sanity sweep over every registered vendor file.

Deliberately weaker than test_golden.py and kept alongside it: these
assertions hold for *any* correct conversion, so a newly added sample is
covered here the moment it enters the registry — before anyone has captured
a golden reference for it (FullTestPlan §2.2, vendor/format breadth).

Driven entirely by helpers/samples.py: adding a vendor costs a registry entry,
not new test code.
"""
import numpy as np
import pytest

import gwyddionpy
from helpers.requirements import require_sample
from helpers.samples import IMAGE_SAMPLES, SAMPLES, TEST_DATA

pytestmark = [pytest.mark.converter, pytest.mark.formats]

IDS = lambda sample: sample.id  # noqa: E731 — parametrize id callback


@pytest.mark.parametrize("sample", SAMPLES, ids=IDS)
def test_format_detected(sample):
    """The expected Gwyddion module claims the file and finds the expected
    number of image channels."""
    require_sample(sample)
    data = gwyddionpy.load(sample.path)
    assert data.source_format == sample.module
    assert len(data.channels) == sample.channels


@pytest.mark.parametrize("sample", IMAGE_SAMPLES, ids=IDS)
def test_channels_are_usable_arrays(sample):
    """Every channel is a non-empty 2-D array of finite values with positive
    physical dimensions — the minimum for the data to mean anything."""
    require_sample(sample)
    data = gwyddionpy.load(sample.path)
    for name, channel in data.channels.items():
        assert channel.data.ndim == 2, f"{name} is not 2-D"
        assert channel.data.size > 0, f"{name} is empty"
        assert np.isfinite(channel.data).all(), f"{name} holds non-finite values"
        assert channel.xreal > 0 and channel.yreal > 0, (
            f"{name} has non-positive scan dimensions"
        )


def test_spectroscopy_file_loads_with_zero_channels():
    # Nanonis .dat holds graph/spectra objects; the gwyddionpy model only
    # extracts image channels so far (TODO.md: spectra/volume support).
    from helpers.samples import SAMPLES_BY_NAME

    sample = SAMPLES_BY_NAME["Bias-Spectroscopy002.dat"]
    require_sample(sample)
    data = gwyddionpy.load(sample.path)
    assert data.source_format == "nanonis_spec"
    assert data.channels == {}


def test_unsupported_format_raises():
    bogus = TEST_DATA / "README.md"  # text file, no module claims it
    if not bogus.is_file():
        pytest.skip("test-data/README.md missing")
    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(bogus)
