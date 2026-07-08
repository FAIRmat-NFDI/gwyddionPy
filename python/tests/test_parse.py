import numpy as np
import pytest

import gwybridge
from conftest import make_gwy


def test_two_channels_full_fidelity(two_channel_gwy):
    data = gwybridge.load(two_channel_gwy)  # .gwy loads without a converter

    assert list(data.channels) == ["Height", "Phase"]
    height = data.channels["Height"]
    assert height.data.shape == (3, 4)
    np.testing.assert_allclose(height.data[2, 3], 11e-9)
    assert height.xreal == 2e-6 and height.yreal == 1.5e-6
    assert height.si_unit_xy == "m" and height.si_unit_z == "m"
    assert height.meta["Tip"] == "RTESPA-300"
    assert data.channels["Phase"].si_unit_z == "deg"


def test_metadata_union_first_wins(two_channel_gwy):
    data = gwybridge.load(two_channel_gwy)
    # Both channels define "Scan Rate"; the first channel wins in the union.
    assert data.metadata["Scan Rate"] == "1.0"
    assert data.metadata["Tip"] == "RTESPA-300"
    assert data.channels["Phase"].meta["Scan Rate"] == "2.0"


def test_untitled_channel_gets_numbered_name(tmp_path):
    path = make_gwy(tmp_path / "untitled.gwy", [{"data": np.zeros((2, 2))}])
    data = gwybridge.load(path)
    assert list(data.channels) == ["Channel 0"]


def test_missing_units_default_to_empty_string(tmp_path):
    path = make_gwy(tmp_path / "unitless.gwy", [{"data": np.ones((2, 3))}])
    channel = gwybridge.load(path).channels["Channel 0"]
    assert channel.si_unit_xy == "" and channel.si_unit_z == ""
    assert channel.xreal == 1.0 and channel.yreal == 1.0


def test_duplicate_titles_are_disambiguated(tmp_path):
    path = make_gwy(
        tmp_path / "dup.gwy",
        [
            {"name": "Height", "data": np.zeros((2, 2))},
            {"name": "Height", "data": np.ones((2, 2))},
        ],
    )
    data = gwybridge.load(path)
    assert list(data.channels) == ["Height", "Height (2)"]
    np.testing.assert_array_equal(data.channels["Height (2)"].data, 1.0)


def test_zero_channel_file(tmp_path):
    from gwyfile.objects import GwyContainer

    path = tmp_path / "empty.gwy"
    GwyContainer().tofile(str(path))
    data = gwybridge.load(path)
    assert data.channels == {}
    assert data.metadata == {}


def test_non_ascii_metadata(tmp_path):
    path = make_gwy(
        tmp_path / "unicode.gwy",
        [{"name": "Höhe µm", "data": np.zeros((2, 2)),
          "meta": {"Kommentar": "Messung α→β, 25 °C"}}],
    )
    data = gwybridge.load(path)
    assert data.channels["Höhe µm"].meta["Kommentar"] == "Messung α→β, 25 °C"


def test_nonexistent_file_raises():
    with pytest.raises(FileNotFoundError):
        gwybridge.load("/no/such/file.spm")
