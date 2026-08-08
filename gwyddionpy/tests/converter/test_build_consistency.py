"""Two builds of the converter must read a measurement the same way.

The converter can be built more than one way — from a distribution's Gwyddion
package, or from the source tarball the release bundle uses — and those pull
in different Gwyddion versions. A file has to mean the same thing whichever
one read it, or a result depends on how the reader was assembled.

How this is checked depends on what is available:

  with a second build   set GWYDDIONPY_ALT_CONVERT to another gwyconvert and
                        every measurement is read twice and compared directly.
  without one           the committed references stand in. They were captured
                        from one build, so any build that passes them agrees
                        with that build — and therefore with every other build
                        that passes them too.

The second form is not a weaker version of the first; it is the same guarantee
reached transitively, and it is what makes the reference files worth trusting
across the two build paths CI runs.

context part: measured directly on 2026-08-08 between a wheel bundle
reporting 170 formats and a source build reporting 163 — every specimen came
back identical, pixels and metadata alike.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_golden, require_specimen
from helpers.specimens import SPECIMENS

ALT_CONVERTER_ENV = "GWYDDIONPY_ALT_CONVERT"
ALT_CONVERTER = os.environ.get(ALT_CONVERTER_ENV, "")
TESTS_DIR = Path(__file__).resolve().parents[1]

READER = """
import sys, json
sys.path.insert(0, {tests!r})
import gwyddionpy
from helpers import content as content_mod
from helpers.specimens import SPECIMENS_BY_ID
specimen = SPECIMENS_BY_ID[sys.argv[1]]
print(json.dumps(content_mod.extract_content(
    gwyddionpy.load(specimen.path, converter=sys.argv[2])), sort_keys=True))
"""


def read_with(converter, specimen):
    """Read one measurement with a named converter, in its own process.

    A separate process because the converter is chosen per call and the
    comparison should share nothing else between the two readings.
    """
    import json

    result = subprocess.run(
        [sys.executable, "-c", READER.format(tests=str(TESTS_DIR)),
         specimen.relpath, converter],
        capture_output=True, text=True, check=False, env=os.environ,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def differences(first, second):
    """Every way two readings of one measurement disagree."""
    found = []
    if first["source_format"] != second["source_format"]:
        found.append(f"format: {first['source_format']} vs {second['source_format']}")
    if first["channel_names"] != second["channel_names"]:
        found.append(f"channels: {first['channel_names']} vs {second['channel_names']}")
    for name in first["channels"].keys() & second["channels"].keys():
        one, other = first["channels"][name], second["channels"][name]
        if one["shape"] != other["shape"]:
            found.append(f"{name}: shape {one['shape']} vs {other['shape']}")
        found += content_mod.float_diffs(
            {"xreal": one["xreal"], "yreal": one["yreal"]},
            {"xreal": other["xreal"], "yreal": other["yreal"]}, where=f"{name}.")
        found += content_mod.float_diffs(one["pixels"], other["pixels"],
                                         where=f"{name} @ ")
        found += [f"{name}.{d}" for d in content_mod.meta_diffs(one["meta"],
                                                                other["meta"])]
    return found


# --------------------------------------------------------------------------
# The comparison itself must be able to fail
# --------------------------------------------------------------------------
def test_the_comparison_notices_a_difference():
    """context part: without this, a comparison that always returned "no
    differences" would make everything below pass and mean nothing."""
    specimen = SPECIMENS[0]
    require_golden(specimen)
    reference = content_mod.load_golden(specimen)

    altered = content_mod.load_golden(specimen)
    altered["source_format"] = "something-else"
    assert differences(reference, altered)

    if reference["channels"]:
        name = reference["channel_names"][0]
        moved = content_mod.load_golden(specimen)
        moved["channels"][name]["xreal"] *= 1.001
        assert differences(reference, moved)


def test_a_reading_matches_itself():
    specimen = SPECIMENS[0]
    require_golden(specimen)
    reference = content_mod.load_golden(specimen)
    assert differences(reference, content_mod.load_golden(specimen)) == []


# --------------------------------------------------------------------------
# This build against the committed references
# --------------------------------------------------------------------------
@pytest.mark.parametrize("specimen", SPECIMENS, ids=lambda s: s.id)
def test_this_build_agrees_with_the_recorded_reading(specimen):
    """The transitive form: agreeing with the references is what makes two
    builds agree with each other."""
    require_golden(specimen)
    fresh = content_mod.extract_content(gwyddionpy.load(specimen.path))
    found = differences(content_mod.load_golden(specimen), fresh)
    assert not found, (
        "this build reads the measurement differently from the recorded "
        "reading:\n" + content_mod.format_diffs(found)
    )


def test_the_format_list_is_large_enough_to_be_a_real_build():
    """Builds differ in how many formats they carry — 163 and 170 have both
    been seen — so this is a floor rather than a number to match."""
    assert len(gwyddionpy.list_formats()) >= 150


# --------------------------------------------------------------------------
# This build against another one, when there is another one
# --------------------------------------------------------------------------
@pytest.mark.skipif(not ALT_CONVERTER,
                    reason=f"no second build given in {ALT_CONVERTER_ENV}")
@pytest.mark.parametrize("specimen", SPECIMENS, ids=lambda s: s.id)
def test_two_builds_read_a_measurement_the_same_way(specimen):
    require_specimen(specimen)
    from gwyddionpy._run import find_converter

    found = differences(read_with(find_converter(), specimen),
                        read_with(ALT_CONVERTER, specimen))
    assert not found, (
        f"the two builds disagree about {specimen.relpath}:\n"
        + content_mod.format_diffs(found)
    )


@pytest.mark.skipif(not ALT_CONVERTER,
                    reason=f"no second build given in {ALT_CONVERTER_ENV}")
def test_the_second_build_is_actually_a_different_one():
    """Guards the comparison above: pointing the variable at the same binary
    would make it compare a build with itself."""
    from gwyddionpy._run import find_converter

    assert os.path.realpath(ALT_CONVERTER) != os.path.realpath(find_converter()), (
        f"{ALT_CONVERTER_ENV} points at the build already in use"
    )
