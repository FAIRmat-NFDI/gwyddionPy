"""Two builds of the converter must read a measurement the same way.

Set GWYDDIONPY_ALT_CONVERT to a second gwyconvert and every measurement is
read twice and compared. Without one the committed references stand in:
any build passing them agrees with the build they came from, and so with
every other build that passes them.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_reference, require_specimen
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

    Separate processes so the two readings share nothing else.
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
    """Without this, a comparison that always returned "no differences"
    would make everything below pass and mean nothing."""
    specimen = SPECIMENS[0]
    require_reference(specimen)
    reference = content_mod.load_reference(specimen)

    altered = content_mod.load_reference(specimen)
    altered["source_format"] = "something-else"
    assert differences(reference, altered)

    if reference["channels"]:
        name = reference["channel_names"][0]
        moved = content_mod.load_reference(specimen)
        moved["channels"][name]["xreal"] *= 1.001
        assert differences(reference, moved)


def test_a_reading_matches_itself():
    specimen = SPECIMENS[0]
    require_reference(specimen)
    reference = content_mod.load_reference(specimen)
    assert differences(reference, content_mod.load_reference(specimen)) == []


# --------------------------------------------------------------------------
# This build against the committed references
# --------------------------------------------------------------------------
@pytest.mark.parametrize("specimen", SPECIMENS, ids=lambda s: s.id)
def test_this_build_agrees_with_the_recorded_reading(specimen):
    """The transitive form. Agreeing with the references is what makes two
    builds agree with each other."""
    require_reference(specimen)
    fresh = content_mod.extract_content(gwyddionpy.load(specimen.path))
    found = differences(content_mod.load_reference(specimen), fresh)
    assert not found, (
        "this build reads the measurement differently from the recorded "
        "reading:\n" + content_mod.format_diffs(found)
    )


def test_the_format_list_is_large_enough_to_be_a_real_build():
    """Builds differ in how many formats they carry, so this is a floor
    rather than a number to match."""
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
    """Guards the comparison above. Pointing the variable at the same binary
    would compare a build with itself."""
    from gwyddionpy._run import find_converter

    assert os.path.realpath(ALT_CONVERTER) != os.path.realpath(find_converter()), (
        f"{ALT_CONVERTER_ENV} points at the build already in use"
    )
