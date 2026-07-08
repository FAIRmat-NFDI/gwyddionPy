"""Converter discovery and failure paths. These manipulate the process
environment (not mocks) to exercise real code paths."""
import numpy as np
import pytest

import gwyddionpy
from gwyddionpy._run import ENV_VAR, find_converter
from conftest import make_gwy


@pytest.fixture
def no_converter_anywhere(monkeypatch, tmp_path):
    """Environment where gwyconvert cannot be found: env var unset and PATH
    reduced to an empty directory."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


def test_converter_not_found(no_converter_anywhere):
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        find_converter()


def test_env_var_pointing_nowhere(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "/no/such/gwyconvert")
    with pytest.raises(gwyddionpy.ConverterNotFoundError, match=ENV_VAR):
        find_converter()


def test_explicit_converter_pointing_nowhere():
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        find_converter("/no/such/gwyconvert")


def test_raw_load_without_converter_raises(no_converter_anywhere, tmp_path):
    raw = tmp_path / "scan.spm"
    raw.write_bytes(b"\x00" * 16)
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        gwyddionpy.load(raw)


def test_gwy_load_needs_no_converter(no_converter_anywhere, tmp_path):
    # Native .gwy input must bypass the converter entirely.
    path = make_gwy(tmp_path / "native.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2))}])
    data = gwyddionpy.load(path)
    assert "Height" in data.channels


def test_list_formats_without_converter(no_converter_anywhere):
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        gwyddionpy.list_formats()
