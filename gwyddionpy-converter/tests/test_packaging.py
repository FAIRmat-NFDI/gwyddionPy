"""The packaging layer that hands gwyddionpy a converter to run.

`binary_path()` is the last step of the converter search and the only one
that matters once the wheel is installed, so everything it promises is
checked here against the really installed package.

Not covered yet: `setup.py`'s `platform_tag()`.
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

gwyddionpy_converter = pytest.importorskip(
    "gwyddionpy_converter",
    reason="the converter wheel must be installed for its packaging to be tested",
)


@pytest.fixture(scope="module")
def binary():
    return gwyddionpy_converter.binary_path()


def test_the_reported_path_exists(binary):
    assert binary.is_file(), f"binary_path() points at {binary}, which is not a file"


def test_the_reported_path_is_absolute(binary):
    """A relative path would resolve differently depending on where the
    caller happened to be working."""
    assert binary.is_absolute()


def test_the_binary_is_executable(binary):
    mode = binary.stat().st_mode
    assert mode & stat.S_IXUSR, f"{binary} is not executable by its owner"
    assert os.access(binary, os.X_OK)


def test_the_binary_lives_inside_the_installed_package(binary):
    """It ships as package data, so it must be under the package rather than
    somewhere else on the machine that happens to have a converter."""
    package_root = Path(gwyddionpy_converter.__file__).parent
    assert package_root in binary.parents


def test_a_path_object_is_returned(binary):
    assert isinstance(binary, Path)


def test_repeated_calls_agree(binary):
    assert gwyddionpy_converter.binary_path() == binary


def test_the_binary_actually_runs(binary):
    """Being present and executable is not the same as working."""
    result = subprocess.run([str(binary), "--list-formats"],
                            capture_output=True, text=True, check=False,
                            env={**os.environ, "GTK_MODULES": "",
                                 "GDK_PIXBUF_MODULE_FILE": os.devnull})
    assert result.returncode == 0, result.stderr
    assert result.stdout.lstrip().startswith("["), "no format list on stdout"


def test_a_missing_bundle_is_reported_clearly(monkeypatch, tmp_path):
    """What a wheel built for the wrong platform produces. It must name the
    problem: gwyddionpy reads it as "try the next place to look", so an
    unclear message resurfaces later as a converter that cannot be found."""
    monkeypatch.setattr(gwyddionpy_converter, "_BIN_DIR", tmp_path / "bin")

    with pytest.raises(FileNotFoundError) as raised:
        gwyddionpy_converter.binary_path()

    message = str(raised.value)
    assert "gwyconvert" in message
    assert "wheel" in message or "platform" in message


def test_gwyddionpy_finds_this_binary_when_nothing_else_is_set(monkeypatch,
                                                               tmp_path,
                                                               binary):
    """The seam between the two packages: gwyddionpy falls back to the
    installed wheel once every other candidate has come up empty."""
    run = pytest.importorskip("gwyddionpy._run")

    monkeypatch.delenv(run.ENV_VAR, raising=False)
    empty = tmp_path / "nothing"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert os.path.realpath(run.find_converter()) == os.path.realpath(str(binary))


def test_the_package_declares_its_licence():
    """The wheel carries GPL-licensed Gwyddion libraries. Saying so is what
    lets gwyddionpy itself stay Apache-2.0."""
    from importlib import metadata

    try:
        info = metadata.metadata("gwyddionpy-converter")
    except metadata.PackageNotFoundError:      # pragma: no cover
        pytest.skip("distribution metadata not available for this install")

    declared = " ".join(filter(None, [
        info.get("License", ""), *info.get_all("Classifier", []),
    ]))
    assert "GPL" in declared.upper(), f"no GPL statement in: {declared[:200]}"


#: What a shared library is called in the bundle. Linux puts the version in
#: the file name (libgwyddion2.so.0) and macOS does not
#: (libgwyddion2.0.dylib), so both spellings are matched.
LIBRARY_PATTERNS = ("lib/*.so", "lib/*.so.*", "lib/*.dylib")


def test_the_bundle_carries_its_own_libraries(binary):
    """The bundle ships Gwyddion and its dependencies beside the binary,
    which is what lets it run on a machine with no Gwyddion installed."""
    if binary.read_bytes()[:2] != b"#!":
        pytest.skip("no wrapper script on this platform")

    bundled = [path for pattern in LIBRARY_PATTERNS
               for path in binary.parent.glob(pattern)]
    assert bundled, f"no bundled libraries beside {binary}"
    assert any("gwy" in path.name for path in bundled), (
        "the bundle carries libraries but none of them are Gwyddion's"
    )


def test_python_version_independence():
    """Tagged py3-none-<platform>: the payload runs as a subprocess and
    depends on no Python application binary interface (ABI)."""
    assert sys.version_info >= (3, 9)
    assert gwyddionpy_converter.binary_path().is_file()
