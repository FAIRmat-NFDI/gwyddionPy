"""What reading files repeatedly leaves behind: open descriptors, scratch
directories, retained measurements.

Nothing here fails on a single reading; each check repeats an operation and
looks at what accumulated. Failures are exercised as heavily as successes,
since their cleanup path is the least-tried one.
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
    """A portable stand-in for "how many descriptors are open": opening a
    file returns the lowest number not in use, so this climbs on a leak."""
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
    """A leak check that cannot fail is worse than none."""
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
    with pytest.raises(gwyddionpy.GwyddionPyError):
        gwyddionpy.load(UNREADABLE)         # warm up
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
    """Shows the directories counted above are really created and removed,
    rather than never having existed."""
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
    """Nothing may hold a measurement after the caller drops it."""
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
    """A traceback keeps frames alive; one holding a measurement would
    accumulate them in any caller that logs failures."""
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
    """A stopped converter left running would show up in the next read."""
    for _ in range(3):
        with pytest.raises(gwyddionpy.ConversionError):
            gwyddionpy.load(specimen.path, timeout=0.001)

    data = gwyddionpy.load(specimen.path)
    assert len(data.channels) == specimen.channels


def test_the_wrapper_replaces_itself_rather_than_forking():
    """The wrapper must end in `exec`, so the process Python starts becomes
    the converter. One that called the binary instead would strand a process
    on every overrun."""
    from gwyddionpy._run import find_converter

    converter = Path(find_converter())
    if converter.read_bytes()[:2] != b"#!":
        assert converter.is_file()   # no wrapper, so nothing can be stranded
        return

    script = converter.read_text(encoding="utf-8", errors="replace")
    launches = [line.strip() for line in script.splitlines()
                if "gwyconvert.real" in line and not line.strip().startswith("#")]
    assert launches, "the wrapper never launches the real converter"
    assert all(line.startswith("exec ") for line in launches), (
        "the wrapper launches the converter without exec, so a stopped "
        f"conversion would leave a process behind: {launches}"
    )
