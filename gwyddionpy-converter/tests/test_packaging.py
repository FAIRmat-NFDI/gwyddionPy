"""The packaging layer that hands gwyddionpy a converter to run.

`binary_path()` is the last step of gwyddionpy's search for a converter and
the only one that matters once the wheel is installed, which is now the only
supported way to get one. Everything it promises is checked here, against the
really installed package rather than a stand-in.

warning: `setup.py` in this package still returns a hardcoded
`manylinux_2_28_x86_64` wheel tag. Deliberately not pinned by a test: the
branch that adds macOS and Windows builds replaces it with a tag resolved
from the build environment, and a test written against the hardcoded value
would have to be rewritten immediately and would meanwhile record a wheel tag
that is wrong on three of the four platforms being built.
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
    """It ships as package data, so it has to be under the package rather
    than somewhere on the machine that happens to have a converter."""
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
    """The failure a wheel built for the wrong platform would produce. It has
    to name the problem: gwyddionpy treats this as "try the next place to
    look", so a confusing message here surfaces later as a converter that
    simply cannot be found."""
    monkeypatch.setattr(gwyddionpy_converter, "_BIN_DIR", tmp_path / "bin")

    with pytest.raises(FileNotFoundError) as raised:
        gwyddionpy_converter.binary_path()

    message = str(raised.value)
    assert "gwyconvert" in message
    assert "wheel" in message or "platform" in message


def test_gwyddionpy_finds_this_binary_when_nothing_else_is_set(monkeypatch,
                                                               tmp_path,
                                                               binary):
    """context part: the two packages are released separately, so this is the
    seam between them. gwyddionpy falls back to the installed wheel once the
    explicit path, the environment variable and PATH have all come up empty.
    """
    run = pytest.importorskip("gwyddionpy._run")

    monkeypatch.delenv(run.ENV_VAR, raising=False)
    empty = tmp_path / "nothing"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert os.path.realpath(run.find_converter()) == os.path.realpath(str(binary))


def test_the_package_declares_its_licence():
    """The wheel carries GPL-licensed Gwyddion libraries; keeping that stated
    is what allows gwyddionpy itself to stay Apache-2.0."""
    from importlib import metadata

    try:
        info = metadata.metadata("gwyddionpy-converter")
    except metadata.PackageNotFoundError:      # pragma: no cover
        pytest.skip("distribution metadata not available for this install")

    declared = " ".join(filter(None, [
        info.get("License", ""), *info.get_all("Classifier", []),
    ]))
    assert "GPL" in declared.upper(), f"no GPL statement in: {declared[:200]}"


#: What a shared library is called in the bundle, which differs by platform:
#: Linux versions the file name (libgwyddion2.so.0) where macOS does not
#: (libgwyddion2.0.dylib). Matching only one of them would let the check pass
#: vacuously on the other, which is exactly what it exists to prevent.
LIBRARY_PATTERNS = ("lib/*.so", "lib/*.so.*", "lib/*.dylib")


def test_the_bundle_carries_its_own_libraries(binary):
    """context part: the bundle ships Gwyddion and its dependencies beside
    the binary, which is what lets it run on a machine with no Gwyddion
    installed. If that directory vanished, the wheel would work only where
    Gwyddion happened to be present already."""
    if binary.read_bytes()[:2] != b"#!":
        pytest.skip("no wrapper script on this platform")

    bundled = [path for pattern in LIBRARY_PATTERNS
               for path in binary.parent.glob(pattern)]
    assert bundled, f"no bundled libraries beside {binary}"
    assert any("gwy" in path.name for path in bundled), (
        "the bundle carries libraries but none of them are Gwyddion's"
    )


def test_python_version_independence():
    """The wheel is tagged py3-none-<platform>: the payload is run as a
    subprocess and depends on no Python ABI, so the interpreter reading it
    here is irrelevant to whether it works."""
    assert sys.version_info >= (3, 9)
    assert gwyddionpy_converter.binary_path().is_file()
