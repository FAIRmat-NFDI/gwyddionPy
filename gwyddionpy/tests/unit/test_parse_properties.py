"""Properties the .gwy reader must hold for inputs nobody thought to write.

The damaged files elsewhere in the suite are ones a person chose: empty,
truncated at the header, body overwritten. Those cover the failures somebody
already imagined. These generate inputs instead — arbitrary bytes, cuts at
every offset, single-byte edits — and assert the properties that must hold
whatever comes in.

Two families, and they are different in kind:

  rejection   anything that is not a readable container must come back as a
              typed error. Not a crash, not a hang, and not a silent success
              that yields data invented from noise.
  fidelity    anything that *is* a valid container must survive being read:
              names, shapes, units and metadata come back as they went in.

context part: generation is derandomized, so a run here is reproducible from
the source alone and a failure someone reports can be reproduced exactly.
Hypothesis still shrinks a failing input to its simplest form before showing
it, which is most of the value — the smallest broken file is usually the one
that explains the bug.
"""
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import gwyddionpy
from helpers.gwy_builder import make_gwy

# Reading writes and parses a real file each time, which is far slower than
# hypothesis expects of a test body, so the per-example deadline is lifted and
# the example count kept deliberately modest.
PROPERTY_SETTINGS = settings(
    deadline=None,
    derandomize=True,
    max_examples=60,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

CHANNEL_NAMES = st.text(min_size=1, max_size=24).filter(
    lambda s: s.strip() != "" and "\x00" not in s)
# NUL is excluded deliberately: the container stores strings NUL-terminated,
# so a value containing one cannot be represented at all. See
# test_a_nul_in_metadata_makes_an_unreadable_file for what happens if it is.
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


#: Why two of the offsets below never return. gwyfile reads an object array's
#: item count as an unbounded uint32 straight from the buffer, so a count that
#: corruption has made enormous sends it round a loop up to 2**32 times over an
#: exhausted buffer. Upstream defect, recorded rather than worked around.
HANG_REASON = ("gwyfile loops on a corrupt object-array count and never "
               "returns; upstream defect, see §2.15 of the test plan")

#: Offsets to cut a container at. Sampled rather than exhaustive because
#: each one is read in a process of its own — see the test below for why.
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

    Out of process because some damaged inputs never return, and no
    in-process limit stops them: the loop sits below a C-level call chain, so
    neither a signal alarm nor Ctrl-C interrupts it. Killing the process is
    the only way out, which means the reader has to be somewhere killable.
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
    """Cut a valid container at a given offset and read what is left.

    A file copied while still being written, or a transfer that stopped, looks
    exactly like this. Two outcomes are acceptable — rejected as a typed
    error, or read successfully — and two are not: an exception the caller
    cannot catch, or never returning at all.
    """
    path = tmp_path / "cut.gwy"
    path.write_bytes(valid_container[:cut])

    outcome = read_out_of_process(path)
    assert outcome in ("read", "rejected"), f"cut to {cut} bytes: {outcome}"


@pytest.mark.parametrize("position", [0, 40, 120, 194, 400, 700])
@pytest.mark.parametrize("replacement", [0, 255])
def test_a_single_altered_byte_never_escapes_the_error_type(
    position, replacement, valid_container, tmp_path
):
    """One changed byte either still reads, or fails as a typed error.

    What it must never do is raise something the caller cannot catch. Byte 194
    set to zero used to produce a bare `ValueError: cannot reshape array of
    size 64 into shape (0,8)` — raised when the channel's array was first
    touched, long after the file appeared to have been read.

    Read out of process for the same reason as the truncation test: a changed
    byte can land in an item count and send the reader into the unbounded loop
    described there.
    """
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
    """Trailing rubbish, as a truncated download followed by other data or a
    concatenation mistake would leave."""
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
    """Vendor metadata is text and must come back as the same text — no
    trimming, no reinterpretation, whatever characters it holds."""
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
    """A metadata value cannot contain a NUL, and saying so is better than
    finding out later.

    warning: this records a real defect rather than approving of it. The
    container stores strings NUL-terminated, so a NUL inside one ends the
    field early and corrupts everything after it — the writer produces a file
    that this package itself then refuses to read. It should reject such a
    value when writing instead of emitting a broken file.
    """
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
