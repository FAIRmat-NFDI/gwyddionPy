"""What reading files repeatedly leaves behind.

A leak of any kind — an open descriptor, a scratch directory, a parsed
measurement still referenced — costs nothing on the first call and matters a
great deal to anything that reads thousands of files in one run, which is
what a batch ingest does. Nothing here would fail on a single reading; every
check repeats an operation and looks at what accumulated.

Failures are exercised as heavily as successes, because the cleanup path that
runs when something goes wrong is the one least likely to have been tried.
"""
import gc
import os
import tempfile
from pathlib import Path

import pytest

import gwyddionpy
from gwyddionpy._model import Channel
from helpers.requirements import require_specimen
from helpers.specimens import SPECIMENS_BY_ID

REPEATS = 25
WSXM = "wsxm/sample_0.top"
UNREADABLE = Path("gwyddionpy/tests/data/README.md")


@pytest.fixture(scope="module")
def specimen():
    specimen = SPECIMENS_BY_ID[WSXM]
    require_specimen(specimen)
    return specimen


def lowest_free_descriptor() -> int:
    """A portable stand-in for "how many descriptors are open".

    Opening a file hands back the lowest number not currently in use, so if
    anything is leaking descriptors this number climbs. Cheaper and more
    portable than reading /proc, and the control test below proves it works.
    """
    handle = os.open(os.devnull, os.O_RDONLY)
    os.close(handle)
    return handle


def scratch_directories() -> set:
    return set(Path(tempfile.gettempdir()).glob("gwyddionpy-*"))


def live_channels() -> int:
    gc.collect()
    return sum(1 for obj in gc.get_objects() if isinstance(obj, Channel))


def read_and_discard(path, times=REPEATS):
    for _ in range(times):
        gwyddionpy.load(path)


def fail_repeatedly(path, times=REPEATS):
    for _ in range(times):
        with pytest.raises(gwyddionpy.GwyddionPyError):
            gwyddionpy.load(path)


# --------------------------------------------------------------------------
# The measurement technique itself
# --------------------------------------------------------------------------
def test_the_descriptor_probe_detects_a_real_leak():
    """context part: a leak check that cannot fail is worse than none, so the
    probe is shown to notice descriptors that are deliberately held open."""
    baseline = lowest_free_descriptor()
    held = [open(os.devnull) for _ in range(5)]
    try:
        assert lowest_free_descriptor() > baseline
    finally:
        for handle in held:
            handle.close()
    assert lowest_free_descriptor() == baseline


def test_the_channel_count_probe_detects_a_retained_reading(specimen):
    """The same for the other probe: holding a measurement must show up."""
    baseline = live_channels()
    retained = gwyddionpy.load(specimen.path)
    assert live_channels() > baseline
    del retained
    assert live_channels() == baseline


# --------------------------------------------------------------------------
# Descriptors
# --------------------------------------------------------------------------
def test_reading_many_times_leaks_no_descriptors(specimen):
    gwyddionpy.load(specimen.path)          # warm up anything cached on first use
    baseline = lowest_free_descriptor()
    read_and_discard(specimen.path)
    assert lowest_free_descriptor() == baseline


def test_failing_many_times_leaks_no_descriptors():
    gwyddionpy.load  # noqa: B018 — module already imported; nothing to warm here
    with pytest.raises(gwyddionpy.GwyddionPyError):
        gwyddionpy.load(UNREADABLE)
    baseline = lowest_free_descriptor()
    fail_repeatedly(UNREADABLE)
    assert lowest_free_descriptor() == baseline


def test_listing_formats_many_times_leaks_no_descriptors():
    gwyddionpy.list_formats()
    baseline = lowest_free_descriptor()
    for _ in range(REPEATS):
        gwyddionpy.list_formats()
    assert lowest_free_descriptor() == baseline


def test_reading_a_native_gwy_many_times_leaks_no_descriptors(tmp_path):
    """The in-process path opens the file itself rather than handing it to a
    subprocess, so it leaks differently if it leaks at all."""
    import numpy as np

    from helpers.gwy_builder import make_gwy

    path = make_gwy(tmp_path / "native.gwy",
                    [{"name": "Height", "data": np.zeros((8, 8))}])
    gwyddionpy.load(path)
    baseline = lowest_free_descriptor()
    read_and_discard(path)
    assert lowest_free_descriptor() == baseline


