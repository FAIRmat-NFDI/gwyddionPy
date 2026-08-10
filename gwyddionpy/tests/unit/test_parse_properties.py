"""Properties the .gwy reader must hold for generated inputs: arbitrary
bytes, cuts at many offsets, single-byte edits.

*Rejection* — anything unreadable comes back as a typed error, never a
crash, a hang or invented data. *Fidelity* — anything valid survives being
read unchanged. Generation is derandomized, so failures reproduce.
"""
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import gwyddionpy
from helpers.gwy_builder import make_gwy

# Each example writes and parses a real file, far slower than hypothesis
# expects, so the deadline is lifted and the example count kept modest.
PROPERTY_SETTINGS = settings(
    deadline=None,
    derandomize=True,
    max_examples=60,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

CHANNEL_NAMES = st.text(min_size=1, max_size=24).filter(
    lambda s: s.strip() != "" and "\x00" not in s)
# The NUL character (a zero byte) is excluded: the container terminates
# strings with it, so a value holding one cannot be represented.
META_TEXT = st.text(max_size=40).filter(lambda s: "\x00" not in s)


@pytest.fixture(scope="module")
def valid_container(tmp_path_factory):
    """A small, well-formed .gwy to cut up and corrupt."""
    directory = tmp_path_factory.mktemp("valid")
    path = make_gwy(directory / "valid.gwy", [
        {"name": "Height", "data": np.arange(64.0).reshape(8, 8),
         "xreal": 2e-6, "yreal": 1e-6, "unit_xy": "m", "unit_z": "m",
         "meta": {"Scan Rate": "1.5 Hz"}},
    ])
    return path.read_bytes()


# --------------------------------------------------------------------------
# Rejection
# --------------------------------------------------------------------------
@given(payload=st.binary(min_size=0, max_size=512))
@PROPERTY_SETTINGS
def test_arbitrary_bytes_are_rejected_not_misread(payload, tmp_path):
    path = tmp_path / "input.gwy"
    path.write_bytes(payload)
    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(path)


#: Why two of the offsets below never return: gwyfile reads an object
#: array's item count without bounds-checking it, so a corrupted count sends
#: it round a loop up to 2**32 times over an exhausted buffer.
HANG_REASON = ("gwyfile loops on a corrupt object-array count and never "
               "returns; defect in the gwyfile package, to be reported "
               "upstream at https://github.com/tuxu/gwyfile/issues")

#: Sampled rather than exhaustive, because each runs in its own process.
TRUNCATION_OFFSETS = [
    0, 4, 8, 21, 34, 47, 62, 77, 91, 105,
    pytest.param(106, marks=pytest.mark.xfail(raises=TimeoutError, strict=True,
        reason=HANG_REASON)),
    131, 167, 208, 300, 420, 560, 700, 760,
    pytest.param(785, marks=pytest.mark.xfail(raises=TimeoutError, strict=True,
        reason=HANG_REASON)),
]

READ_ONE = """
import sys
sys.path.insert(0, {tests!r})
import gwyddionpy
try:
    gwyddionpy.load(sys.argv[1])
    print("read")
except gwyddionpy.UnsupportedFormatError:
    print("rejected")
except BaseException as error:
    print("escaped:" + type(error).__name__)
"""


def read_out_of_process(path, timeout=6):
    """Read a file in a process of its own and report what happened.

    Out of process because some damaged inputs never return, and neither a
    signal alarm nor Ctrl-C interrupts the loop. Killing is the only way out.
    """
    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, "-c",
             READ_ONE.format(tests=str(Path(__file__).resolve().parents[1])),
             str(path)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"reading {path.name} never returned") from None
    return result.stdout.strip() or f"no output; stderr={result.stderr[:200]}"


@pytest.mark.parametrize("cut", TRUNCATION_OFFSETS)
def test_a_container_cut_short_is_rejected_or_read_but_never_hangs(
    cut, valid_container, tmp_path
):
    """A file copied while still being written looks like this. Rejected or
    read are both fine; an uncatchable exception or a hang are not."""
    path = tmp_path / "cut.gwy"
    path.write_bytes(valid_container[:cut])

    outcome = read_out_of_process(path)
    assert outcome in ("read", "rejected"), f"cut to {cut} bytes: {outcome}"


