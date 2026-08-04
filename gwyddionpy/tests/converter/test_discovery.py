"""How gwyddionpy finds a gwyconvert binary, and how it fails when it can't.

Split out of the former test_run.py: discovery answers "which binary" and is
driven by the process environment, while invocation (test_invocation.py)
answers "what happens when we run it". They break for unrelated reasons.

These manipulate the real environment rather than mocking the lookup, so the
production code path is the one under test.
"""
import sys

import pytest

import gwyddionpy
from gwyddionpy._run import ENV_VAR, find_converter


@pytest.fixture
def no_converter_anywhere(monkeypatch, tmp_path):
    """Environment where gwyconvert cannot be found: env var unset and PATH
    reduced to an empty directory."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


def test_converter_not_found():
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        find_converter()


def test_env_var_pointing_nowhere(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "/no/such/gwyconvert")
    with pytest.raises(gwyddionpy.ConverterNotFoundError, match=ENV_VAR):
        find_converter()


def test_explicit_converter_pointing_nowhere():
    with pytest.raises(gwyddionpy.ConverterNotFoundError):
        find_converter("/no/such/gwyconvert")


def _install_fake_converter_package(tmp_path, monkeypatch, body):
    """Make a real, importable `gwyddionpy_converter` module (not a mock)
    available on sys.path, with the given `binary_path()` body."""
    pkg_root = tmp_path / "site-packages"
    pkg_dir = pkg_root / "gwyddionpy_converter"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(body)
    monkeypatch.syspath_prepend(str(pkg_root))
    monkeypatch.delitem(sys.modules, "gwyddionpy_converter", raising=False)


def test_installed_converter_package_fallback(
    no_converter_anywhere, tmp_path, monkeypatch
):
    """The `gwyddionpy[converter]` extra ships gwyconvert as package data,
    so find_converter() must fall back to
    gwyddionpy_converter.binary_path() once the env var and PATH come up
    empty. This is what makes `pip install "gwyddionpy[converter]"` work
    with no further setup."""
    binary = tmp_path / "gwyconvert"
    binary.write_text("#!/bin/sh\necho stub\n")
    binary.chmod(0o755)
    _install_fake_converter_package(
        tmp_path,
        monkeypatch,
        "from pathlib import Path\n\n\n"
        f"def binary_path():\n    return Path({str(binary)!r})\n",
    )
    try:
        assert find_converter() == str(binary)
    finally:
        sys.modules.pop("gwyddionpy_converter", None)


def test_installed_converter_package_binary_missing_falls_through(
    no_converter_anywhere, tmp_path, monkeypatch
):
    """A gwyddionpy_converter package whose bundled binary is missing (e.g.
    an unbuilt platform wheel) must not raise from find_converter() itself -
    it falls through to the next discovery step."""
    _install_fake_converter_package(
        tmp_path,
        monkeypatch,
        "def binary_path():\n"
        "    raise FileNotFoundError('not built for this platform')\n",
    )
    try:
        with pytest.raises(gwyddionpy.ConverterNotFoundError):
            find_converter()
    finally:
        sys.modules.pop("gwyddionpy_converter", None)
