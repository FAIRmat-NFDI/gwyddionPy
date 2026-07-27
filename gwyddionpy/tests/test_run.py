"""Converter discovery and failure paths. These manipulate the process
environment (not mocks) to exercise real code paths."""
import sys

import numpy as np
import pytest

import gwyddionpy
from gwyddionpy._errors import ConverterNotFoundError
from gwyddionpy._run import ENV_VAR, find_converter
from conftest import make_gwy

try:
    find_converter()
    HAVE_CONVERTER = True
except ConverterNotFoundError:
    HAVE_CONVERTER = False


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
    """gwyddionpy-converter is now a hard dependency (pyproject.toml) that
    ships gwyconvert as installed-package data; find_converter() must fall
    back to gwyddionpy_converter.binary_path() when PATH/env var don't
    resolve — this is the discovery step that was missing (D6 item 4)."""
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


@pytest.mark.converter
@pytest.mark.skipif(not HAVE_CONVERTER, reason="gwyconvert not available")
def test_list_formats_reports_known_formats():
    """Verify gwyconvert reports a real, well-formed format registry.

    Guards against gwyconvert linking against a stub or empty module
    registry instead of Gwyddion's actual file-format parsers — a broken
    build could still exit 0 and return an empty or malformed list, and
    this would be the only test to catch it.
    """
    formats = gwyddionpy.list_formats()

    # Not an exact count on purpose: the system-package build reports 170
    # (Gwyddion 2.60), the source-tarball build gwyddionpy-converter/ci/build-*.sh
    # uses reports 185 (Gwyddion 2.71) — both are legitimate, and the
    # count will keep drifting as Gwyddion gains formats. > 100 is a
    # floor that only a genuinely broken registry (this test's actual
    # target) would fail.
    assert len(formats) >= 170
    names = {fmt["name"] for fmt in formats}
    assert "nanoscope" in names  # Bruker, exercised end-to-end in test_real_files.py
    assert "gwyfile" in names    # Gwyddion's own native format

    for fmt in formats:
        assert fmt.keys() == {"name", "description", "can_load", "can_save",
                               "detectable"}
        assert fmt["name"] and fmt["description"]
        assert isinstance(fmt["can_load"], bool)
        assert isinstance(fmt["can_save"], bool)
        assert isinstance(fmt["detectable"], bool)
