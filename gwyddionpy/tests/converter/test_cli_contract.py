"""The gwyconvert command-line contract, exercised on the binary itself.

Everywhere else the converter is reached through gwyddionpy. Here it is run
directly, because the agreement between the two is what the Python side is
built on: an exit code that says which kind of thing went wrong, a result on
stdout that can be parsed without filtering, and diagnostics kept out of it.

    gwyconvert INPUT OUTPUT.gwy   ->  0 on success, 1 if the file cannot be
                                      read or the output cannot be written
    gwyconvert --list-formats     ->  0, the format list on stdout
    anything else                 ->  2, usage on stderr

warning: run in a bare environment the binary also emits GTK and GdkPixbuf
warnings on every call, successful ones included — a bundling artefact, not a
diagnostic. gwyddionpy suppresses them through converter_environment(), which
is the environment these tests use, so what is asserted here is the contract
as callers of this package actually receive it.
"""
import json
import os
import subprocess

import pytest

from gwyddionpy._run import converter_environment, find_converter
from helpers.requirements import require_specimen
from helpers.specimens import SPECIMENS_BY_ID

SUCCESS, FAILED_TO_CONVERT, BAD_INVOCATION = 0, 1, 2

WSXM = "wsxm/sample_0.top"


@pytest.fixture(scope="module")
def converter():
    return find_converter()


@pytest.fixture(scope="module")
def specimen():
    specimen = SPECIMENS_BY_ID[WSXM]
    require_specimen(specimen)
    return specimen


def run(converter, *args, cwd=None, env=None):
    return subprocess.run(
        [converter, *[str(a) for a in args]],
        capture_output=True, text=True, check=False, cwd=cwd,
        env=env if env is not None else converter_environment(),
    )


# --------------------------------------------------------------------------
# Exit codes
# --------------------------------------------------------------------------
def test_a_successful_conversion_reports_success(converter, specimen, tmp_path):
    result = run(converter, specimen.path, tmp_path / "out.gwy")
    assert result.returncode == SUCCESS
    assert (tmp_path / "out.gwy").is_file()


def test_listing_formats_reports_success(converter):
    assert run(converter, "--list-formats").returncode == SUCCESS


def test_an_unreadable_file_is_distinguished_from_a_bad_invocation(
    converter, tmp_path
):
    """The distinction the Python side depends on: 1 means the converter ran
    and could not read the file, 2 means it was called wrongly."""
    unreadable = tmp_path / "notes.spm"
    unreadable.write_text("this is not a measurement")
    assert run(converter, unreadable,
               tmp_path / "o.gwy").returncode == FAILED_TO_CONVERT


def test_a_missing_input_file_reports_a_conversion_failure(converter, tmp_path):
    assert run(converter, tmp_path / "absent.spm",
               tmp_path / "o.gwy").returncode == FAILED_TO_CONVERT


def test_an_unwritable_destination_reports_a_conversion_failure(
    converter, specimen, tmp_path
):
    assert run(converter, specimen.path,
               tmp_path / "no-such-directory" / "o.gwy").returncode == \
        FAILED_TO_CONVERT


@pytest.mark.parametrize("args", [
    pytest.param((), id="no arguments"),
    pytest.param(("only-one",), id="one argument"),
    pytest.param(("a", "b", "c"), id="three arguments"),
    pytest.param(("--help",), id="unsupported --help"),
    pytest.param(("--version",), id="unsupported --version"),
    pytest.param(("--nonsense",), id="unknown option"),
    pytest.param(("--list-formats", "extra"), id="list-formats with an extra"),
])
def test_a_bad_invocation_is_reported_as_such(converter, args):
    result = run(converter, *args)
    assert result.returncode == BAD_INVOCATION
    assert "Usage" in result.stderr


# --------------------------------------------------------------------------
# What goes on which stream
# --------------------------------------------------------------------------
def test_a_conversion_puts_only_its_result_on_stdout(converter, specimen,
                                                     tmp_path):
    result = run(converter, specimen.path, tmp_path / "out.gwy")
    parsed = json.loads(result.stdout)      # raises if anything else crept in
    assert parsed["module"] == specimen.module


def test_the_format_list_is_parsable_straight_off_stdout(converter):
    formats = json.loads(run(converter, "--list-formats").stdout)
    assert isinstance(formats, list)
    assert len(formats) >= 170
    assert all(entry.keys() == {"name", "description", "can_load", "can_save",
                                "detectable"} for entry in formats)


def test_a_successful_run_says_nothing_on_stderr(converter, specimen, tmp_path):
    """context part: this is the assertion the GTK/GdkPixbuf noise used to
    break. Those warnings appeared on every run and were quoted verbatim in
    this package's error messages."""
    result = run(converter, specimen.path, tmp_path / "out.gwy")
    assert result.stderr == "", f"unexpected output on stderr: {result.stderr!r}"


