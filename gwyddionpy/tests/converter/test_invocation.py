"""Running the converter, and the cases where it is deliberately not run:
a native .gwy must never reach it.

The failure paths point GWYDDIONPY_CONVERT at a nonexistent file, the one
way to make an installed converter unreachable without uninstalling it.
"""
import numpy as np
import pytest

import gwyddionpy
from gwyddionpy._run import ENV_VAR
from helpers.gwy_builder import make_gwy


@pytest.fixture
def unreachable_converter(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "/no/such/gwyconvert")


def test_gwy_input_needs_no_converter(unreachable_converter, tmp_path):
    path = make_gwy(tmp_path / "native.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2))}])
    data = gwyddionpy.load(path)
    assert "Height" in data.channels


def test_raw_input_without_a_converter_raises(unreachable_converter, tmp_path):
    raw = tmp_path / "scan.spm"
    raw.write_bytes(b"\x00" * 16)
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        gwyddionpy.load(raw)


def test_list_formats_without_a_converter_raises(unreachable_converter):
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        gwyddionpy.list_formats()


def test_nonexistent_file_raises():
    with pytest.raises(FileNotFoundError):
        gwyddionpy.load("/no/such/file.spm")


def test_list_formats_reports_a_real_registry():
    """A converter with an empty module registry still exits cleanly and
    returns a well-formed empty list, so check the formats are really there
    and each entry is complete."""
    formats = gwyddionpy.list_formats()

    # The count drifts with the Gwyddion release the converter was built
    # against, so this is a floor rather than an exact number.
    assert len(formats) >= 170
    names = {fmt["name"] for fmt in formats}
    assert "nanoscope" in names
    assert "gwyfile" in names

    for fmt in formats:
        assert fmt.keys() == {"name", "description", "can_load", "can_save",
                               "detectable"}
        assert fmt["name"] and fmt["description"]
        assert isinstance(fmt["can_load"], bool)
        assert isinstance(fmt["can_save"], bool)
        assert isinstance(fmt["detectable"], bool)
