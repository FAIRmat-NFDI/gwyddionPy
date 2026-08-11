"""Awkward but entirely valid data taken through the exports: a single
line, a single point, one pixel tall, entirely flat, or full of gaps where
nothing was measured. None of it is malformed and all must survive.

Built from constructed files, so these need no converter.
"""
import numpy as np
import pytest

import gwyddionpy
from helpers.gwy_builder import make_gwy

h5py = pytest.importorskip("h5py")

SHAPES = {
    "single pixel": (1, 1),
    "single row": (1, 512),
    "single column": (512, 1),
    "very wide": (2, 2048),
    "very tall": (2048, 2),
    "square": (32, 32),
}


def build(tmp_path, name, values, **channel):
    spec = {"name": "Height", "data": values, "unit_xy": "m", "unit_z": "m"}
    spec.update(channel)
    return make_gwy(tmp_path / f"{name}.gwy", [spec])


def read_back(tmp_path, values, **channel):
    return gwyddionpy.load(build(tmp_path, "case", values, **channel))


@pytest.mark.parametrize("label", list(SHAPES))
def test_unusual_shapes_survive_every_export(label, tmp_path):
    rows, cols = SHAPES[label]
    values = np.arange(rows * cols, dtype="f8").reshape(rows, cols)
    data = read_back(tmp_path, values)

    assert data.channels["Height"].data.shape == (rows, cols)

    exported = data.to_dict()["channels"]["Height"]
    np.testing.assert_array_equal(exported["data"], values)

    out = tmp_path / "shape.h5"
    data.to_hdf5(out)
    with h5py.File(out, "r") as handle:
        np.testing.assert_array_equal(handle["channels/Height/data"][()], values)

    written = tmp_path / "shape.gwy"
    data.to_gwy(written)
    np.testing.assert_array_equal(
        gwyddionpy.load(written).channels["Height"].data, values
    )


def test_gaps_in_the_data_are_preserved(tmp_path):
    """Unmeasured points are NaN and must stay NaN rather than becoming zero."""
    values = np.array([[np.nan, 1.0], [2.0, np.nan]])
    data = read_back(tmp_path, values)

    np.testing.assert_array_equal(data.channels["Height"].data, values)

    out = tmp_path / "gaps.h5"
    data.to_hdf5(out)
    with h5py.File(out, "r") as handle:
        stored = handle["channels/Height/data"][()]
    assert np.isnan(stored[0, 0]) and np.isnan(stored[1, 1])
    assert stored[0, 1] == 1.0

    written = tmp_path / "gaps.gwy"
    data.to_gwy(written)
    np.testing.assert_array_equal(
        gwyddionpy.load(written).channels["Height"].data, values
    )


def test_a_completely_flat_channel_is_kept(tmp_path):
    """A flat scan is a legitimate result, not an empty one."""
    values = np.zeros((16, 16))
    data = read_back(tmp_path, values)
    assert data.channels["Height"].data.shape == (16, 16)
    np.testing.assert_array_equal(data.to_dict()["channels"]["Height"]["data"],
                                  values)


def test_extreme_magnitudes_are_not_rounded_away(tmp_path):
    values = np.array([[1e-300, 1e300], [-1e300, 0.0]])
    data = read_back(tmp_path, values)

    written = tmp_path / "extreme.gwy"
    data.to_gwy(written)
    np.testing.assert_array_equal(
        gwyddionpy.load(written).channels["Height"].data, values
    )


def test_narrow_input_is_widened_to_double_precision(tmp_path):
    """The .gwy container stores doubles, so a float32 source is widened on
    the way in and stays double. Pinned so a caller checking dtype is not
    surprised."""
    values = np.arange(12, dtype="f4").reshape(3, 4)
    data = read_back(tmp_path, values)

    channel = data.channels["Height"]
    assert channel.data.dtype == np.dtype("float64")
    np.testing.assert_array_equal(channel.data, values.astype("f8"))


def test_tiny_scan_dimensions_survive(tmp_path):
    values = np.ones((2, 2))
    data = read_back(tmp_path, values, xreal=1e-12, yreal=1e-12)
    channel = data.channels["Height"]
    assert channel.xreal == pytest.approx(1e-12)
    assert channel.yreal == pytest.approx(1e-12)


def test_a_file_with_no_channels_still_exports(tmp_path):
    """Spectroscopy files read successfully with no image channels, and the
    exports have to cope with that rather than fail."""
    from gwyfile.objects import GwyContainer

    path = tmp_path / "empty.gwy"
    GwyContainer().tofile(str(path))
    data = gwyddionpy.load(path)
    assert data.channels == {}

    assert data.to_dict()["channels"] == {}
    out = tmp_path / "empty.h5"
    data.to_hdf5(out)
    with h5py.File(out, "r") as handle:
        assert len(handle["channels"]) == 0


