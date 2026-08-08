"""What must be true of the converter on whichever platform this is.

The wheel is built for Linux, macOS and Windows, and the three genuinely
differ: how the binary is launched, what a path looks like, whether the system
will report a child's peak memory. Every test here runs on all three and
asserts what should hold on the one it finds itself on — none of them skips,
because a leg that skips its own platform's tests is indistinguishable from a
leg that passes them.

Cross-platform agreement about *content* needs nothing extra: every platform
runs the same measurements against the same committed references, so any
build that passes them reads a file the same way as every other build that
passes them. What is left for this file is the handful of things that are
genuinely platform-specific.

These run only when a platform is declared, with --require-platform or
GWYDDIONPY_REQUIRE_PLATFORM. In CI each leg declares itself, and a leg that
declared the wrong one stops the run outright. On a developer's machine they
stay out of the way: there is nothing here the rest of the suite does not
already cover for the platform being worked on.
"""
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
    """context part: the declaration is enforced once at start-up, before any
    test runs, so a mismatched leg stops rather than reporting results for the
    wrong system. Repeated here so the guarantee is visible in the suite
    rather than buried in a hook."""
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
def test_the_converter_is_launched_the_way_this_platform_expects():
    """On Linux and macOS the bundle is reached through a shell wrapper that
    sets its library paths and then replaces itself with the real binary. On
    Windows there is no wrapper — the executable is launched directly."""
    converter = Path(find_converter())
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
    """Every module a committed measurement depends on must exist here.

    context part: this is checked live rather than against a stored list per
    platform. A file that reads on Linux and not on Windows is the bug worth
    catching, and running the real measurements on each platform catches it
    directly — the format tests do exactly that. A recorded list would add
    three files to regenerate on every Gwyddion upgrade to say the same thing
    less directly.
    """
    from helpers.specimens import SPECIMENS

    available = set(format_names())
    needed = {s.module for s in SPECIMENS}
    missing = sorted(needed - available)
    assert not missing, (
        f"this {platforms.current()} build cannot read {missing}, which "
        "committed measurements depend on"
    )


def test_the_format_list_is_well_formed_here():
    """A build that registers nothing still exits cleanly, so the entries are
    checked rather than only counted."""
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
    """context part: Windows uses backslashes and a drive letter, POSIX uses
    forward slashes. Passing the string form of a path exercises whichever
    this platform produces."""
    source = tmp_path / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())

    as_written = str(source)
    if platforms.supports("posix_paths"):
        assert "\\" not in as_written
    else:
        assert "\\" in as_written and as_written[1:3] == ":\\"

    assert len(gwyddionpy.load(as_written).channels) == specimen.channels


def test_the_converter_accepts_this_platforms_paths(specimen, tmp_path):
    """Straight to the binary, since the wrapper on POSIX and the executable
    on Windows quote their arguments differently."""
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
    """`getrusage` exists on POSIX and not on Windows. Both are asserted, so
    a platform that quietly loses the ability is noticed rather than skipped
    past."""
    try:
        import resource  # noqa: F401
        available = True
    except ImportError:
        available = False

    assert available == platforms.supports("peak_memory"), (
        f"{platforms.current()} was expected to "
        f"{'have' if platforms.supports('peak_memory') else 'lack'} getrusage"
    )
