"""Real measurements carried through to the exported formats.

The reference tests establish that a file is read correctly; these carry
the same content into the dict, into HDF5 and back out through a written
.gwy, checking nothing is dropped, renamed or rounded away.
"""
import numpy as np
import pytest

import gwyddionpy
from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS

pytestmark = pytest.mark.formats

h5py = pytest.importorskip("h5py")


@pytest.fixture(scope="module", params=IMAGE_SPECIMENS, ids=lambda s: s.id)
def reading(request):
    specimen = request.param
    require_specimen(specimen)
    yield specimen, gwyddionpy.load(specimen.path)


def test_dict_keeps_every_channel(reading):
    specimen, data = reading
    exported = data.to_dict()
    assert len(exported["channels"]) == len(data.channels) == specimen.channels
    assert {entry["name"] for entry in exported["channels"].values()} == set(data.channels)


def test_dict_keeps_the_values_and_the_scale(reading):
    _, data = reading
    exported = data.to_dict()
    by_name = {entry["name"]: entry for entry in exported["channels"].values()}
    for name, channel in data.channels.items():
        entry = by_name[name]
        np.testing.assert_array_equal(entry["data"], channel.data)
        assert entry["xreal"] == channel.xreal
        assert entry["yreal"] == channel.yreal
        assert entry["si_unit_xy"] == channel.si_unit_xy
        assert entry["si_unit_z"] == channel.si_unit_z


def test_dict_reports_the_source_format(reading):
    specimen, data = reading
    assert data.to_dict()["source_format"] == specimen.module


def test_hdf5_keeps_every_channel_and_its_values(reading, tmp_path):
    specimen, data = reading
    out = tmp_path / "export.h5"
    data.to_hdf5(out)

    with h5py.File(out, "r") as handle:
        assert handle.attrs["source_format"] == specimen.module
        groups = handle["channels"]
        assert len(groups) == len(data.channels)
        for group in groups.values():
            channel = data.channels[group.attrs["name"]]
            np.testing.assert_array_equal(group["data"][()], channel.data)
            assert group.attrs["xreal"] == pytest.approx(channel.xreal)
            assert group.attrs["yreal"] == pytest.approx(channel.yreal)
            assert group.attrs["si_unit_xy"] == channel.si_unit_xy
            assert group.attrs["si_unit_z"] == channel.si_unit_z


def test_hdf5_carries_the_vendor_metadata(reading, tmp_path):
    """Flat mode stores the values verbatim, so it can be compared directly
    with what was read; the hierarchical default reshapes them."""
    _, data = reading
    out = tmp_path / "flat.h5"
    data.to_hdf5(out, hierarchical_meta=False)

    with h5py.File(out, "r") as handle:
        for group in handle["channels"].values():
            channel = data.channels[group.attrs["name"]]
            stored = dict(group["meta"].attrs)
            assert set(stored) == set(channel.meta)
            for key, value in channel.meta.items():
                assert stored[key] == value


def test_written_gwy_reads_back_with_the_same_content(reading, tmp_path):
    _, data = reading
    out = tmp_path / "written.gwy"
    data.to_gwy(out)
    reloaded = gwyddionpy.load(out)

    assert list(reloaded.channels) == list(data.channels)
    for name, channel in data.channels.items():
        returned = reloaded.channels[name]
        np.testing.assert_array_equal(returned.data, channel.data)
        assert returned.xreal == pytest.approx(channel.xreal)
        assert returned.yreal == pytest.approx(channel.yreal)
        assert returned.si_unit_xy == channel.si_unit_xy
        assert returned.si_unit_z == channel.si_unit_z
        assert returned.meta == channel.meta


def test_written_gwy_does_not_claim_a_source_format(reading, tmp_path):
    """source_format records which module read the original measurement. A
    .gwy written from that data was read by no vendor module, so the field
    is empty rather than inherited."""
    _, data = reading
    out = tmp_path / "written.gwy"
    data.to_gwy(out)
    assert gwyddionpy.load(out).source_format is None


def test_the_two_exports_agree_with_each_other(reading, tmp_path):
    """The dict and HDF5 layouts are meant to be structurally identical, so
    a caller can move between them without remapping anything."""
    _, data = reading
    out = tmp_path / "compare.h5"
    data.to_hdf5(out)
    exported = data.to_dict()

    with h5py.File(out, "r") as handle:
        assert set(handle["channels"]) == set(exported["channels"])
        for key, group in handle["channels"].items():
            entry = exported["channels"][key]
            assert group.attrs["name"] == entry["name"]
            np.testing.assert_array_equal(group["data"][()], entry["data"])
