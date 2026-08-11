"""Reading files that are damaged, truncated or not what they claim to be.

Each must fail quickly with a typed error, never hang or return data, and
leave nothing behind. The .gwy cases matter most: those are read in-process
by gwyfile, which raises whatever the damage happens to break.
"""
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

import gwyddionpy
from helpers.gwy_builder import make_gwy
from helpers.specimens import SPECIMENS_BY_ID

#: Generous enough never to fire on a healthy machine, small enough that a
#: real hang fails the test rather than stalling the suite.
RESPONSE_LIMIT_SECONDS = 30.0

BRUKER = "bruker_nanoscope/VGEP-15m-.0_00000.spm"


@pytest.fixture(scope="module")
def real_bytes():
    """The opening bytes of a genuine vendor file, to build partial ones."""
    return SPECIMENS_BY_ID[BRUKER].path.read_bytes()[:200_000]


def build_raw_cases(tmp_path, real):
    """Damaged inputs carrying an extension that promises a real format."""
    cases = {}

    empty = tmp_path / "empty.spm"
    empty.write_bytes(b"")
    cases["empty file"] = empty

    noise = tmp_path / "noise.spm"
    noise.write_bytes(bytes(range(256)) * 16)
    cases["arbitrary bytes"] = noise

    text = tmp_path / "text.spm"
    text.write_text("this is a note about a scan, not a scan\n")
    cases["text in a binary format"] = text

    stub = tmp_path / "stub.spm"
    stub.write_bytes(real[:1024])
    cases["header cut off early"] = stub

    partial = tmp_path / "partial.spm"
    partial.write_bytes(real[:100_000])
    cases["header intact, data truncated"] = partial

    garbled = tmp_path / "garbled.spm"
    garbled.write_bytes(real[:80_000] + bytes(range(256)) * 80)
    cases["header intact, data replaced"] = garbled

    misnamed = tmp_path / "actually_text.jpk"
    misnamed.write_text("nothing to see here")
    cases["wrong extension"] = misnamed

    return cases


@pytest.fixture(scope="module")
def raw_cases(tmp_path_factory, real_bytes):
    return build_raw_cases(tmp_path_factory.mktemp("malformed"), real_bytes)


@pytest.fixture(scope="module")
def raw_case_ids(raw_cases):
    return sorted(raw_cases)


def test_the_case_set_is_not_empty(raw_cases):
    """Guards the fixtures. An empty case set would make every parametrized
    test below vanish silently."""
    assert len(raw_cases) >= 7


@pytest.mark.parametrize("case", [
    "empty file", "arbitrary bytes", "text in a binary format",
    "header cut off early", "header intact, data truncated",
    "header intact, data replaced", "wrong extension",
])
def test_damaged_raw_file_is_rejected(raw_cases, case):
    path = raw_cases[case]
    started = time.perf_counter()
    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(path)
    assert time.perf_counter() - started < RESPONSE_LIMIT_SECONDS, (
        f"reading {case!r} took too long to fail"
    )


@pytest.mark.parametrize("case", [
    "empty file", "arbitrary bytes", "text in a binary format",
    "header cut off early", "header intact, data truncated",
    "header intact, data replaced", "wrong extension",
])
def test_damaged_raw_file_raises_a_typed_error(raw_cases, case):
    """Callers catch GwyddionPyError; nothing may escape that hierarchy."""
    with pytest.raises(gwyddionpy.GwyddionPyError):
        gwyddionpy.load(raw_cases[case])


