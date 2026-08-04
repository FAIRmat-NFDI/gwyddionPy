"""Field-by-field comparison of each converted file against its reference.

Every raw file in tests/data/ has a JSON reference beside it recording what
reading it produces. These tests read the file again and compare the result
one data element at a time, so a failure says which element changed and for
which file — test_units[jpk/sample_0.jpk] rather than a single assertion that
stops at the first difference.

References are captured with make_golden.py and reviewed before being
committed; regenerating one to make a failing test pass is how the suite
stops testing anything.
"""
from functools import lru_cache

import numpy as np
import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_golden
from helpers.specimens import IMAGE_SPECIMENS, SPECIMENS, SPECIMENS_BY_ID

pytestmark = pytest.mark.formats

IDS = lambda specimen: specimen.id  # noqa: E731 — parametrize id callback


@lru_cache(maxsize=None)
def _read(relpath):
    """Read a specimen once and reuse it across the element tests.

    Conversion dominates the runtime and every test below wants the same
    result; nothing here mutates what it gets back.
    """
    return gwyddionpy.load(SPECIMENS_BY_ID[relpath].path)


def _reference_and_result(specimen):
    require_golden(specimen)
    return content_mod.load_golden(specimen), _read(specimen.relpath)


def _channels(reference, data):
    """Pair up channels present in both the reference and the result.

    Names that appear on only one side are left to test_channel_names, so a
    renamed channel produces one clear failure instead of the same news
    repeated by every element test.
    """
    for name, expected in reference["channels"].items():
        if name in data.channels:
            yield name, expected, data.channels[name]


def test_every_specimen_has_a_reference():
    """A specimen without a reference would silently drop out of everything
    below, so check the set directly."""
    missing = [s.relpath for s in SPECIMENS if not s.golden_path.is_file()]
    assert not missing, "specimens with no golden reference: " + ", ".join(missing)


@pytest.mark.parametrize("specimen", SPECIMENS, ids=IDS)
def test_source_format(specimen):
    """Which Gwyddion module claimed the file, i.e. format detection."""
    reference, data = _reference_and_result(specimen)
    assert data.source_format == reference["source_format"]


@pytest.mark.parametrize("specimen", SPECIMENS, ids=IDS)
def test_channel_names(specimen):
    """Channel names and their order, which callers index by."""
    reference, data = _reference_and_result(specimen)
    assert list(data.channels) == reference["channel_names"]


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=IDS)
def test_channel_arrays(specimen):
    """Each channel holds a real array of the expected shape and size."""
    reference, data = _reference_and_result(specimen)
    diffs = []
    for name, expected, actual in _channels(reference, data):
        if not isinstance(actual.data, np.ndarray):
            diffs.append(f"{name}: not an array, got {type(actual.data).__name__}")
            continue
        if list(actual.data.shape) != expected["shape"]:
            diffs.append(f"{name}: expected shape {tuple(expected['shape'])}, "
                         f"got {actual.data.shape}")
        if int(actual.data.size) != expected["size"]:
            diffs.append(f"{name}: expected {expected['size']} values, "
                         f"got {actual.data.size}")
    assert not diffs, "channel arrays changed:\n" + content_mod.format_diffs(diffs)


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=IDS)
def test_scan_dimensions(specimen):
    """Physical scan size. A change here makes every length, area and lateral
    calibration derived from the data wrong as well."""
    reference, data = _reference_and_result(specimen)
    diffs = []
    for name, expected, actual in _channels(reference, data):
        diffs += content_mod.float_diffs(
            {"xreal": expected["xreal"], "yreal": expected["yreal"]},
            {"xreal": actual.xreal, "yreal": actual.yreal},
            where=f"{name}.",
        )
    assert not diffs, "scan dimensions changed:\n" + content_mod.format_diffs(diffs)


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=IDS)
def test_units(specimen):
    reference, data = _reference_and_result(specimen)
    diffs = []
    for name, expected, actual in _channels(reference, data):
        for field, got in (("si_unit_xy", actual.si_unit_xy),
                           ("si_unit_z", actual.si_unit_z)):
            if got != expected[field]:
                diffs.append(f"{name}.{field}: expected {expected[field]!r}, "
                             f"got {got!r}")
    assert not diffs, "units changed:\n" + content_mod.format_diffs(diffs)


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=IDS)
def test_pixel_values(specimen):
    """Values at fixed positions: the corners, the centre and a few interior
    points, which together catch both ordering and scaling changes."""
    reference, data = _reference_and_result(specimen)
    diffs = []
    for name, expected, actual in _channels(reference, data):
        got = {
            key: actual.data[int(row), int(col)]
            for key in expected["pixels"]
            for row, col in [key.split(",")]
        }
        diffs += content_mod.float_diffs(expected["pixels"], got, where=f"{name} @ ")
    assert not diffs, "pixel values changed:\n" + content_mod.format_diffs(diffs)


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=IDS)
def test_metadata(specimen):
    """Vendor metadata, compared exactly.

    context part: metadata is the element most likely to move legitimately
    between Gwyddion releases, since a new release can add header keys. It is
    kept as its own test so that such a change can be handled here without
    loosening any of the numeric comparisons above.
    """
    reference, data = _reference_and_result(specimen)
    diffs = []
    for name, expected, actual in _channels(reference, data):
        diffs += [f"{name}.{d}" for d in content_mod.meta_diffs(
            expected["meta"], actual.meta)]
    assert not diffs, "vendor metadata changed:\n" + content_mod.format_diffs(diffs)
