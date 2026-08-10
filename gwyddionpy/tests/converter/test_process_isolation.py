"""Several processes reading files at the same time, as a shared analysis
machine or a parallel test runner does.

Each converts through its own scratch directory, so the question is whether
those collide, or two conversions of one measurement disagree.
"""

import json
import os
import subprocess
import sys
import tempfile
from concurrent import futures
from pathlib import Path

import pytest

from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS, SPECIMENS_BY_ID

TESTS_DIR = Path(__file__).resolve().parents[1]
WORKERS = 8

READER = """
import sys, json, hashlib
sys.path.insert(0, {tests!r})
import gwyddionpy
from helpers import content as content_mod
from helpers.specimens import SPECIMENS_BY_ID

specimen = SPECIMENS_BY_ID[sys.argv[1]]
data = gwyddionpy.load(specimen.path)
content = content_mod.extract_content(data)
print(json.dumps({{
    "digest": hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()).hexdigest(),
    "channels": len(data.channels),
    "format": data.source_format,
}}))
"""


def read_in_a_separate_process(relpath):
    result = subprocess.run(
        [sys.executable, "-c", READER.format(tests=str(TESTS_DIR)), relpath],
        capture_output=True, text=True, check=False, env=os.environ,
    )
    return result, relpath


def scratch_directories():
    return set(Path(tempfile.gettempdir()).glob("gwyddionpy-*"))


@pytest.fixture(scope="module")
def specimens():
    chosen = IMAGE_SPECIMENS[:3]
    for specimen in chosen:
        require_specimen(specimen)
    return chosen


def test_concurrent_readings_of_one_file_all_agree(specimens):
    """One measurement read by several processes at once must come back the
    same every time."""
    relpath = specimens[0].relpath
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(read_in_a_separate_process,
                                 [relpath] * WORKERS))

    digests = set()
    for result, _ in outcomes:
        assert result.returncode == 0, result.stderr
        digests.add(json.loads(result.stdout)["digest"])
    assert len(digests) == 1, f"{len(digests)} different results from one file"


def test_concurrent_readings_of_different_files_do_not_cross(specimens):
    """Running together must not let one measurement's data reach another's
    result, which is what a shared scratch path would cause."""
    order = [s.relpath for s in specimens] * 3
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(read_in_a_separate_process, order))

    by_file = {}
    for result, relpath in outcomes:
        assert result.returncode == 0, result.stderr
        by_file.setdefault(relpath, set()).add(json.loads(result.stdout)["digest"])

    for relpath, digests in by_file.items():
        assert len(digests) == 1, f"{relpath} gave inconsistent results"
    # Different measurements must not collapse onto one another.
    everything = {next(iter(d)) for d in by_file.values()}
    assert len(everything) == len(by_file)


def test_concurrent_readings_report_the_right_format_and_channels(specimens):
    order = [s.relpath for s in specimens] * 2
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(read_in_a_separate_process, order))

    for result, relpath in outcomes:
        assert result.returncode == 0, result.stderr
        reported = json.loads(result.stdout)
        specimen = SPECIMENS_BY_ID[relpath]
        assert reported["format"] == specimen.module
        assert reported["channels"] == specimen.channels


def test_concurrent_readings_match_a_reading_done_alone(specimens):
    """Concurrency must not change the answer, only when it arrives."""
    import gwyddionpy
    from helpers import content as content_mod
    import hashlib

    specimen = specimens[0]
    alone = hashlib.sha256(json.dumps(
        content_mod.extract_content(gwyddionpy.load(specimen.path)),
        sort_keys=True).encode()).hexdigest()

    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(read_in_a_separate_process,
                                 [specimen.relpath] * WORKERS))

    for result, _ in outcomes:
        assert json.loads(result.stdout)["digest"] == alone


def test_concurrent_readings_leave_no_scratch_directories(specimens):
    before = scratch_directories()
    order = [s.relpath for s in specimens] * 2
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(read_in_a_separate_process, order))
    for result, _ in outcomes:
        assert result.returncode == 0, result.stderr
    assert scratch_directories() == before


def test_each_process_gets_its_own_scratch_directory(specimens):
    """Each call gets a uniquely named scratch directory, which is what
    keeps simultaneous conversions apart. Checked by having several
    processes report the path they used."""
    script = (
        "import sys, tempfile, pathlib\n"
        f"sys.path.insert(0, {str(TESTS_DIR)!r})\n"
        "import gwyddionpy\n"
        "from helpers.specimens import SPECIMENS_BY_ID\n"
        "seen = []\n"
        "real = gwyddionpy.parse_gwy\n"
        "def note(path):\n"
        "    seen.append(str(pathlib.Path(path).parent))\n"
        "    return real(path)\n"
        "gwyddionpy.parse_gwy = note\n"
        "gwyddionpy.load(SPECIMENS_BY_ID[sys.argv[1]].path)\n"
        "print(seen[0])\n"
    )
    relpath = specimens[0].relpath

    def run(_):
        return subprocess.run([sys.executable, "-c", script, relpath],
                              capture_output=True, text=True, check=False,
                              env=os.environ)

    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(run, range(WORKERS)))

    paths = []
    for result in results:
        assert result.returncode == 0, result.stderr
        paths.append(result.stdout.strip())
    assert len(set(paths)) == len(paths), f"scratch paths were shared: {paths}"


def test_a_failing_process_does_not_disturb_the_others(specimens):
    """One job reading a file it cannot handle must not affect the rest."""
    good = specimens[0].relpath
    order = [good, "nonexistent/file", good, "nonexistent/file", good]

    def run(relpath):
        if relpath == "nonexistent/file":
            script = (f"import sys; sys.path.insert(0, {str(TESTS_DIR)!r})\n"
                      "import gwyddionpy\n"
                      "gwyddionpy.load('gwyddionpy/tests/data/README.md')\n")
            return None, subprocess.run([sys.executable, "-c", script],
                                        capture_output=True, text=True,
                                        check=False, env=os.environ)
        return read_in_a_separate_process(relpath)

    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(run, order))

    digests = set()
    for first, second in outcomes:
        if first is None:            # the failing job
            assert second.returncode != 0
        else:
            assert first.returncode == 0, first.stderr
            digests.add(json.loads(first.stdout)["digest"])
    assert len(digests) == 1