@pytest.mark.parametrize("position", [0, 40, 120, 194, 400, 700])
@pytest.mark.parametrize("replacement", [0, 255])
def test_a_single_altered_byte_never_escapes_the_error_type(
    position, replacement, valid_container, tmp_path
):
    """One changed byte must never raise something the caller cannot catch.
    Read out of process because it can also land in an item count and
    trigger the unbounded loop described above."""
    corrupted = bytearray(valid_container)
    corrupted[position] = replacement
    path = tmp_path / "input.gwy"
    path.write_bytes(bytes(corrupted))

    outcome = read_out_of_process(path)
    assert outcome in ("read", "rejected"), (
        f"byte {position} set to {replacement}: {outcome}"
    )


@given(payload=st.binary(min_size=1, max_size=64))
@PROPERTY_SETTINGS
def test_noise_appended_to_a_valid_container(payload, valid_container,
                                             tmp_path):
    """Trailing rubbish, as a truncated download or a concatenation mistake
    would leave."""
    path = tmp_path / "input.gwy"
    path.write_bytes(valid_container + payload)

    try:
        gwyddionpy.load(path)
    except gwyddionpy.UnsupportedFormatError:
        pass


# --------------------------------------------------------------------------
# Fidelity
# --------------------------------------------------------------------------
@given(name=CHANNEL_NAMES, rows=st.integers(1, 8), cols=st.integers(1, 8))
@PROPERTY_SETTINGS
def test_any_channel_name_and_shape_survives(name, rows, cols, tmp_path):
    values = np.arange(rows * cols, dtype="f8").reshape(rows, cols)
    path = make_gwy(tmp_path / "c.gwy",
                    [{"name": name, "data": values}])

    channels = gwyddionpy.load(path).channels
    assert list(channels) == [name]
    assert channels[name].data.shape == (rows, cols)
    np.testing.assert_array_equal(channels[name].data, values)


@given(key=CHANNEL_NAMES, value=META_TEXT)
@PROPERTY_SETTINGS
def test_any_metadata_text_survives_unchanged(key, value, tmp_path):
    """Vendor metadata is text and must come back as the same text: no
    trimming, no reinterpretation."""
    path = make_gwy(tmp_path / "m.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {key: value}}])

    meta = gwyddionpy.load(path).channels["Height"].meta
    assert meta.get(key) == value


@given(values=st.lists(st.floats(allow_nan=True, allow_infinity=True,
                                 width=64), min_size=4, max_size=4))
@PROPERTY_SETTINGS
def test_any_pixel_values_survive_including_gaps(values, tmp_path):
    array = np.array(values, dtype="f8").reshape(2, 2)
    path = make_gwy(tmp_path / "p.gwy",
                    [{"name": "Height", "data": array}])

    returned = gwyddionpy.load(path).channels["Height"].data
    np.testing.assert_array_equal(returned, array)


@given(count=st.integers(min_value=1, max_value=6))
@PROPERTY_SETTINGS
def test_channel_order_follows_the_file_however_many_there_are(count, tmp_path):
    names = [f"Channel {index}" for index in range(count)]
    path = make_gwy(tmp_path / "n.gwy",
                    [{"name": name, "data": np.full((2, 2), float(index))}
                     for index, name in enumerate(names)])

    assert list(gwyddionpy.load(path).channels) == names


def test_a_nul_in_metadata_makes_an_unreadable_file(tmp_path):
    """Records a known defect rather than approving of it: a NUL ends the
    field early, so the writer produces a file this package then refuses to
    read. Writing should reject the value instead."""
    path = make_gwy(tmp_path / "nul.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {"Comment": "before\x00after"}}])

    with pytest.raises(gwyddionpy.UnsupportedFormatError):
        gwyddionpy.load(path)


@pytest.mark.parametrize("value", ["a\nb", "a\tb", "  spaced  ", "µm °C α→β",
                                   "\\backslash", '"quoted"'])
def test_awkward_but_representable_metadata_survives(value, tmp_path):
    """Everything short of a NUL comes back untouched."""
    path = make_gwy(tmp_path / "awkward.gwy",
                    [{"name": "Height", "data": np.zeros((2, 2)),
                      "meta": {"Comment": value}}])

    assert gwyddionpy.load(path).channels["Height"].meta["Comment"] == value
