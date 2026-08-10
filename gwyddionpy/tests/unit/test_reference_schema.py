"""Tests for the machinery that captures and compares reference content.

context part: the format tests report a failure only when the comparison
helpers return a difference, so a fault in those helpers would not break any
test — it would quietly make them pass. Neutering both of them to return "no
differences" leaves the whole format suite green, which is why they are
exercised directly here rather than only through the files they compare.

Everything here runs on constructed channels, so it needs no converter and no
measurement files.
"""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from gwyddionpy._model import Channel, GwyData
from helpers import content as content_mod


def make_channel(name="Height", data=None, **kwargs):
    if data is None:
        data = np.arange(12, dtype="f8").reshape(3, 4)
    options = {
        "xreal": 2e-6,
        "yreal": 1.5e-6,
        "si_unit_xy": "m",
        "si_unit_z": "m",
        "meta": {"Scan Rate": "1.0"},
    }
    options.update(kwargs)
    return Channel(name=name, data=np.asarray(data, dtype="f8"), **options)


# --------------------------------------------------------------------------
# float_diffs
# --------------------------------------------------------------------------
def test_identical_floats_report_nothing():
    values = {"xreal": 2e-6, "yreal": 1.5e-6}
    assert content_mod.float_diffs(values, dict(values)) == []


def test_difference_within_tolerance_is_ignored():
    """Last-bit differences between builds are not defects."""
    base = 1.9999999999999998e-05
    nudged = base * (1 + content_mod.RTOL / 100)
    assert content_mod.float_diffs({"xreal": base}, {"xreal": nudged}) == []


def test_difference_beyond_tolerance_is_reported():
    """A part-per-million drift in scan size must not pass unnoticed."""
    base = 2e-5
    diffs = content_mod.float_diffs({"xreal": base}, {"xreal": base * 1.000001})
    assert len(diffs) == 1
    assert "xreal" in diffs[0]


def test_tolerance_boundary_is_relative_not_absolute():
    """The same relative drift is caught whatever the magnitude, which matters
    because scan sizes are ~1e-5 and pixel values can be ~1e-9."""
    for magnitude in (1e-12, 1e-9, 1.0, 1e6):
        drifted = magnitude * 1.000001
        assert content_mod.float_diffs({"v": magnitude}, {"v": drifted}), (
            f"drift not caught at magnitude {magnitude}"
        )


def test_nan_matches_nan():
    """A masked pixel stays masked; that is agreement, not a difference."""
    assert content_mod.float_diffs({"v": "NaN"}, {"v": float("nan")}) == []


def test_nan_against_a_number_is_reported():
    assert len(content_mod.float_diffs({"v": "NaN"}, {"v": 0.0})) == 1
    assert len(content_mod.float_diffs({"v": 0.0}, {"v": float("nan")})) == 1


def test_infinities_match_and_differ_correctly():
    assert content_mod.float_diffs({"v": "Infinity"}, {"v": float("inf")}) == []
    assert len(content_mod.float_diffs({"v": "Infinity"},
                                       {"v": float("-inf")})) == 1


def test_missing_and_unexpected_keys_are_reported():
    missing = content_mod.float_diffs({"a": 1.0, "b": 2.0}, {"a": 1.0})
    assert len(missing) == 1 and "missing" in missing[0]

    extra = content_mod.float_diffs({"a": 1.0}, {"a": 1.0, "b": 2.0})
    assert len(extra) == 1 and "unexpected" in extra[0]


def test_where_prefix_identifies_the_channel():
    diffs = content_mod.float_diffs({"xreal": 1.0}, {"xreal": 2.0},
                                    where="Height.")
    assert diffs[0].startswith("Height.xreal")


# --------------------------------------------------------------------------
# meta_diffs
# --------------------------------------------------------------------------
def test_identical_metadata_reports_nothing():
    meta = {"Scan Rate": "1.0", "Tip": "RTESPA-300"}
    assert content_mod.meta_diffs(meta, dict(meta)) == []


def test_changed_metadata_value_is_reported():
    diffs = content_mod.meta_diffs({"Tip": "RTESPA-300"}, {"Tip": "OTESPA"})
    assert len(diffs) == 1 and "Tip" in diffs[0]


def test_added_and_removed_metadata_keys_are_reported():
    removed = content_mod.meta_diffs({"a": "1", "b": "2"}, {"a": "1"})
    assert len(removed) == 1 and "missing" in removed[0]

    added = content_mod.meta_diffs({"a": "1"}, {"a": "1", "b": "2"})
    assert len(added) == 1 and "not in reference" in added[0]


def test_metadata_compares_as_text_not_as_numbers():
    """Vendor values are strings; "1.0" and "1.00" are different readings of
    the header even though they are the same number."""
    assert len(content_mod.meta_diffs({"Scan Rate": "1.0"},
                                      {"Scan Rate": "1.00"})) == 1


# --------------------------------------------------------------------------
# pixel_positions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("shape", [(1, 1), (2, 2), (3, 7), (512, 512),
                                   (1, 2048), (2048, 1)])
def test_positions_stay_inside_the_array(shape):
    positions = content_mod.pixel_positions(shape)
    assert positions, f"no positions produced for {shape}"
    for row, col in positions:
        assert 0 <= row < shape[0]
        assert 0 <= col < shape[1]


@pytest.mark.parametrize("shape", [(1, 1), (2, 2), (3, 7), (512, 512)])
def test_positions_are_unique(shape):
    positions = content_mod.pixel_positions(shape)
    assert len(positions) == len(set(positions))


