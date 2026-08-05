"""Giving up on a converter that does not come back.

Without a limit, a converter that hangs blocks its caller for as long as the
process lives, with no error and no way out. Every call therefore carries a
deadline, and the tests below drive the real converter against a deadline it
cannot meet rather than standing in a stub that sleeps: what needs proving is
that a real running process is stopped and reported, not that a mock was
called.

warning: the deadline is a safety net for a hung process, not a performance
budget. DEFAULT_TIMEOUT is deliberately far above any legitimate reading time,
so a file that trips it should be treated as a fault to investigate rather
than a reason to raise the number.
"""
import tempfile
import time
from pathlib import Path

import pytest

import gwyddionpy
from gwyddionpy._run import DEFAULT_TIMEOUT, query_formats, run_converter
from helpers.requirements import require_specimen
from helpers.specimens import SPECIMENS_BY_ID

#: Short enough that no process can finish inside it, so the deadline is
#: certain to be the thing that ends the call.
UNMEETABLE = 0.001

#: How long the call itself may take once its deadline has passed. Generous
#: against a loaded machine while still failing if nothing was actually
#: stopped.
OVERSHOOT_ALLOWANCE = 30.0

BRUKER = "bruker_nanoscope/VGEP-15m-.0_00000.spm"


@pytest.fixture
def specimen():
    specimen = SPECIMENS_BY_ID[BRUKER]
    require_specimen(specimen)
    return specimen


def test_a_reading_that_overruns_is_reported(specimen):
    with pytest.raises(gwyddionpy.ConversionError) as raised:
        gwyddionpy.load(specimen.path, timeout=UNMEETABLE)
    message = str(raised.value)
    assert "did not finish" in message
    assert str(specimen.path) in message


def test_the_call_returns_promptly_once_the_deadline_passes(specimen):
    """The point of the deadline: the caller gets control back."""
    started = time.perf_counter()
    with pytest.raises(gwyddionpy.ConversionError):
        gwyddionpy.load(specimen.path, timeout=UNMEETABLE)
    assert time.perf_counter() - started < OVERSHOOT_ALLOWANCE


def test_the_overrun_is_catchable_as_a_gwyddionpy_error(specimen):
    with pytest.raises(gwyddionpy.GwyddionPyError):
        gwyddionpy.load(specimen.path, timeout=UNMEETABLE)


def test_the_underlying_fault_is_preserved(specimen):
    """Keeping the TimeoutExpired as the cause means the traceback still says
    what actually happened."""
    import subprocess

    with pytest.raises(gwyddionpy.ConversionError) as raised:
        gwyddionpy.load(specimen.path, timeout=UNMEETABLE)
    assert isinstance(raised.value.__cause__, subprocess.TimeoutExpired)


def test_an_overrun_leaves_no_temporary_directory(specimen):
    before = set(Path(tempfile.gettempdir()).glob("gwyddionpy-*"))
    with pytest.raises(gwyddionpy.ConversionError):
        gwyddionpy.load(specimen.path, timeout=UNMEETABLE)
    assert set(Path(tempfile.gettempdir()).glob("gwyddionpy-*")) == before


def test_reading_works_again_after_an_overrun(specimen):
    """Whatever was stopped must not affect the next call."""
    with pytest.raises(gwyddionpy.ConversionError):
        gwyddionpy.load(specimen.path, timeout=UNMEETABLE)

    data = gwyddionpy.load(specimen.path)
    assert data.source_format == specimen.module
    assert len(data.channels) == specimen.channels


def test_a_generous_deadline_does_not_disturb_a_normal_reading(specimen):
    data = gwyddionpy.load(specimen.path, timeout=DEFAULT_TIMEOUT)
    assert len(data.channels) == specimen.channels


def test_the_deadline_reaches_the_converter_directly(specimen, tmp_path):
    """run_converter is the layer that owns the deadline; check it there too,
    not only through load()."""
    with pytest.raises(gwyddionpy.ConversionError):
        run_converter(specimen.path, tmp_path / "out.gwy", timeout=UNMEETABLE)


def test_listing_formats_carries_a_deadline_too():
    with pytest.raises(gwyddionpy.ConversionError) as raised:
        query_formats(timeout=UNMEETABLE)
    assert "did not list its formats" in str(raised.value)


def test_listing_formats_still_works_with_a_generous_deadline():
    assert len(gwyddionpy.list_formats(timeout=DEFAULT_TIMEOUT)) >= 170


def test_reading_a_native_gwy_ignores_the_deadline(tmp_path):
    """context part: a .gwy is read in-process, with no converter to stop, so
    an unmeetable deadline must not affect it."""
    import numpy as np

    from helpers.gwy_builder import make_gwy

    path = make_gwy(tmp_path / "native.gwy",
                    [{"name": "Height", "data": np.zeros((4, 4))}])
    data = gwyddionpy.load(path, timeout=UNMEETABLE)
    assert "Height" in data.channels
