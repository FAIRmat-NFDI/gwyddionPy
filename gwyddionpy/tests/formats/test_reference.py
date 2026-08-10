"""Compare each measurement against the JSON reference beside it, one
element at a time, so a failure names both the element and the file.

References come from make_reference.py and are reviewed before committing.
Regenerating one to make a test pass is how the suite stops testing.
"""
import numpy as np
import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_reference
from helpers.specimens import SPECIMENS

pytestmark = pytest.mark.formats

#: Files currently held open, so the one-at-a-time guarantee can be asserted
#: rather than assumed.
_OPEN = []


@pytest.fixture(scope="module", params=SPECIMENS, ids=lambda s: s.id)
def reading(request):
    """One file's reference and a fresh reading of it.

    Module scope with parameters groups the run: pytest finishes every test
    for one file before opening the next, so peak memory stays at the
    largest file rather than the total.
    """
    specimen = request.param
    require_reference(specimen)
    reference = content_mod.load_reference(specimen)
    data = gwyddionpy.load(specimen.path)
    _OPEN.append(specimen.relpath)
    try:
        yield specimen, reference, data
    finally:
        _OPEN.remove(specimen.relpath)


def paired_channels(reference, data):
    """Yield (name, reference channel, read channel) for channels in both.

    Names on only one side are left to test_channel_names, so a renamed
    channel fails once rather than in every test below.
    """
    for name, expected in reference["channels"].items():
        if name in data.channels:
            yield name, expected, data.channels[name]


def test_every_specimen_has_a_reference():
    """A file without a reference would drop silently out of everything
    below, so check the set directly."""
    missing = [s.relpath for s in SPECIMENS if not s.reference_path.is_file()]
    assert not missing, "files with no reference: " + ", ".join(missing)


def test_only_one_file_is_held_open(reading):
    """Guards what the fixture exists for. Reintroducing caching, or
    widening the fixture scope, fails here."""
    assert _OPEN == [reading[0].relpath]


def test_source_format(reading):
    """Which Gwyddion module claimed the file, i.e. format detection."""
    _, reference, data = reading
    assert data.source_format == reference["source_format"]


def test_channel_names(reading):
    """Channel names and their order, which callers index by."""
    _, reference, data = reading
    assert list(data.channels) == reference["channel_names"]


def test_channel_arrays(reading):
    """Shape, element count and dtype. The values are test_pixel_values."""
    _, reference, data = reading
    diffs = []
    for name, expected, actual in paired_channels(reference, data):
        if not isinstance(actual.data, np.ndarray):
            diffs.append(f"{name}: not an array, got {type(actual.data).__name__}")
            continue
        if list(actual.data.shape) != expected["shape"]:
            diffs.append(f"{name}: expected shape {tuple(expected['shape'])}, "
                         f"got {actual.data.shape}")
        if int(actual.data.size) != expected["size"]:
            diffs.append(f"{name}: expected {expected['size']} values, "
                         f"got {actual.data.size}")
        if str(actual.data.dtype) != expected["dtype"]:
            diffs.append(f"{name}: expected dtype {expected['dtype']}, "
                         f"got {actual.data.dtype}")
    assert not diffs, "channel arrays changed:\n" + content_mod.format_diffs(diffs)


def test_scan_dimensions(reading):
    """Physical scan size. A change here makes every length, area and lateral
    calibration derived from the data wrong as well."""
    _, reference, data = reading
    diffs = []
    for name, expected, actual in paired_channels(reference, data):
        diffs += content_mod.float_diffs(
            {"xreal": expected["xreal"], "yreal": expected["yreal"]},
            {"xreal": actual.xreal, "yreal": actual.yreal},
            where=f"{name}.",
        )
    assert not diffs, "scan dimensions changed:\n" + content_mod.format_diffs(diffs)


def test_units(reading):
    _, reference, data = reading
    diffs = []
    for name, expected, actual in paired_channels(reference, data):
        for field, got in (("si_unit_xy", actual.si_unit_xy),
                           ("si_unit_z", actual.si_unit_z)):
            if got != expected[field]:
                diffs.append(f"{name}.{field}: expected {expected[field]!r}, "
                             f"got {got!r}")
    assert not diffs, "units changed:\n" + content_mod.format_diffs(diffs)


def test_pixel_values(reading):
    """Values at fixed positions: the corners, the centre and a few interior
    points, which together catch both ordering and scaling changes."""
    _, reference, data = reading
    diffs = []
    for name, expected, actual in paired_channels(reference, data):
        got = {
            key: actual.data[int(row), int(col)]
            for key in expected["pixels"]
            for row, col in [key.split(",")]
        }
        diffs += content_mod.float_diffs(expected["pixels"], got, where=f"{name} @ ")
    assert not diffs, "pixel values changed:\n" + content_mod.format_diffs(diffs)


def test_metadata(reading):
    """Vendor metadata, compared exactly. Its own test because a Gwyddion
    release can legitimately add header keys, and that must be handleable
    without loosening the numeric comparisons above."""
    _, reference, data = reading
    diffs = []
    for name, expected, actual in paired_channels(reference, data):
        diffs += [f"{name}.{d}" for d in content_mod.meta_diffs(
            expected["meta"], actual.meta)]
    assert not diffs, "vendor metadata changed:\n" + content_mod.format_diffs(diffs)
