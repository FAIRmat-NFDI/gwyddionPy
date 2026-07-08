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
        assert height["meta"].attrs["Tip"] == "RTESPA-300"
        assert f["channels/Phase"].attrs["si_unit_z"] == "deg"


def test_hdf5_hierarchical_metadata(tmp_path):
    from conftest import make_gwy

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
        assert meta["group 2"].attrs["AmplitudeLimit"] == "2000 mV"
        assert meta["Samps"].attrs["line"] == "512"
        assert meta.attrs["Scan Rate"] == "1.0"  # plain keys stay at top level


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


def test_hdf5_channel_name_with_slash(tmp_path):
    from conftest import make_gwy

    path = make_gwy(tmp_path / "slash.gwy",
                    [{"name": "Amplitude/Error", "data": np.zeros((2, 2))}])
    data = gwyddionpy.load(path)
    out = tmp_path / "out.h5"
    data.to_hdf5(out)
    with h5py.File(out) as f:
        # "/" is HDF5's path separator; the group name is sanitized but the
        # original channel name is kept in the "name" attribute.
        assert f["channels/Amplitude_Error"].attrs["name"] == "Amplitude/Error"
