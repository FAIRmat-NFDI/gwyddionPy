"""Locating the gwyconvert binary, in order: an explicit path,
GWYDDIONPY_CONVERT, PATH, the running env's bin folder (conda), then the
installed converter package. Driven through the real environment rather
than a stand-in.
"""
import os
import sys

import pytest

import gwyddionpy
from gwyddionpy._run import (
    BINARY_NAME,
    ENV_VAR,
    _find_in_env_prefix,
    find_converter,
)


def test_bundled_converter_is_found():
    """With nothing configured, discovery falls through to the converter
    shipped in the gwyddionpy-converter package."""
    binary = find_converter()
    assert os.path.isfile(binary)
    assert os.access(binary, os.X_OK), f"{binary} is not executable"


def test_bundled_converter_matches_the_installed_package():
    package = pytest.importorskip("gwyddionpy_converter")
    assert os.path.realpath(find_converter()) == os.path.realpath(
        str(package.binary_path())
    )


def test_explicit_path_wins(monkeypatch):
    """An explicitly passed path takes precedence over the environment."""
    bundled = find_converter()
    monkeypatch.setenv(ENV_VAR, "/no/such/gwyconvert")
    assert find_converter(bundled) == bundled


def test_environment_variable_is_used(monkeypatch):
    bundled = find_converter()
    monkeypatch.setenv(ENV_VAR, bundled)
    assert find_converter() == bundled


def test_environment_variable_pointing_nowhere(monkeypatch):
    """A configured but wrong path is reported against the variable that set
    it, rather than falling back to another converter."""
    monkeypatch.setenv(ENV_VAR, "/no/such/gwyconvert")
    with pytest.raises(gwyddionpy.ConverterNotFoundError, match=ENV_VAR):
        find_converter()


def test_explicit_path_pointing_nowhere():
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        find_converter("/no/such/gwyconvert")


def _place_converter(folder):
    """Put an executable stand-in named like gwyconvert into folder."""
    folder.mkdir(parents=True, exist_ok=True)
    name = BINARY_NAME + (".exe" if sys.platform == "win32" else "")
    path = folder / name
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_env_prefix_bin_is_searched(tmp_path):
    """conda's bin/ is found without PATH, as in an unactivated env (#12)."""
    placed = _place_converter(tmp_path / "bin")
    assert os.path.samefile(_find_in_env_prefix(str(tmp_path)), placed)


def test_env_prefix_windows_library_bin_is_searched(tmp_path):
    """conda on Windows puts executables in Library/bin."""
    placed = _place_converter(tmp_path / "Library" / "bin")
    assert os.path.samefile(_find_in_env_prefix(str(tmp_path)), placed)


def test_env_prefix_bin_wins_over_library_bin(tmp_path):
    placed = _place_converter(tmp_path / "bin")
    _place_converter(tmp_path / "Library" / "bin")
    assert os.path.samefile(_find_in_env_prefix(str(tmp_path)), placed)


def test_env_prefix_without_converter(tmp_path):
    """An env with no bin folder at all, and one with an empty bin."""
    assert _find_in_env_prefix(str(tmp_path)) is None
    (tmp_path / "bin").mkdir()
    assert _find_in_env_prefix(str(tmp_path)) is None


@pytest.mark.skipif(sys.platform == "win32", reason="no execute bit on Windows")
def test_env_prefix_ignores_a_non_executable_file(tmp_path):
    _place_converter(tmp_path / "bin").chmod(0o644)
    assert _find_in_env_prefix(str(tmp_path)) is None
