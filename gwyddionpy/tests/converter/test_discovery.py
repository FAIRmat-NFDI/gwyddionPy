"""Locating the gwyconvert binary, in order: an explicit path,
GWYDDIONPY_CONVERT, PATH, then the installed converter package. Driven
through the real environment rather than a stand-in.
"""
import os

import pytest

import gwyddionpy
from gwyddionpy._run import ENV_VAR, find_converter


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
