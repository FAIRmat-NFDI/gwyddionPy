"""How much memory a conversion costs, and whether that scales sensibly.

Cost splits into a fixed part (starting GTK, ~23 MB) and a per-data part
(~2x the pixel bytes); only the second is a leak signal. Limits sit well
above what was measured, so these catch a change in kind, not a budget.
"""
import subprocess
import sys
from pathlib import Path

import pytest

import gwyddionpy
from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS, SPECIMENS_BY_ID

TESTS_DIR = Path(__file__).resolve().parents[1]

#: Measured ~23 MB. The margin covers other builds and platforms while
#: still catching a start-up cost that changes by an order of magnitude.
FIXED_COST_LIMIT_MB = 150.0

#: Measured ~1.5-2.2x the pixel bytes. Four allows roughly a doubling.
PER_DATA_LIMIT = 4.0

NO_PIXELS = "nanonis/Bias-Spectroscopy002.dat"

MEASURE = """
import resource, subprocess, sys, tempfile, pathlib
sys.path.insert(0, {tests!r})
from gwyddionpy._run import find_converter, converter_environment

with tempfile.TemporaryDirectory() as tmp:
    output = pathlib.Path(tmp, "converted.gwy")
    subprocess.run([find_converter(), sys.argv[1], str(output)],
                   capture_output=True, env=converter_environment(), check=True)
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
# ru_maxrss is kilobytes on Linux and bytes on macOS.
print(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024)
"""

try:
    import resource as _resource  # noqa: F401
    CAN_MEASURE = True
except ImportError:                # pragma: no cover - Windows
    CAN_MEASURE = False


def peak_megabytes(specimen) -> float:
    """Peak memory of one conversion, in a process of its own. The reported
    figure is a high-water mark that never comes down, so several
    conversions in one process would only report the largest."""
    result = subprocess.run(
        [sys.executable, "-c", MEASURE.format(tests=str(TESTS_DIR)),
         str(specimen.path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return float(result.stdout.strip())


def pixel_megabytes(specimen) -> float:
    data = gwyddionpy.load(specimen.path)
    return sum(channel.data.nbytes for channel in data.channels.values()) / 1e6


def largest_and_smallest():
    by_size = sorted(IMAGE_SPECIMENS, key=pixel_megabytes)
    return by_size[0], by_size[-1]


pytestmark = pytest.mark.skipif(
    not CAN_MEASURE,
    reason="peak memory needs getrusage, which Windows does not provide",
)


def test_the_fixed_cost_is_paid_once_and_is_modest():
    """A file with no image data isolates start-up: whatever this costs is
    GTK and the module registry."""
    specimen = SPECIMENS_BY_ID[NO_PIXELS]
    require_specimen(specimen)
    assert pixel_megabytes(specimen) == 0, "this file is supposed to hold no images"

    peak = peak_megabytes(specimen)
    assert peak < FIXED_COST_LIMIT_MB, (
        f"starting the converter now costs {peak:.0f} MB before reading any "
        f"pixels, against a measured baseline of about 23 MB"
    )


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=lambda s: s.id)
def test_a_conversion_stays_within_a_bounded_multiple_of_its_data(specimen):
    require_specimen(specimen)
    pixels = pixel_megabytes(specimen)
    peak = peak_megabytes(specimen)
    allowed = FIXED_COST_LIMIT_MB + PER_DATA_LIMIT * pixels

    assert peak < allowed, (
        f"reading {pixels:.1f} MB of pixels cost {peak:.0f} MB, more than the "
        f"{allowed:.0f} MB allowed ({FIXED_COST_LIMIT_MB:.0f} fixed + "
        f"{PER_DATA_LIMIT}x the data)"
    )


def test_memory_grows_only_in_proportion_to_the_data():
    """The leak-shaped question, asked without the fixed cost in the way:
    comparing largest against smallest cancels start-up out, leaving
    megabytes spent per megabyte of pixels."""
    smallest, largest = largest_and_smallest()
    for specimen in (smallest, largest):
        require_specimen(specimen)

    small_pixels, large_pixels = pixel_megabytes(smallest), pixel_megabytes(largest)
    assert large_pixels > small_pixels * 2, (
        "need measurements of clearly different sizes for this comparison"
    )

    marginal = ((peak_megabytes(largest) - peak_megabytes(smallest))
                / (large_pixels - small_pixels))
    assert marginal < PER_DATA_LIMIT, (
        f"each extra megabyte of pixels now costs {marginal:.1f} MB of memory, "
        f"against about 2 when measured; that is the shape of a leak that "
        f"grows with the file"
    )


def test_reading_the_same_file_twice_costs_the_same():
    """Each conversion starts from nothing, so a difference would mean
    something outlives the process."""
    specimen = SPECIMENS_BY_ID["wsxm/sample_0.top"]
    require_specimen(specimen)

    first, second = peak_megabytes(specimen), peak_megabytes(specimen)
    assert abs(first - second) < 0.25 * max(first, second), (
        f"two conversions of one file cost {first:.0f} MB and {second:.0f} MB"
    )
