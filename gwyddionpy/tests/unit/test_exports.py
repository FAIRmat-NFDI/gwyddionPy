import numpy as np
import pytest

import gwyddionpy

h5py = pytest.importorskip("h5py")


def test_hdf5_round_trip(two_channel_gwy, tmp_path):
    data = gwyddionpy.load(two_channel_gwy)
    out = tmp_path / "out.h5"
    data.to_hdf5(out)

    with h5py.File(out) as f:
        assert set(f["channels"]) == {"Height", "Phase"}
        height = f["channels/Height"]
        np.testing.assert_array_equal(
            height["data"][()], data.channels["Height"].data
        )
        assert height["data"].dtype == np.float64
        assert height.attrs["xreal"] == 2e-6
        assert height.attrs["si_unit_z"] == "m"
        assert height["meta/Tip"].asstr()[()] == "RTESPA-300"
        assert f["channels/Phase"].attrs["si_unit_z"] == "deg"


def test_hdf5_hierarchical_metadata(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(
        tmp_path / "hier.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"2:AmplitudeLimit": "2000 mV",
                   "Samps/line": "512",
                   "Scan Rate": "1.0"}}],
    )
    data = gwyddionpy.load(path)
    out = tmp_path / "out.h5"
    data.to_hdf5(out)
    with h5py.File(out) as f:
        meta = f["channels/Height/meta"]
        # "<number> <unit>" values split into dataset value + unit attribute
        assert meta["group 2/AmplitudeLimit"][()] == 2000
        assert meta["group 2/AmplitudeLimit"].attrs["unit"] == "mV"
        assert meta["Samps/line"][()] == 512
        assert "unit" not in meta["Samps/line"].attrs
        assert meta["Scan Rate"][()] == 1.0  # plain keys stay at top level


def test_hdf5_metadata_value_parsing(tmp_path):
    from helpers.gwy_builder import make_gwy

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
    out = tmp_path / "out.h5"
    data.to_hdf5(out)
    with h5py.File(out) as f:
        meta = f["channels/Height/meta"]
        assert meta["Drive Routing"].asstr()[()] == "Tapping Piezo"
        assert "unit" not in meta["Drive Routing"].attrs
        assert meta["Sensitivity"][()] == 1
        assert meta["Sensitivity"].attrs["unit"] == "nA/V"
        assert meta["Engage X Pos"][()] == -19783.4
        assert meta["Engage X Pos"].attrs["unit"] == "um"
        assert meta["Gains"].asstr()[()] == "0.05 0.05"
        assert meta["Padded"][()] == 1.0
        assert "unit" not in meta["Padded"].attrs


def test_hdf5_metadata_key_collisions(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(
        tmp_path / "clash.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"2:Limit": "1 mV",
                   "group 2/Limit": "2 mV",   # same node as the key above
                   "Samps": "top",
                   "Samps/line": "512"}}],    # needs a group where a
    )                                         # dataset already sits
    data = gwyddionpy.load(path)
    out = tmp_path / "out.h5"
    data.to_hdf5(out)
    with h5py.File(out) as f:
        meta = f["channels/Height/meta"]
        assert meta["group 2/Limit"][()] == 1
        # colliding keys survive under their flat name at the meta root
        assert meta["group 2_Limit"][()] == 2
        assert meta["Samps"].asstr()[()] == "top"
        assert meta["Samps_line"][()] == 512


def test_hdf5_flat_metadata_option(two_channel_gwy, tmp_path):
    data = gwyddionpy.load(two_channel_gwy)
    out = tmp_path / "flat.h5"
    data.to_hdf5(out, hierarchical_meta=False)
    with h5py.File(out) as f:
        meta = f["channels/Height/meta"]
        assert meta.attrs["Tip"] == "RTESPA-300"
        assert len(meta.keys()) == 0  # no nested groups in flat mode


def test_gwy_export_round_trip(two_channel_gwy, tmp_path):
    data = gwyddionpy.load(two_channel_gwy)
    out = tmp_path / "back.gwy"
    data.to_gwy(out)

    again = gwyddionpy.load(out)  # .gwy loads without a converter
    assert list(again.channels) == ["Height", "Phase"]
    height = again.channels["Height"]
    np.testing.assert_allclose(height.data, data.channels["Height"].data)
    assert height.xreal == 2e-6
    assert height.si_unit_z == "m"
    assert height.meta["Tip"] == "RTESPA-300"
    assert again.channels["Phase"].si_unit_z == "deg"


