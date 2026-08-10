"""What must be true of the converter on whichever platform this is: how
the binary is launched, how a path is spelled, which calls exist.

Nothing skips, because a leg that skips its own tests looks like one that
passes them. Runs only when --require-platform or
GWYDDIONPY_REQUIRE_PLATFORM names the platform.
"""
import os
import subprocess
from pathlib import Path

import pytest

import gwyddionpy
from gwyddionpy._run import converter_environment, find_converter
from helpers import platforms
from helpers.requirements import require_specimen
from helpers.specimens import SPECIMENS_BY_ID

WSXM = "wsxm/sample_0.top"

pytestmark = pytest.mark.platform


@pytest.fixture(scope="module")
def specimen():
    specimen = SPECIMENS_BY_ID[WSXM]
    require_specimen(specimen)
    return specimen


def format_names():
    return sorted(entry["name"] for entry in gwyddionpy.list_formats())


# --------------------------------------------------------------------------
# The declaration itself
# --------------------------------------------------------------------------
def test_this_platform_is_one_the_converter_is_built_for():
    assert platforms.current() in platforms.KNOWN


def test_a_declared_platform_matches_the_one_running(required_platform):
    """Enforced once at start-up, before any test runs. Repeated here so the
    guarantee is visible in the suite rather than only in a hook."""
    assert required_platform is not None, (
        "these tests only run when a platform is declared, so reaching this "
        "without one means the marker is no longer being honoured"
    )
    assert required_platform == platforms.current()


def test_platform_labels_are_understood():
    """The labels CI actually writes must map onto the three names."""
    for label, expected in [
        ("ubuntu-latest", platforms.LINUX), ("macos-15", platforms.MACOS),
        ("macos-15-intel", platforms.MACOS), ("windows-latest", platforms.WINDOWS),
        ("manylinux_2_28_x86_64", platforms.LINUX), ("win_amd64", platforms.WINDOWS),
    ]:
        assert platforms.normalize(label) == expected, label

    with pytest.raises(ValueError):
        platforms.normalize("solaris")


# --------------------------------------------------------------------------
# How the converter is launched here
# --------------------------------------------------------------------------
def test_the_converter_in_use_is_an_executable_file():
    """True of whichever converter this run found, however it was obtained."""
    converter = Path(find_converter())
    assert converter.is_file()
    assert os.access(converter, os.X_OK), f"{converter} is not executable"


def test_the_bundled_converter_is_launched_the_way_this_platform_expects():
    """Linux and macOS reach the bundle through a shell wrapper; Windows
    launches the executable directly. The wrapper belongs to the bundle, so
    this asks the installed package rather than whichever converter
    discovery happened to pick."""
    package = pytest.importorskip(
        "gwyddionpy_converter",
        reason="no converter wheel installed, so there is no bundle to check",
    )
    converter = Path(package.binary_path())
    assert converter.is_file()

    starts_with_shebang = converter.read_bytes()[:2] == b"#!"
    if platforms.supports("wrapper_script"):
        assert starts_with_shebang, (
            f"{converter} was expected to be a wrapper script on "
            f"{platforms.current()} but does not start with #!"
        )
        script = converter.read_text(encoding="utf-8", errors="replace")
        assert "exec " in script, (
            "the wrapper must exec the real binary, so that stopping the "
            "process stops the conversion"
        )
    else:
        assert not starts_with_shebang, (
            f"{converter} looks like a shell script on {platforms.current()}, "
            "where there should be no wrapper"
        )
        assert converter.suffix.lower() == ".exe", converter


def test_the_converter_runs_here():
    formats = gwyddionpy.list_formats()
    assert len(formats) >= 150, (
        f"only {len(formats)} formats on {platforms.describe()} — a build "
        "that registers almost nothing still exits cleanly"
    )


# --------------------------------------------------------------------------
# The formats this platform's build carries
# --------------------------------------------------------------------------
def test_this_build_carries_the_modules_the_measurements_need():
    """Checked live rather than against a stored list per platform: the bug
    worth catching is a file that reads on one platform and not another."""
    from helpers.specimens import SPECIMENS

    available = set(format_names())
    needed = {s.module for s in SPECIMENS}
    missing = sorted(needed - available)
    assert not missing, (
        f"this {platforms.current()} build cannot read {missing}, which "
        "committed measurements depend on"
    )


def test_the_format_list_is_well_formed_here():
    """A build that registers nothing still exits cleanly, so the entries
    are checked rather than only counted."""
    formats = gwyddionpy.list_formats()
    for entry in formats:
        assert entry.keys() == {"name", "description", "can_load", "can_save",
                                "detectable"}
        assert entry["name"] and entry["description"]

    names = [entry["name"] for entry in formats]
    assert len(names) == len(set(names)), "the same format is listed twice"


# --------------------------------------------------------------------------
# Paths, which is where platforms differ most
# --------------------------------------------------------------------------
def test_a_path_with_spaces_works_here(specimen, tmp_path):
    directory = tmp_path / "a folder with spaces"
    directory.mkdir()
    source = directory / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())

    data = gwyddionpy.load(source)
    assert len(data.channels) == specimen.channels


def test_a_path_with_non_ascii_characters_works_here(specimen, tmp_path):
    directory = tmp_path / "Ångström-messungen"
    directory.mkdir()
    source = directory / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())

    data = gwyddionpy.load(source)
    assert len(data.channels) == specimen.channels


def test_the_native_separator_is_accepted(specimen, tmp_path):
    """Passing a path in string form exercises whichever separator this
    platform produces."""
    source = tmp_path / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())

    as_written = str(source)
    if platforms.supports("posix_paths"):
        assert "\\" not in as_written
    else:
        assert "\\" in as_written and as_written[1:3] == ":\\"

    assert len(gwyddionpy.load(as_written).channels) == specimen.channels


def test_the_converter_accepts_this_platforms_paths(specimen, tmp_path):
    """Straight to the binary, since the wrapper script and the bare
    executable quote their arguments differently."""
    output = tmp_path / "out put.gwy"
    result = subprocess.run(
        [find_converter(), str(specimen.path), str(output)],
        capture_output=True, text=True, check=False, env=converter_environment(),
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()


# --------------------------------------------------------------------------
# Capabilities that differ, asserted rather than skipped
# --------------------------------------------------------------------------
def test_peak_memory_is_measurable_exactly_where_it_should_be():
    """`getrusage` exists on Linux and macOS but not Windows. Both cases are
    asserted, so a platform quietly losing it is noticed."""
    try:
        import resource  # noqa: F401
        available = True
    except ImportError:
        available = False

    assert available == platforms.supports("peak_memory"), (
        f"{platforms.current()} was expected to "
        f"{'have' if platforms.supports('peak_memory') else 'lack'} getrusage"
    )
