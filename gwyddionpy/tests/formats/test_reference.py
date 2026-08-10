"""Field-by-field comparison of each measurement file against its reference.

Every raw file in tests/data/ has a JSON reference beside it recording what
reading it produces. These tests read the file again and compare the result
one data element at a time, so a failure says which element changed and for
which file — test_units[jpk/sample_0.jpk] rather than a single assertion that
stops at the first difference.

Files are opened one at a time: the fixture below is parametrized at module
scope, so pytest runs every test for one file and releases it before opening
the next. Peak memory is therefore the size of the largest file rather than
the total of all of them, which is what keeps the suite affordable as more
measurements are added — a single high-resolution scan can run to hundreds of
megabytes once its channels are expanded to float64.

References are captured with make_reference.py and reviewed before being
committed; regenerating one to make a failing test pass is how the suite stops
testing anything.
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

    Module scope with parameters is what produces the grouping: pytest runs
    all the tests below for a single file, tears this fixture down, and only
    then moves to the next. Nothing caches the result, so the data becomes
    collectable as soon as the file's tests are done.
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

    Names appearing on only one side are left to test_channel_names, so a
    renamed channel produces one clear failure instead of the same news
    repeated by every element test. Files that hold no image channels yield
    nothing here; their content is pinned by the two file-level tests.
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
    """Guards the property the fixture exists for: if someone reintroduces
    caching, or widens the fixture scope, this is what notices."""
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
    """Each channel holds a real array of the expected dimensions and type.

    The values themselves are checked by test_pixel_values; this is about the
    shape of the container — dimensions, element count and dtype.
    """
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
    """Vendor metadata, compared exactly.

    context part: metadata is the element most likely to move legitimately
    between Gwyddion releases, since a new release can add header keys. It is
    kept as its own test so that such a change can be handled here without
    loosening any of the numeric comparisons above.
    """
    _, reference, data = reading
    diffs = []
    for name, expected, actual in paired_channels(reference, data):
        diffs += [f"{name}.{d}" for d in content_mod.meta_diffs(
            expected["meta"], actual.meta)]
    assert not diffs, "vendor metadata changed:\n" + content_mod.format_diffs(diffs)
