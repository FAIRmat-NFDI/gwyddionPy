"""The JSON metadata export: layout, strict validity, and what it drops.

Kept out of test_exports.py, which skips its whole module without h5py.
Nothing here needs h5py, and these must not skip with it.

Built from constructed .gwy files, so these need no converter.
"""
import json
import math

import numpy as np

import gwyddionpy
from helpers.gwy_builder import make_gwy


def load_written(data, tmp_path, name="meta.json", **kwargs):
    """Write the export and read the file back as JSON, the way a consumer
    would — through the file, not the in-memory payload."""
    path = tmp_path / name
    data.to_json(path, **kwargs)
    return json.loads(path.read_text(encoding="utf-8"))


def test_to_json_writes_channels_and_metadata(two_channel_gwy, tmp_path):
    data = gwyddionpy.load(two_channel_gwy)
    result = load_written(data, tmp_path)

    assert result["source_format"] == data.source_format
    assert set(result["channels"]) == {"Height", "Phase"}
    height = result["channels"]["Height"]
    assert height["name"] == "Height"
    assert height["xreal"] == 2e-6
    assert height["yreal"] == 1.5e-6
    assert height["si_unit_xy"] == "m"
    assert height["si_unit_z"] == "m"
    assert height["meta"]["Tip"] == "RTESPA-300"
    assert result["channels"]["Phase"]["si_unit_z"] == "deg"


def test_to_json_carries_no_pixel_data(two_channel_gwy, tmp_path):
    data = gwyddionpy.load(two_channel_gwy)
    result = load_written(data, tmp_path)

    height = result["channels"]["Height"]
    assert "data" not in height
    # The array is gone, but the file still records what size it was.
    assert height["shape"] == [3, 4]
    assert result["channels"]["Phase"]["shape"] == [3, 4]

    # No pixel value survives anywhere in the file, at any nesting depth.
    text = (tmp_path / "meta.json").read_text(encoding="utf-8")
    assert "1e-09" not in text and "-90.0" not in text


def test_to_json_matches_to_dict_apart_from_the_array(two_channel_gwy,
                                                      tmp_path):
    """The two exports must not drift: everything but the image is equal."""
    data = gwyddionpy.load(two_channel_gwy)
    from_json = load_written(data, tmp_path)
    from_dict = data.to_dict()

    assert from_json["source_format"] == from_dict["source_format"]
    assert list(from_json["channels"]) == list(from_dict["channels"])
    for key, channel in from_dict["channels"].items():
        expected = {k: v for k, v in channel.items() if k != "data"}
        actual = {k: v for k, v in from_json["channels"][key].items()
                  if k != "shape"}
        assert actual == expected


def test_to_json_hierarchical_metadata(tmp_path):
    path = make_gwy(
        tmp_path / "hier.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"2:AmplitudeLimit": "2000 mV",
                   "Samps/line": "512",
                   "Scan Rate": "1.0"}}],
    )
    data = gwyddionpy.load(path)
    meta = load_written(data, tmp_path)["channels"]["Height"]["meta"]
    # Same grouping and value/unit split as the dict and HDF5 exports,
    # as nested JSON objects.
    assert meta["group 2"]["AmplitudeLimit"] == {"value": 2000, "unit": "mV"}
    assert meta["Samps"]["line"] == 512
    assert meta["Scan Rate"] == 1.0   # plain keys stay at top level


def test_to_json_flat_metadata_option(two_channel_gwy, tmp_path):
    data = gwyddionpy.load(two_channel_gwy)
    result = load_written(data, tmp_path, hierarchical_meta=False)
    # raw strings, unsplit — no nested objects, no value/unit parsing
    assert result["channels"]["Height"]["meta"] == {
        "Scan Rate": "1.0", "Tip": "RTESPA-300",
    }


def test_to_json_metadata_value_parsing(tmp_path):
    path = make_gwy(
        tmp_path / "vals.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"Drive Routing": "Tapping Piezo",   # plain text
                   "Sensitivity": "1 nA/V",            # unit with a slash
                   "Engage X Pos": "-19783.4 um",      # negative number
                   "Gains": "0.05 0.05",               # list: stays a string
                   "Padded": "1.000000 "}}],           # trailing whitespace
    )
    data = gwyddionpy.load(path)
    meta = load_written(data, tmp_path)["channels"]["Height"]["meta"]
    assert meta["Drive Routing"] == "Tapping Piezo"
    assert meta["Sensitivity"] == {"value": 1, "unit": "nA/V"}
    assert meta["Engage X Pos"] == {"value": -19783.4, "unit": "um"}
    assert meta["Gains"] == "0.05 0.05"
    assert meta["Padded"] == 1.0


def test_to_json_metadata_key_collisions(tmp_path):
    path = make_gwy(
        tmp_path / "clash.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"2:Limit": "1 mV",
                   "group 2/Limit": "2 mV",   # same node as the key above
                   "Samps": "top",
                   "Samps/line": "512"}}],    # needs a group where a
    )                                         # leaf already sits
    data = gwyddionpy.load(path)
    meta = load_written(data, tmp_path)["channels"]["Height"]["meta"]
    assert meta["group 2"]["Limit"] == {"value": 1, "unit": "mV"}
    # colliding keys survive under their flat name at the meta root
    assert meta["group 2_Limit"] == {"value": 2, "unit": "mV"}
    assert meta["Samps"] == "top"
    assert meta["Samps_line"] == 512