def test_to_dict(two_channel_gwy):
    data = gwyddionpy.load(two_channel_gwy)
    result = data.to_dict()

    assert result["source_format"] == data.source_format
    assert set(result["channels"]) == {"Height", "Phase"}
    height = result["channels"]["Height"]
    assert height["name"] == "Height"
    np.testing.assert_array_equal(height["data"], data.channels["Height"].data)
    assert height["xreal"] == 2e-6
    assert height["si_unit_z"] == "m"
    assert height["meta"]["Tip"] == "RTESPA-300"
    assert result["channels"]["Phase"]["si_unit_z"] == "deg"


def test_to_dict_hierarchical_metadata(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(
        tmp_path / "hier.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"2:AmplitudeLimit": "2000 mV",
                   "Samps/line": "512",
                   "Scan Rate": "1.0"}}],
    )
    data = gwyddionpy.load(path)
    meta = data.to_dict()["channels"]["Height"]["meta"]
    # mirrors test_hdf5_hierarchical_metadata: same grouping and value/unit
    # split as the HDF5 export, just as nested dicts instead of groups.
    assert meta["group 2"]["AmplitudeLimit"] == {"value": 2000, "unit": "mV"}
    assert meta["Samps"]["line"] == 512
    assert meta["Scan Rate"] == 1.0  # plain keys stay at top level


def test_to_dict_metadata_value_parsing(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(
        tmp_path / "vals.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"Drive Routing": "Tapping Piezo",   # plain text
                   "Sensitivity": "1 nA/V",            # unit with a slash
                   "Engage X Pos": "-19783.4 um",       # negative number
                   "Gains": "0.05 0.05",                # list: stays a string
                   "Padded": "1.000000 "}}],            # trailing whitespace
    )
    data = gwyddionpy.load(path)
    meta = data.to_dict()["channels"]["Height"]["meta"]
    assert meta["Drive Routing"] == "Tapping Piezo"
    assert meta["Sensitivity"] == {"value": 1, "unit": "nA/V"}
    assert meta["Engage X Pos"] == {"value": -19783.4, "unit": "um"}
    assert meta["Gains"] == "0.05 0.05"
    assert meta["Padded"] == 1.0


def test_to_dict_metadata_key_collisions(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(
        tmp_path / "clash.gwy",
        [{"name": "Height", "data": np.zeros((2, 2)),
          "meta": {"2:Limit": "1 mV",
                   "group 2/Limit": "2 mV",   # same node as the key above
                   "Samps": "top",
                   "Samps/line": "512"}}],    # needs a group where a
    )                                         # leaf already sits
    data = gwyddionpy.load(path)
    meta = data.to_dict()["channels"]["Height"]["meta"]
    assert meta["group 2"]["Limit"] == {"value": 1, "unit": "mV"}
    # colliding keys survive under their flat name at the meta root
    assert meta["group 2_Limit"] == {"value": 2, "unit": "mV"}
    assert meta["Samps"] == "top"
    assert meta["Samps_line"] == 512


def test_to_dict_flat_metadata_option(two_channel_gwy):
    data = gwyddionpy.load(two_channel_gwy)
    result = data.to_dict(hierarchical_meta=False)
    meta = result["channels"]["Height"]["meta"]
    # raw strings, unsplit — no nested groups, no value/unit parsing
    assert meta == {"Scan Rate": "1.0", "Tip": "RTESPA-300"}


def test_to_dict_channel_name_with_slash(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(tmp_path / "slash.gwy",
                    [{"name": "Amplitude/Error", "data": np.zeros((2, 2))}])
    data = gwyddionpy.load(path)
    result = data.to_dict()
    # "/" is sanitized in the key, same as the HDF5 group name, but the
    # original channel name is kept in the "name" field.
    assert result["channels"]["Amplitude_Error"]["name"] == "Amplitude/Error"


def test_hdf5_channel_name_with_slash(tmp_path):
    from helpers.gwy_builder import make_gwy

    path = make_gwy(tmp_path / "slash.gwy",
                    [{"name": "Amplitude/Error", "data": np.zeros((2, 2))}])
    data = gwyddionpy.load(path)
    out = tmp_path / "out.h5"
    data.to_hdf5(out)
    with h5py.File(out) as f:
        # "/" is HDF5's path separator; the group name is sanitized but the
        # original channel name is kept in the "name" attribute.
        assert f["channels/Amplitude_Error"].attrs["name"] == "Amplitude/Error"
