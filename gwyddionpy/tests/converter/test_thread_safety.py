"""Reading files from several threads of one process.

Separate processes are covered elsewhere; this is the harder case, because
threads share everything the module has — the environment the converter is
launched with, the working directory, whatever the package keeps at module
level. A conversion goes out to a subprocess through a scratch directory, so
the question is whether two of those running at once can reach each other's.

The comparison is always against a reading done alone: concurrency may change
when an answer arrives, never what it is.
"""
from concurrent import futures

import numpy as np
import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS

THREADS = 8


@pytest.fixture(scope="module")
def specimens():
    chosen = IMAGE_SPECIMENS[:3]
    for specimen in chosen:
        require_specimen(specimen)
    return chosen


@pytest.fixture(scope="module")
def read_alone(specimens):
    """What each measurement looks like with nothing else going on."""
    return {s.relpath: content_mod.extract_content(gwyddionpy.load(s.path))
            for s in specimens}


def read(specimen):
    return specimen.relpath, content_mod.extract_content(
        gwyddionpy.load(specimen.path))


def assert_matches_solo(relpath, content, expected):
    reference = expected[relpath]
    assert content["channel_names"] == reference["channel_names"], relpath
    assert content["source_format"] == reference["source_format"], relpath
    for name, channel in reference["channels"].items():
        actual = content["channels"][name]
        assert content_mod.float_diffs(
            channel["pixels"], actual["pixels"], where=f"{relpath} {name} @ "
        ) == []
        assert content_mod.meta_diffs(channel["meta"], actual["meta"]) == [], (
            f"{relpath} {name} metadata"
        )


def test_one_file_read_by_many_threads_at_once(specimens, read_alone):
    specimen = specimens[0]
    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(pool.map(read, [specimen] * THREADS))
    for relpath, content in results:
        assert_matches_solo(relpath, content, read_alone)


def test_different_files_read_at_once_do_not_cross(specimens, read_alone):
    """The failure a shared scratch path would cause: one measurement's data
    turning up in another's result."""
    work = list(specimens) * 3
    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(pool.map(read, work))

    assert len(results) == len(work)
    for relpath, content in results:
        assert_matches_solo(relpath, content, read_alone)


def test_threads_do_not_share_a_scratch_directory(specimens, monkeypatch):
    """context part: each call makes its own scratch directory, which is what
    keeps simultaneous conversions apart. Recorded here by noting the path
    every call actually used."""
    used = []
    real_parse = gwyddionpy.parse_gwy

    def note(path):
        used.append(str(path))
        return real_parse(path)

    monkeypatch.setattr(gwyddionpy, "parse_gwy", note)
    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        list(pool.map(read, list(specimens) * 2))

    assert len(used) == len(specimens) * 2
    assert len(set(used)) == len(used), f"scratch paths were shared: {used}"


def test_failures_in_some_threads_do_not_disturb_the_others(specimens,
                                                            read_alone):
    good = specimens[0]

    def work(index):
        if index % 2:
            with pytest.raises(gwyddionpy.GwyddionPyError):
                gwyddionpy.load("gwyddionpy/tests/data/README.md")
            return None
        return read(good)

    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(pool.map(work, range(THREADS)))

    succeeded = [r for r in results if r is not None]
    assert succeeded, "no thread was given real work"
    for relpath, content in succeeded:
        assert_matches_solo(relpath, content, read_alone)


def test_overruns_in_some_threads_do_not_disturb_the_others(specimens,
                                                            read_alone):
    """A conversion stopped part-way in one thread must not take another's
    with it — they share nothing but the module."""
    good = specimens[0]

    def work(index):
        if index % 2:
            with pytest.raises(gwyddionpy.ConversionError):
                gwyddionpy.load(good.path, timeout=0.001)
            return None
        return read(good)

    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(pool.map(work, range(THREADS)))

    for relpath, content in (r for r in results if r is not None):
        assert_matches_solo(relpath, content, read_alone)


def test_listing_formats_from_many_threads(specimens):
    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        listings = list(pool.map(lambda _: gwyddionpy.list_formats(),
                                 range(THREADS)))
    first = listings[0]
    assert len(first) >= 170
    for listing in listings[1:]:
        assert listing == first


def test_reading_native_gwy_files_in_parallel(tmp_path):
    """The in-process path shares more than the subprocess one does: no
    converter, no scratch directory, just gwyfile and the model."""
    from helpers.gwy_builder import make_gwy

    paths = []
    for index in range(THREADS):
        values = np.full((16, 16), float(index))
        paths.append(make_gwy(tmp_path / f"native{index}.gwy",
                              [{"name": f"Channel {index}", "data": values}]))

    def read_native(index):
        data = gwyddionpy.load(paths[index])
        return index, data

    with futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(pool.map(read_native, range(THREADS)))

    for index, data in results:
        assert list(data.channels) == [f"Channel {index}"]
        np.testing.assert_array_equal(
            data.channels[f"Channel {index}"].data, np.full((16, 16), float(index))
        )
