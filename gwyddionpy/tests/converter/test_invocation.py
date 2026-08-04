"""What happens when gwyddionpy actually runs (or deliberately doesn't run)
the converter, and what the binary reports about itself.

Split out of the former test_run.py; discovery lives in test_discovery.py.
"""
import numpy as np
import pytest

import gwyddionpy
from gwyddionpy._run import ENV_VAR
from helpers.gwy_builder import make_gwy


@pytest.fixture
def no_converter_anywhere(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_VAR, raising=False)
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


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


def test_nonexistent_file_raises():
    with pytest.raises(FileNotFoundError):
        gwyddionpy.load("/no/such/file.spm")


@pytest.mark.converter
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
    # count will keep drifting as Gwyddion gains formats. The floor is what
    # a genuinely broken registry (this test's actual target) would fail.
    assert len(formats) >= 170
    names = {fmt["name"] for fmt in formats}
    assert "nanoscope" in names  # Bruker, exercised end-to-end in formats/
    assert "gwyfile" in names    # Gwyddion's own native format

    for fmt in formats:
        assert fmt.keys() == {"name", "description", "can_load", "can_save",
                               "detectable"}
        assert fmt["name"] and fmt["description"]
        assert isinstance(fmt["can_load"], bool)
        assert isinstance(fmt["can_save"], bool)
        assert isinstance(fmt["detectable"], bool)