def test_to_json_channel_name_with_slash(tmp_path):
    path = make_gwy(tmp_path / "slash.gwy",
                    [{"name": "Amplitude/Error", "data": np.zeros((2, 2))}])
    data = gwyddionpy.load(path)
    result = load_written(data, tmp_path)
    # "/" is sanitized in the key, same as the dict and HDF5 exports, but
    # the original channel name is kept in the "name" field.
    assert result["channels"]["Amplitude_Error"]["name"] == "Amplitude/Error"


def test_to_json_tags_non_finite_metadata(tmp_path):
    """_metatree turns "NaN"/"inf" into floats, which have no JSON literal."""
    path = make_gwy(
        tmp_path / "nonfinite.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"Missing": "NaN", "Ceiling": "inf", "Floor": "-inf",
                   "Real": "1.5"}}],
    )
    data = gwyddionpy.load(path)
    text = (tmp_path / "meta.json")
    result = load_written(data, tmp_path)
    meta = result["channels"]["Height"]["meta"]

    assert meta["Missing"] == "NaN"
    assert meta["Ceiling"] == "Infinity"
    assert meta["Floor"] == "-Infinity"
    assert meta["Real"] == 1.5

    # The tags are strings a strict parser accepts, and float() reads them
    # straight back to the values the metadata tree held.
    assert math.isnan(float(meta["Missing"]))
    assert float(meta["Ceiling"]) == math.inf
    assert float(meta["Floor"]) == -math.inf
    # No bare NaN/Infinity literal anywhere in the file.
    assert json.loads(text.read_text(encoding="utf-8"),
                      parse_constant=_reject) is not None


def _reject(literal):
    raise AssertionError(f"invalid JSON literal in the file: {literal}")


def test_to_json_non_finite_dimensions_are_tagged(tmp_path):
    """xreal/yreal come straight from the file and can be non-finite too."""
    path = make_gwy(
        tmp_path / "dims.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "xreal": math.nan, "yreal": math.inf}],
    )
    data = gwyddionpy.load(path)
    result = load_written(data, tmp_path)
    assert result["channels"]["Height"]["xreal"] == "NaN"
    assert result["channels"]["Height"]["yreal"] == "Infinity"


def test_to_json_keeps_non_ascii_metadata_readable(tmp_path):
    """Vendor headers are full of µ, ° and Å; escaping them helps nobody."""
    path = make_gwy(
        tmp_path / "unicode.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"Scan Size": "5 µm", "Angle": "90 °", "Tip": "Å-probe"}}],
    )
    data = gwyddionpy.load(path)
    text = (tmp_path / "meta.json")
    result = load_written(data, tmp_path)

    assert result["channels"]["Height"]["meta"]["Scan Size"] == {
        "value": 5, "unit": "µm",
    }
    assert "µm" in text.read_text(encoding="utf-8")   # not µm
    assert result["channels"]["Height"]["meta"]["Tip"] == "Å-probe"


def test_to_json_accepts_a_string_path(two_channel_gwy, tmp_path):
    """to_hdf5 and to_gwy both take str or Path; this must not be the odd
    one out."""
    data = gwyddionpy.load(two_channel_gwy)
    out = tmp_path / "as_string.json"
    data.to_json(str(out))
    assert json.loads(out.read_text(encoding="utf-8"))["channels"]


def test_to_json_handles_a_file_with_no_channels(tmp_path):
    path = make_gwy(tmp_path / "empty.gwy", [])
    data = gwyddionpy.load(path)
    result = load_written(data, tmp_path)
    assert result["channels"] == {}


def test_to_json_records_unusual_shapes(tmp_path):
    """A single row and a single column must not collapse to the same shape."""
    path = make_gwy(
        tmp_path / "shapes.gwy",
        [{"name": "Row", "data": np.zeros((1, 8))},
         {"name": "Column", "data": np.zeros((8, 1))}],
    )
    data = gwyddionpy.load(path)
    channels = load_written(data, tmp_path)["channels"]
    assert channels["Row"]["shape"] == [1, 8]
    assert channels["Column"]["shape"] == [8, 1]


def test_to_json_file_ends_with_a_newline(two_channel_gwy, tmp_path):
    """Text files end in a newline, so the result is diffable and appendable."""
    data = gwyddionpy.load(two_channel_gwy)
    out = tmp_path / "nl.json"
    data.to_json(out)
    assert out.read_text(encoding="utf-8").endswith("}\n")


def test_to_json_overwrites_an_existing_file(two_channel_gwy, tmp_path):
    """A second export must replace the file, not append to it."""
    data = gwyddionpy.load(two_channel_gwy)
    out = tmp_path / "twice.json"
    out.write_text("stale content that is not JSON at all", encoding="utf-8")
    data.to_json(out)
    data.to_json(out)
    assert set(json.loads(out.read_text(encoding="utf-8"))["channels"]) == {
        "Height", "Phase",
    }