def test_channels_that_sanitize_alike_are_both_kept(tmp_path):
    """"/" is HDF5's path separator and becomes "_", which can land two
    different channels on one key. Both must survive under distinct keys."""
    path = make_gwy(tmp_path / "clash.gwy", [
        {"name": "A/B", "data": np.ones((2, 2))},
        {"name": "A_B", "data": np.zeros((2, 2))},
    ])
    data = gwyddionpy.load(path)
    assert len(data.channels) == 2

    exported = data.to_dict()["channels"]
    assert len(exported) == 2, "a channel was lost on the way into the dict"
    assert {entry["name"] for entry in exported.values()} == {"A/B", "A_B"}

    out = tmp_path / "clash.h5"
    data.to_hdf5(out)
    with h5py.File(out, "r") as handle:
        assert len(handle["channels"]) == 2
        names = {group.attrs["name"] for group in handle["channels"].values()}
        assert names == {"A/B", "A_B"}


def test_both_exports_choose_the_same_keys_for_clashing_names(tmp_path):
    path = make_gwy(tmp_path / "clash2.gwy", [
        {"name": "X/Y", "data": np.ones((2, 2))},
        {"name": "X_Y", "data": np.zeros((2, 2))},
    ])
    data = gwyddionpy.load(path)
    out = tmp_path / "clash2.h5"
    data.to_hdf5(out)
    with h5py.File(out, "r") as handle:
        assert set(handle["channels"]) == set(data.to_dict()["channels"])


@pytest.mark.parametrize("value", ["0", "1", "5", "A", "-", " ", "Å", "°", "µ"])
def test_single_character_metadata_survives_a_gwy_round_trip(value, tmp_path):
    """The .gwy writer has to state that text is text. Left to infer, it
    stores a one-character string as Gwyddion's char type, which reads back
    as the character's numeric code, and a non-ASCII one such as "Å" comes
    back truncated and leaves the whole file unreadable.
    """
    path = make_gwy(tmp_path / "short.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {"Setting": value}}])
    data = gwyddionpy.load(path)
    assert data.channels["Height"].meta["Setting"] == value

    written = tmp_path / "written.gwy"
    data.to_gwy(written)
    assert gwyddionpy.load(written).channels["Height"].meta["Setting"] == value


@pytest.mark.parametrize("name", ["Z", "1", "Å"])
def test_single_character_channel_name_survives_a_gwy_round_trip(name, tmp_path):
    path = make_gwy(tmp_path / "shortname.gwy",
                    [{"name": name, "data": np.ones((2, 2))}])
    data = gwyddionpy.load(path)
    assert list(data.channels) == [name]

    written = tmp_path / "written.gwy"
    data.to_gwy(written)
    assert list(gwyddionpy.load(written).channels) == [name]


def test_unicode_names_and_metadata_survive(tmp_path):
    path = make_gwy(tmp_path / "unicode.gwy", [
        {"name": "Höhe µm", "data": np.zeros((2, 2)),
         "meta": {"Kommentar": "Messung α→β, 25 °C"}},
    ])
    data = gwyddionpy.load(path)

    exported = data.to_dict()["channels"]
    entry = next(iter(exported.values()))
    assert entry["name"] == "Höhe µm"
    assert entry["meta"]["Kommentar"] == "Messung α→β, 25 °C"

    out = tmp_path / "unicode.h5"
    data.to_hdf5(out, hierarchical_meta=False)
    with h5py.File(out, "r") as handle:
        group = next(iter(handle["channels"].values()))
        assert group.attrs["name"] == "Höhe µm"
        assert group["meta"].attrs["Kommentar"] == "Messung α→β, 25 °C"


@pytest.mark.parametrize("raw", ["1_000", "１２", "0x10", "1,5", "true", "", "  "])
def test_vendor_text_is_not_silently_turned_into_a_number(raw, tmp_path):
    """int() and float() accept more than an instrument ever writes: "1_000"
    parses as 1000 through digit separators and "１２" as 12 through
    non-ASCII digits, either of which would rewrite the recorded value."""
    path = make_gwy(tmp_path / "meta.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {"Label": raw}}])
    data = gwyddionpy.load(path)
    stored = data.to_dict()["channels"]["Height"]["meta"]["Label"]
    assert stored == raw, f"{raw!r} was rewritten as {stored!r}"


@pytest.mark.parametrize("raw,expected", [("12", 12), ("-2.44", -2.44),
                                          ("1e5", 100000.0), (".5", 0.5)])
def test_genuine_numbers_are_still_parsed(raw, expected, tmp_path):
    """The counterpart: real numbers must still be recognised."""
    path = make_gwy(tmp_path / "num.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {"Value": raw}}])
    data = gwyddionpy.load(path)
    assert data.to_dict()["channels"]["Height"]["meta"]["Value"] == expected


def test_values_with_units_are_still_split(tmp_path):
    path = make_gwy(tmp_path / "unit.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {"Bias": "-2.44 V", "Limit": "0 mV"}}])
    meta = gwyddionpy.load(path).to_dict()["channels"]["Height"]["meta"]
    assert meta["Bias"] == {"value": -2.44, "unit": "V"}
    assert meta["Limit"] == {"value": 0, "unit": "mV"}
