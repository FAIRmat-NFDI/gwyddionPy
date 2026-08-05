"""Reading the same file twice must give the same answer.

Cheap to check and worth checking: uninitialised memory in a C reader, a
hash-ordered container, or anything else that varies between runs shows up
here as a difference between two readings of one file, and nowhere else in
the suite.

warning: the intermediate .gwy is deliberately *not* compared byte for byte.
Gwyddion stamps the conversion time into the container, so two readings of
the same measurement differ in those bytes and in nothing else — byte
equality would fail for a reason that has nothing to do with the data.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS, SPECIMENS, SPECIMENS_BY_ID

TESTS_DIR = Path(__file__).resolve().parents[1]
WSXM = "wsxm/sample_0.top"


def read_content(specimen):
    return content_mod.extract_content(gwyddionpy.load(specimen.path))


def assert_same_content(first, second, label):
    assert first["source_format"] == second["source_format"], label
    assert first["channel_names"] == second["channel_names"], label
    for name, expected in first["channels"].items():
        actual = second["channels"][name]
        assert expected["shape"] == actual["shape"], f"{label}: {name} shape"
        assert expected["dtype"] == actual["dtype"], f"{label}: {name} dtype"
        assert content_mod.float_diffs(
            {"xreal": expected["xreal"], "yreal": expected["yreal"]},
            {"xreal": actual["xreal"], "yreal": actual["yreal"]},
            where=f"{name}.",
        ) == [], label
        assert content_mod.float_diffs(
            expected["pixels"], actual["pixels"], where=f"{name} @ "
        ) == [], label
        assert content_mod.meta_diffs(expected["meta"], actual["meta"]) == [], label


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=lambda s: s.id)
def test_two_readings_in_one_process_agree(specimen):
    require_specimen(specimen)
    assert_same_content(read_content(specimen), read_content(specimen),
                        f"{specimen.relpath} read twice")


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=lambda s: s.id)
def test_repeated_readings_stay_stable(specimen):
    """Three readings rather than two: a value that alternates would slip
    past a single comparison."""
    require_specimen(specimen)
    readings = [read_content(specimen) for _ in range(3)]
    for index, later in enumerate(readings[1:], start=2):
        assert_same_content(readings[0], later,
                            f"{specimen.relpath} reading 1 vs {index}")


def test_a_fresh_process_reads_the_same_values():
    """Anything carried over inside one interpreter — a cache, a module-level
    variable — would hide here, so the comparison crosses a process boundary."""
    specimen = SPECIMENS_BY_ID[WSXM]
    require_specimen(specimen)

    script = (
        "import sys, json; sys.path.insert(0, %r)\n"
        "import gwyddionpy\n"
        "from helpers import content as c\n"
        "from helpers.specimens import SPECIMENS_BY_ID\n"
        "s = SPECIMENS_BY_ID[%r]\n"
        "print(json.dumps(c.extract_content(gwyddionpy.load(s.path)), sort_keys=True))\n"
        % (str(TESTS_DIR), WSXM)
    )
    runs = []
    for _ in range(2):
        result = subprocess.run([sys.executable, "-c", script],
                                capture_output=True, text=True, check=False,
                                env=os.environ)
        assert result.returncode == 0, result.stderr
        runs.append(json.loads(result.stdout))

    assert_same_content(runs[0], runs[1], "two separate processes")
    assert_same_content(runs[0], read_content(specimen),
                        "separate process vs this one")


def test_channel_order_is_stable():
    """Order comes from the file and is what callers index by, so it must not
    depend on anything that varies between runs."""
    specimen = SPECIMENS_BY_ID["jpk/sample_0.jpk"]
    require_specimen(specimen)
    orders = [list(gwyddionpy.load(specimen.path).channels) for _ in range(3)]
    assert orders[0] == orders[1] == orders[2]
    assert len(orders[0]) == specimen.channels


def test_pixel_data_is_identical_to_the_last_bit():
    """The comparisons elsewhere allow a relative tolerance for differences
    between builds. Two readings on one machine have no such excuse: every
    value must match exactly, which is what would expose uninitialised
    memory behind the data."""
    import numpy as np

    specimen = SPECIMENS_BY_ID[WSXM]
    require_specimen(specimen)
    first = gwyddionpy.load(specimen.path)
    second = gwyddionpy.load(specimen.path)

    for name, channel in first.channels.items():
        np.testing.assert_array_equal(
            channel.data, second.channels[name].data,
            err_msg=f"{name} differs between two readings of the same file",
        )


def test_the_converted_file_differs_only_in_its_timestamp():
    """context part: pins the reason byte equality is not asserted. If a
    future build made the output reproducible, or made it vary in some new
    way, this is what would notice."""
    from gwyddionpy._run import run_converter

    specimen = SPECIMENS_BY_ID[WSXM]
    require_specimen(specimen)

    blobs = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir, "converted.gwy")
            run_converter(specimen.path, output)
            blobs.append(output.read_bytes())

    first, second = blobs
    assert len(first) == len(second), "converted files differ in length"
    differing = [i for i in range(len(first)) if first[i] != second[i]]
    if not differing:
        return  # reproducible byte for byte, which is even better

    # The differing run must be one short stretch: a timestamp, not data.
    assert len(differing) < 64, (
        f"{len(differing)} bytes differ between two conversions; that is more "
        "than a timestamp"
    )
    span = first[max(0, differing[0] - 48):differing[-1] + 8]
    assert b"20" in span, (
        "the differing bytes do not look like a timestamp: " + repr(span[:120])
    )