def test_single_pixel_image_yields_one_position():
    assert content_mod.pixel_positions((1, 1)) == [(0, 0)]


def test_corners_are_covered():
    rows, cols = 512, 512
    positions = set(content_mod.pixel_positions((rows, cols)))
    assert {(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)} <= positions


def test_positions_depend_only_on_shape():
    """No randomness, so a reference captured today is reproducible later."""
    assert content_mod.pixel_positions((37, 91)) == content_mod.pixel_positions(
        (37, 91)
    )


# --------------------------------------------------------------------------
# extract_content
# --------------------------------------------------------------------------
def test_extracted_content_describes_the_channels():
    data = GwyData(
        channels={"Height": make_channel("Height"),
                  "Phase": make_channel("Phase", si_unit_z="deg")},
        source_format="nanoscope",
    )
    content = content_mod.extract_content(data)

    assert content["source_format"] == "nanoscope"
    assert content["channel_names"] == ["Height", "Phase"]
    height = content["channels"]["Height"]
    assert height["shape"] == [3, 4]
    assert height["size"] == 12
    assert height["dtype"] == "float64"
    assert height["si_unit_z"] == "m"
    assert content["channels"]["Phase"]["si_unit_z"] == "deg"


def test_channel_order_follows_the_file():
    data = GwyData(
        channels={name: make_channel(name) for name in ("C", "A", "B")},
        source_format="x",
    )
    assert content_mod.extract_content(data)["channel_names"] == ["C", "A", "B"]


def test_non_finite_pixels_survive_json():
    """Masked and saturated pixels must not make the reference invalid JSON."""
    values = np.array([[np.nan, np.inf], [-np.inf, 1.0]])
    content = content_mod.extract_content(
        GwyData(channels={"Height": make_channel(data=values)}, source_format="x")
    )
    encoded = json.dumps(content, allow_nan=False)  # raises if a bare NaN slipped in
    pixels = json.loads(encoded)["channels"]["Height"]["pixels"]
    assert pixels["0,0"] == "NaN"
    assert pixels["0,1"] == "Infinity"
    assert pixels["1,0"] == "-Infinity"


def test_metadata_values_are_never_treated_as_numbers():
    """A vendor string that happens to read "NaN" stays that string, rather
    than being decoded into a float on the way back in."""
    channel = make_channel(meta={"Fit Status": "NaN", "Gain": "Infinity"})
    content = content_mod.extract_content(
        GwyData(channels={"Height": channel}, source_format="x")
    )
    reloaded = json.loads(json.dumps(content, allow_nan=False))
    meta = reloaded["channels"]["Height"]["meta"]
    assert meta["Fit Status"] == "NaN"
    assert isinstance(meta["Gain"], str)


# --------------------------------------------------------------------------
# capture and compare together
# --------------------------------------------------------------------------
def _round_trip(data, tmp_path):
    """Capture a reference the way make_reference.py does, then read it back."""
    path = tmp_path / "reference.json"
    content_mod.dump_reference(content_mod.extract_content(data), path)
    # A stand-in for a Specimen: load_reference only needs somewhere to read from.
    return content_mod.load_reference(SimpleNamespace(reference_path=path))


def test_captured_reference_matches_the_data_it_came_from(tmp_path):
    """The contract make_reference.py relies on: capture, reload, compare clean."""
    values = np.array([[np.nan, 2.0], [3.0, 4.0]])
    data = GwyData(
        channels={"Height": make_channel(data=values),
                  "Phase": make_channel("Phase", si_unit_z="deg")},
        source_format="nanoscope",
    )
    reference = _round_trip(data, tmp_path)
    fresh = content_mod.extract_content(data)

    assert reference["channel_names"] == fresh["channel_names"]
    for name, expected in reference["channels"].items():
        actual = fresh["channels"][name]
        assert content_mod.float_diffs(expected["pixels"], actual["pixels"]) == []
        assert content_mod.meta_diffs(expected["meta"], actual["meta"]) == []
        assert expected["shape"] == actual["shape"]
        assert expected["dtype"] == actual["dtype"]


def test_a_changed_value_breaks_the_round_trip(tmp_path):
    """The counterpart to the test above: comparison notices a real change."""
    data = GwyData(channels={"Height": make_channel()}, source_format="x")
    reference = _round_trip(data, tmp_path)

    moved = make_channel(data=np.arange(12, dtype="f8").reshape(3, 4) * 1.001)
    changed = content_mod.extract_content(
        GwyData(channels={"Height": moved}, source_format="x")
    )
    diffs = content_mod.float_diffs(
        reference["channels"]["Height"]["pixels"],
        changed["channels"]["Height"]["pixels"],
    )
    assert diffs, "a 0.1% change in every pixel went unnoticed"


def test_reference_file_is_valid_readable_json(tmp_path):
    data = GwyData(channels={"Height": make_channel()}, source_format="x")
    path = tmp_path / "reference.json"
    content_mod.dump_reference(content_mod.extract_content(data), path)

    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text)["source_format"] == "x"


# --------------------------------------------------------------------------
# format_diffs
# --------------------------------------------------------------------------
def test_short_diff_lists_are_shown_in_full():
    rendered = content_mod.format_diffs(["one", "two"])
    assert "one" in rendered and "two" in rendered
    assert "more" not in rendered


def test_long_diff_lists_are_capped():
    rendered = content_mod.format_diffs([f"diff {n}" for n in range(50)], limit=5)
    assert "diff 4" in rendered
    assert "diff 5" not in rendered
    assert "... and 45 more" in rendered