def test_listing_formats_says_nothing_on_stderr(converter):
    assert run(converter, "--list-formats").stderr == ""


def test_a_failure_explains_itself_on_stderr_and_leaves_stdout_empty(
    converter, tmp_path
):
    unreadable = tmp_path / "notes.spm"
    unreadable.write_text("not a measurement")
    result = run(converter, unreadable, tmp_path / "o.gwy")
    assert result.stdout == ""
    assert "cannot load" in result.stderr
    assert unreadable.name in result.stderr


def test_a_failure_names_the_file_it_could_not_write(converter, specimen,
                                                     tmp_path):
    result = run(converter, specimen.path, tmp_path / "missing" / "o.gwy")
    assert "cannot write" in result.stderr


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
@pytest.mark.parametrize("directory", [
    pytest.param("with spaces", id="spaces"),
    pytest.param("naïve-Ångström", id="non-ascii"),
    pytest.param("with'quote", id="single quote"),
    pytest.param("with(parens)", id="parentheses"),
])
def test_awkward_directory_names_are_handled(converter, specimen, tmp_path,
                                             directory):
    """The wrapper script passes arguments on to the real binary, so quoting
    mistakes there would surface exactly here."""
    target = tmp_path / directory
    target.mkdir()
    source = target / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())

    result = run(converter, source, target / "out put.gwy")
    assert result.returncode == SUCCESS, result.stderr
    assert (target / "out put.gwy").is_file()


def test_relative_and_absolute_paths_agree(converter, specimen, tmp_path):
    """context part: the two outputs are compared as data rather than as
    bytes. Gwyddion records the input path it was given inside the container,
    so an absolute run and a relative one differ in length by exactly the
    difference between the two path strings while describing identical
    measurements."""
    import numpy as np

    import gwyddionpy

    source = tmp_path / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())

    absolute = run(converter, source, tmp_path / "abs.gwy")
    relative = run(converter, source.name, "rel.gwy", cwd=tmp_path)

    assert absolute.returncode == relative.returncode == SUCCESS
    assert json.loads(absolute.stdout) == json.loads(relative.stdout)

    from_absolute = gwyddionpy.parse_gwy(tmp_path / "abs.gwy")
    from_relative = gwyddionpy.parse_gwy(tmp_path / "rel.gwy")
    assert list(from_absolute.channels) == list(from_relative.channels)
    for name, channel in from_absolute.channels.items():
        other = from_relative.channels[name]
        np.testing.assert_array_equal(channel.data, other.data)
        assert channel.xreal == other.xreal
        assert channel.meta == other.meta


def test_an_existing_output_file_is_replaced(converter, specimen, tmp_path):
    """context part: the converter overwrites without asking, which is what
    gwyddionpy relies on when it converts into a fresh temporary directory.
    Pinned so a future prompt-or-refuse behaviour would be noticed."""
    output = tmp_path / "out.gwy"
    output.write_bytes(b"stale contents that must not survive")

    result = run(converter, specimen.path, output)
    assert result.returncode == SUCCESS
    assert not output.read_bytes().startswith(b"stale")
    assert output.stat().st_size > 1000


def test_the_output_is_a_file_gwyddionpy_can_read(converter, specimen,
                                                  tmp_path):
    """Closes the loop: the binary's output is what the Python side parses."""
    import gwyddionpy

    output = tmp_path / "out.gwy"
    assert run(converter, specimen.path, output).returncode == SUCCESS
    assert len(gwyddionpy.parse_gwy(output).channels) == specimen.channels


def test_the_input_file_is_left_untouched(converter, specimen, tmp_path):
    source = tmp_path / specimen.path.name
    source.write_bytes(specimen.path.read_bytes())
    before = source.read_bytes()

    run(converter, source, tmp_path / "out.gwy")
    assert source.read_bytes() == before


# --------------------------------------------------------------------------
# The environment the package supplies
# --------------------------------------------------------------------------
def test_the_supplied_environment_is_what_keeps_stderr_clean(converter,
                                                             specimen,
                                                             tmp_path):
    """context part: without the suppression the binary is noisy in a bare
    environment. Kept as a test so the two halves cannot drift apart — if a
    future bundle stops needing it, this is what says so."""
    bare = {k: v for k, v in os.environ.items()
            if k not in ("GTK_MODULES", "GDK_PIXBUF_MODULE_FILE")}
    noisy = run(converter, specimen.path, tmp_path / "a.gwy", env=bare)
    quiet = run(converter, specimen.path, tmp_path / "b.gwy")

    assert quiet.stderr == ""
    assert noisy.returncode == quiet.returncode == SUCCESS
    # Same result either way; only the noise differs.
    assert json.loads(noisy.stdout) == json.loads(quiet.stdout)