def build_gwy_cases(tmp_path):
    """Damaged files carrying the native .gwy extension."""
    intact = make_gwy(tmp_path / "intact.gwy",
                      [{"name": "Height", "data": np.arange(64.0).reshape(8, 8)}])
    raw = intact.read_bytes()
    cases = {}

    empty = tmp_path / "empty.gwy"
    empty.write_bytes(b"")
    cases["empty"] = empty

    stub = tmp_path / "stub.gwy"
    stub.write_bytes(raw[:20])
    cases["first bytes only"] = stub

    halved = tmp_path / "halved.gwy"
    halved.write_bytes(raw[: len(raw) // 2])
    cases["truncated"] = halved

    scrambled = tmp_path / "scrambled.gwy"
    scrambled.write_bytes(raw[:200] + b"\xff" * 500 + raw[700:])
    cases["body overwritten"] = scrambled

    impostor = tmp_path / "impostor.gwy"
    impostor.write_text("plain text pretending to be a container")
    cases["not a container at all"] = impostor

    return cases


@pytest.fixture(scope="module")
def gwy_cases(tmp_path_factory):
    return build_gwy_cases(tmp_path_factory.mktemp("damaged-gwy"))


@pytest.mark.parametrize("case", ["empty", "first bytes only", "truncated",
                                  "body overwritten", "not a container at all"])
def test_damaged_gwy_file_is_rejected(gwy_cases, case):
    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(gwy_cases[case])


@pytest.mark.parametrize("case", ["empty", "first bytes only", "truncated",
                                  "body overwritten", "not a container at all"])
def test_damaged_gwy_error_names_the_file_and_the_cause(gwy_cases, case):
    """An empty error message is no help to whoever holds the file."""
    path = gwy_cases[case]
    with pytest.raises(gwyddionpy.UnsupportedFormatError) as raised:
        gwyddionpy.load(path)
    message = str(raised.value)
    assert path.name in message
    assert len(message) > len(str(path))     # more than just the path
    assert raised.value.__cause__ is not None  # the original fault is kept


@pytest.mark.parametrize("case", ["empty", "first bytes only", "truncated",
                                  "body overwritten", "not a container at all"])
def test_damaged_gwy_error_lists_what_could_be_wrong(gwy_cases, case):
    """A low-level fault such as "unpack requires a buffer of 4 bytes" means
    nothing to the caller, so the message lists the kinds of damage that
    produce it."""
    with pytest.raises(gwyddionpy.UnsupportedFormatError) as raised:
        gwyddionpy.load(gwy_cases[case])
    message = str(raised.value).lower()
    assert "possible reasons" in message
    for phrase in ("empty", "truncated", "incomplete", "corrupted",
                   "not a gwyddion container"):
        assert phrase in message, f"{phrase!r} missing from the explanation"


def test_an_empty_gwy_is_identified_as_empty(gwy_cases):
    """The one cause that can be stated outright rather than guessed at."""
    with pytest.raises(gwyddionpy.UnsupportedFormatError) as raised:
        gwyddionpy.load(gwy_cases["empty"])
    assert "the file is empty" in str(raised.value)


@pytest.mark.parametrize("case", [
    "empty file", "arbitrary bytes", "text in a binary format",
    "header cut off early", "header intact, data truncated",
    "header intact, data replaced", "wrong extension",
])
def test_rejected_raw_file_explains_what_could_be_wrong(raw_cases, case):
    with pytest.raises(gwyddionpy.UnsupportedFormatError) as raised:
        gwyddionpy.load(raw_cases[case])
    message = str(raised.value).lower()
    assert "possible reasons" in message
    for phrase in ("not one gwyddion can read", "empty, truncated",
                   "do not match", "corrupted"):
        assert phrase in message, f"{phrase!r} missing from the explanation"


def test_damaged_gwy_survives_assertions_being_disabled(gwy_cases):
    """gwyfile signals an empty container with a bare assert, which
    `python -O` removes. Reading must fail the same way either way, so this
    runs in a child interpreter with optimisation on."""
    import subprocess
    import sys

    path = gwy_cases["empty"]
    result = subprocess.run(
        [sys.executable, "-O", "-c",
         "import sys, gwyddionpy\n"
         "try:\n"
         f"    gwyddionpy.load({str(path)!r})\n"
         "except gwyddionpy.UnsupportedFormatError:\n"
         "    print('typed')\n"
         "except BaseException as e:\n"
         "    print('leaked', type(e).__name__)\n"
         "else:\n"
         "    print('loaded')\n"],
        capture_output=True, text=True, check=False,
    )
    assert result.stdout.strip() == "typed", result.stdout + result.stderr


def test_directory_in_place_of_a_file(tmp_path):
    directory = tmp_path / "scan.spm"
    directory.mkdir()
    with pytest.raises(FileNotFoundError):
        gwyddionpy.load(directory)


def test_nothing_is_left_in_the_temporary_directory(raw_cases):
    """A failed reading must not leak its scratch directory."""
    before = set(Path(tempfile.gettempdir()).glob("gwyddionpy-*"))
    for path in raw_cases.values():
        with pytest.raises(gwyddionpy.GwyddionPyError):
            gwyddionpy.load(path)
    assert set(Path(tempfile.gettempdir()).glob("gwyddionpy-*")) == before


def test_reading_still_works_after_a_run_of_failures(raw_cases):
    """Repeated failures must not leave anything in a state that breaks the
    next legitimate reading."""
    for path in raw_cases.values():
        with pytest.raises(gwyddionpy.GwyddionPyError):
            gwyddionpy.load(path)

    specimen = SPECIMENS_BY_ID["wsxm/sample_0.top"]
    data = gwyddionpy.load(specimen.path)
    assert data.source_format == specimen.module
    assert len(data.channels) == specimen.channels