# --------------------------------------------------------------------------
# Scratch directories
# --------------------------------------------------------------------------
def test_successful_readings_leave_no_scratch_directories(specimen):
    before = scratch_directories()
    read_and_discard(specimen.path)
    assert scratch_directories() == before


def test_failed_readings_leave_no_scratch_directories():
    before = scratch_directories()
    fail_repeatedly(UNREADABLE)
    assert scratch_directories() == before


def test_an_overrun_leaves_no_scratch_directories(specimen):
    """The cleanup path that runs when the converter is stopped part-way."""
    before = scratch_directories()
    for _ in range(5):
        with pytest.raises(gwyddionpy.ConversionError):
            gwyddionpy.load(specimen.path, timeout=0.001)
    assert scratch_directories() == before


def test_a_scratch_directory_exists_only_while_reading(specimen, monkeypatch):
    """context part: shows the directories being counted are really created
    and really removed, rather than never having existed."""
    seen = {}
    real_parse = gwyddionpy.parse_gwy

    def note_and_parse(path):
        seen["during"] = scratch_directories()
        return real_parse(path)

    before = scratch_directories()
    monkeypatch.setattr(gwyddionpy, "parse_gwy", note_and_parse)
    gwyddionpy.load(specimen.path)

    assert len(seen["during"]) == len(before) + 1, "no scratch directory was made"
    assert scratch_directories() == before, "the scratch directory outlived the read"


# --------------------------------------------------------------------------
# Retained data
# --------------------------------------------------------------------------
def test_discarded_readings_are_released(specimen):
    """Nothing may hold on to a measurement after the caller drops it — the
    whole point of reading one file at a time."""
    gwyddionpy.load(specimen.path)
    baseline = live_channels()
    read_and_discard(specimen.path)
    assert live_channels() == baseline


def test_discarded_failures_retain_nothing():
    fail_repeatedly(UNREADABLE, times=3)
    baseline = live_channels()
    fail_repeatedly(UNREADABLE)
    assert live_channels() == baseline


def test_an_exception_does_not_pin_the_data_it_came_from(specimen):
    """A traceback keeps frames alive; if one holds a whole measurement, a
    caller logging failures slowly accumulates them."""
    baseline = live_channels()
    for _ in range(5):
        try:
            gwyddionpy.load(specimen.path, timeout=0.001)
        except gwyddionpy.ConversionError:
            pass
    assert live_channels() == baseline


# --------------------------------------------------------------------------
# The converter process
# --------------------------------------------------------------------------
def test_reading_works_immediately_after_a_run_of_overruns(specimen):
    """If a stopped converter were left running or holding the input, the
    next read would be the thing to notice."""
    for _ in range(3):
        with pytest.raises(gwyddionpy.ConversionError):
            gwyddionpy.load(specimen.path, timeout=0.001)

    data = gwyddionpy.load(specimen.path)
    assert len(data.channels) == specimen.channels


def test_the_wrapper_replaces_itself_rather_than_forking():
    """context part: on Linux the installed converter is a shell script that
    sets up the bundle's library paths. It ends in `exec`, so the process
    Python starts *becomes* the real converter instead of fathering it —
    which is why stopping that process stops the conversion. A wrapper that
    called the binary instead would strand a grandchild on every overrun,
    and nothing else in the suite would notice.
    """
    from gwyddionpy._run import find_converter

    converter = Path(find_converter())
    head = converter.read_bytes()[:2]
    if head != b"#!":
        # A plain executable: there is no wrapper, so nothing can be stranded.
        assert converter.is_file()
        return

    script = converter.read_text(encoding="utf-8", errors="replace")
    launches = [line.strip() for line in script.splitlines()
                if "gwyconvert.real" in line and not line.strip().startswith("#")]
    assert launches, "the wrapper never launches the real converter"
    assert all(line.startswith("exec ") for line in launches), (
        "the wrapper launches the converter without exec, so a stopped "
        f"conversion would leave a process behind: {launches}"
    )
