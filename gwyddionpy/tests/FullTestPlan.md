# Test plan — gwyddionpy / gwyddionpy-converter

**Where things stand:** 529 tests. 505 pass, 22 are skipped on purpose, 2 are
marked as known failures in a library we depend on. Everything planned is
built except §2.2 (more vendor files), which needs sample files rather than
code and is now partly under way.

**Why this document exists.** The suite is large, and a lot of it exists
because of a specific bug rather than a general principle. This file records
which test covers what, and *why* each choice was made — so that a change six
months from now is made with the reasoning in view instead of guessed at.

**What the tests were worth.** Nearly every step turned up a real bug in the
source rather than just confirming what already worked:

- damaged `.gwy` files raised errors nobody could catch
- the converter had no time limit, so a stuck one hung the caller for ever
- metadata numbers came out differently depending on the computer's language
  settings — and the wrong version had already been recorded as correct
- writing a `.gwy` corrupted one-character text, and could produce a file we
  could not read back
- a channel could vanish silently during export
- a damaged file could send the reader into an endless loop

Each is described in the section that found it.

---

## How to read this file

Section 2 is the substance: one entry per topic, each saying what is covered,
what was decided, and what was found. Sections 3–5 are the priority order,
the open questions, and how the files are arranged.

Two conventions used throughout the test code itself:

- a `context part:` line explains *why* something is written the way it is
- a `warning:` line flags a caveat or a known problem

Neither is a description of what the code does, so they can be skipped when
you only want the behaviour.

---

## 1. What is covered

| File | What it checks |
|------|----------------|
| `unit/test_parse.py` | Reading `.gwy` files built for the test: several channels, metadata precedence, untitled and duplicate channel names, missing units, empty files, non-ASCII text |
| `unit/test_exports.py` | Round trips through HDF5, `to_dict()` and `.gwy` on built fixtures: nested metadata, value/unit splitting, key clashes, channel names containing `/` |
| `unit/test_reference_schema.py` | The comparison machinery itself — the code that decides whether two readings match |
| `unit/test_export_edge_cases.py` | **§2.16** Awkward but legal data through every export: odd shapes, gaps, flat channels, huge and tiny numbers, one-character and non-ASCII text |
| `unit/test_parse_properties.py` | **§2.15** Generated inputs: random bytes, truncations and single-byte edits must be rejected cleanly or read correctly — never crash, never hang |
| `converter/test_discovery.py` | How the converter binary is located, and what happens when it is not there |
| `converter/test_invocation.py` | Running it: `.gwy` input skipping the converter, errors when it is unreachable, the format list |
| `converter/test_malformed_input.py` | **§2.4** Broken files of every kind are rejected with a clear, catchable error |
| `converter/test_timeout.py` | **§2.5** A converter that does not finish is stopped and reported |
| `converter/test_locale.py` | **§2.11** Reading gives the same answer whatever language the computer is set to |
| `converter/test_determinism.py` | **§2.12** Reading the same file twice gives exactly the same result |
| `converter/test_cli_contract.py` | **§2.7** The binary's own promises: exit codes, clean output streams, awkward paths |
| `converter/test_thread_safety.py` | **§2.6** Several threads reading at once do not interfere |
| `converter/test_process_isolation.py` | **§2.13** Several separate programs reading at once do not interfere |
| `converter/test_resource_hygiene.py` | **§2.14** Repeated reading leaks nothing: no open files, no leftover folders, no held memory |
| `converter/test_memory_footprint.py` | **§2.20** How much memory a conversion costs, and whether it grows with the data in the way it should |
| `converter/test_build_consistency.py` | **§2.8** Two different builds of the converter read a file the same way |
| `converter/test_platform.py` | **§2.9** Linux, macOS and Windows differences, checked rather than skipped |
| `converter/test_fetch_converter.py` | The old download route, kept but deprecated (see below) |
| `formats/test_sanity.py` | Broad checks true of any correct reading, so a newly added file is covered immediately |
| `formats/test_reference.py` | **§2.1** Each measurement compared field by field against a stored reference |
| `formats/test_vendor_header.py` | The two Bruker references checked against the raw files' own headers, so they are not just confirming themselves |
| `formats/test_export_chain.py` | **§2.3** Real measurements carried through every export unchanged |
| `gwyddionpy-converter/tests/test_packaging.py` | **§2.10** The installed wheel: the binary is where the package says, and runs |

**The old download route.** `converter/test_fetch_converter.py` covers
fetching a converter from a GitHub release. That route is **deprecated** —
installing the `gwyddionpy-converter` wheel is the supported way — but it
still ships, so it is still tested. Code on its way out is exactly the code
nobody notices breaking, and this one downloads and runs a binary.
`ensure_converter()` raises a `DeprecationWarning`, the command prints the
same notice to the terminal (a warning alone would be invisible there), and
`docs/user/how-to.md` marks the route deprecated.

---

## 2. The topics

### 2.1 Comparing against a stored reference — **done**

`formats/test_reference.py`, `helpers/content.py`, references captured by
`tests/make_reference.py` and stored beside each raw file.

The idea: read each measurement once, record what came out, and compare
future readings against that record.

- **The reference is JSON, not a stored `.gwy`.** JSON can be read in a
  review and shows a meaningful diff when a value changes. A stored `.gwy`
  would be stricter but would also differ for reasons that have nothing to do
  with the data.
- **What is recorded per channel:** shape, size, dtype, physical dimensions,
  both units, pixel values at fixed positions, and all vendor metadata.
  Whole-array statistics were tried and dropped — shape plus sampled pixels
  already pins the array.
- **One test per element**, so a failure names what broke and where:
  `test_units[jpk/sample_0.jpk]`, not one large assertion that stops at the
  first difference.
- **One file open at a time.** Each measurement is read, tested, and released
  before the next is opened, so memory is bounded by the largest file rather
  than the total. Measured at ~66 MB one at a time against ~97 MB holding all
  seven. A test asserts this so it cannot quietly regress.
- **Numbers compare with a small tolerance** (`rtol=1e-9`), tight enough to
  catch a one-part-per-million drift but loose enough to ignore last-digit
  differences between compilers. Text and metadata compare exactly.
- **Missing pixel values** (NaN, infinity) are stored as text so the
  reference stays valid JSON. Only numeric fields are treated this way —
  never metadata, where `NaN` might genuinely be the recorded text.
- **The comparison code is itself tested** (`unit/test_reference_schema.py`).
  This matters: breaking the comparison so it reports no differences leaves
  every format test passing. Four of the seven element tests can only fail
  through those helpers, so they are exercised directly.
- **The reference is not allowed to confirm itself.** A reference captured
  from a conversion only proves the converter still agrees with its past
  self. Two files are also read straight out of their own text headers and
  compared:
  - **Bruker NanoScope** — scan geometry (`\Scan Size: 20000 nm`,
    `\Samps/line: 512`, `\Lines: 512`). Matches exactly.
  - **Bruker SPMLab `.FLT`** — geometry (`ScanRangeX/Y=1.0000 µm`,
    `ResolutionX/Y=512`), and then the whole array. The header states
    `DataOffset`, the resolution and `ZTransferCoefficient=0.7731 µm/V`;
    reading the float32 block ourselves and applying that coefficient
    reproduces all 262144 values bit-for-bit. This is the strongest check in
    the suite: it rests on the raw bytes rather than on a past conversion,
    and it covers every pixel rather than the seven the reference samples.
    Three things it pins that nothing else would:
    - the **z calibration**, against the vendor's own coefficient;
    - the **row order** — the block is stored bottom row first and the
      converter turns it the right way up. A reference captured from a
      flipped reading would look perfectly self-consistent for ever;
    - the **shape**, from the file's length: `DataOffset` plus
      rows x columns x 4 lands exactly on the end of the file.
- **Still open:** JPK, WSxM, Igor and Nanonis have no readable text header,
  so their references rest on the captured reading alone. Confirming them
  needs someone with the instrument, or a second independent reader.

### 2.2 More vendors and formats — **still the thinnest area**

The converter reads 170+ formats; five vendors and six files are here.

Most recent addition: `bruker_spmlab/…​.FLT`, a Dimension Edge measurement in
SPMLab floating-point format. It is the first case of **one vendor in two
formats handled by two different modules** (`nanoscope` and `spmlabf`) —
which is exactly the "more than one file per vendor" point below, and it
arrived with a header complete enough to verify the reading end to end.

- Add files under `tests/data/<vendor>/` and an entry in the `SPECIMENS`
  registry. Prioritise formats NOMAD users actually bring.
- More than one file per vendor is worth more than more vendors: header
  layouts drift between firmware versions, and that is a common way readers
  break.
- Record where each file came from and its licence in `tests/data/README.md`.

### 2.3 Real measurements through the exports — **done**

`formats/test_export_chain.py`.

- Every measurement goes through `to_dict()`, `to_hdf5()` and `to_gwy()`, and
  the content is compared with what was read.
- The dict and HDF5 layouts are also compared **with each other**, because
  they promise the same structure.
- Recorded behaviour: a `.gwy` we write reports no `source_format`. That
  field says which vendor reader handled the original, and a file we wrote
  was not read by one. Worth stating so nobody is surprised.
- Three bugs were found here — described in §2.16.

### 2.4 Broken and hostile input — **done**

`converter/test_malformed_input.py`.

- Empty files, random bytes, text in a binary format, headers cut short, data
  truncated or replaced, wrong extension. All are rejected quickly and
  cleanly.
- **Bug found and fixed.** A damaged `.gwy` is read inside Python rather than
  by the converter, and used to raise whatever the reading library happened
  to hit: `AssertionError` (sometimes with no message), `ValueError`,
  `struct.error`, `UnicodeDecodeError`. None of these was a `GwyddionPyError`,
  so a caller catching the documented errors caught none of them — and with
  Python's `-O` flag the `AssertionError` disappeared entirely. `_parse.py`
  now turns any such failure into `UnsupportedFormatError`, naming the file
  and keeping the original error attached. One test runs the empty-file case
  under `-O` to cover that path too.
- **Error messages now list what could be wrong** — empty, truncated header,
  incomplete data, corrupted, or not this format at all. The underlying fault
  ("unpack requires a buffer of 4 bytes") means nothing to the person holding
  the file. An empty file is named outright rather than guessed at.
- Also covered: passing a folder instead of a file, no leftover temporary
  folders after a failure, and normal reading still working afterwards.

### 2.5 Time limit and interruption — **done**

Changed in `_run.py`, tested in `converter/test_timeout.py`.

- **Decided:** a 300-second default, changeable per call. Going over raises
  `ConversionError` naming the file and the limit, keeping the underlying
  timeout attached. No new exception type — callers already catch
  `ConversionError`.
- The limit is a safety net, not a performance budget. It sits far above any
  legitimate reading, so a file that hits it is a fault to investigate rather
  than a reason to raise the number.
- **Ctrl-C is not a timeout.** An interrupt reaches the caller unchanged
  rather than being turned into a `ConversionError`, which is what an
  interactive user expects. Confirmed by interrupting a running conversion.
- **Cleanup needed no new code.** Python kills and collects the converter on
  both a timeout and an interrupt. Measured: no converter processes survive.

  Worth knowing why that works: the installed `gwyconvert` is a small shell
  script that sets library paths and ends with `exec`. Because it *execs*, it
  is replaced by the real binary rather than starting a second process, so
  the process Python is holding really is the converter. A wrapper that
  called the binary instead would strand a leftover process on every timeout.

### 2.6 Several threads at once — **done**

`converter/test_thread_safety.py`.

Threads share everything, so the question is whether two conversions running
together can reach each other's temporary files.

- The same measurement read by many threads gives the same answer as reading
  it alone.
- Different measurements read together do not mix.
- Each call gets its own temporary folder, checked by having the threads
  report the path they used.
- Failures and timeouts in some threads do not disturb the others.

### 2.7 What the command-line tool promises — **done**

`converter/test_cli_contract.py`, running the binary directly.

- **Exit codes hold as documented:** 0 for success, 1 when the file cannot be
  read or written, 2 for a bad command. `--help` and `--version` are *not*
  supported and fall into the bad-command path — recorded as current
  behaviour, not endorsed.
- Normal output is parsed as JSON and nothing else, so any stray printing
  would fail the parse.
- **Bug found and fixed: the error stream was never clean.** Every run —
  including successful ones — printed three warnings from the graphics
  libraries, ending with advice to run a command as root that would not help.
  The path in the message comes from the machine the converter was built on
  and exists on nobody else's. This noise had been appearing inside our own
  error messages.

  Fixed in two places: in the bundling script, so future builds are quiet;
  and in `converter_environment()`, so it is quiet immediately without
  rebuilding. Checked safe — the format list and every conversion are
  unchanged, because the converter draws nothing.
- Paths with spaces, non-ASCII characters, quotes and brackets all work.
- Relative and absolute paths are compared **as data, not as bytes**:
  Gwyddion records the path it was given inside the file, so the two outputs
  differ in length while describing the same measurement.
- Also recorded: an existing output file is overwritten without asking, and
  the input file is never modified.

### 2.8 Two builds agreeing — **done**

`converter/test_build_consistency.py`.

The converter can be built more than one way, pulling in different Gwyddion
versions. A file must mean the same thing either way.

- With a second build named in `GWYDDIONPY_ALT_CONVERT`, every measurement is
  read twice and compared directly. Measured between a wheel build reporting
  170 formats and a source build reporting 163: **identical**, pixels and
  metadata alike.
- Without a second build, the stored references stand in. Any build that
  passes them agrees with the build they were captured from, and so with
  every other build that passes them. This is the same guarantee reached
  indirectly, not a weaker one.
- Those 8 tests skip when no second build is configured. That is the one
  place a skip means "optional extra tooling is absent" rather than
  "something is missing".

### 2.9 Linux, macOS and Windows — **done**

`converter/test_platform.py`, `helpers/platforms.py`, plus a check that runs
before any test.

- **These tests are opt-in.** Without a declared platform they are skipped,
  so someone working on Linux is not asked about Windows path spelling. CI
  declares a platform on every leg, so they always run there.
- **A declared run must really be that platform**, set with
  `--require-platform` or `GWYDDIONPY_REQUIRE_PLATFORM`. If it is running
  somewhere else the run **stops with an error**. This catches the one thing
  a test matrix cannot otherwise show: an image that changed, a typo in the
  job file, a leg that quietly fell back to the default runner. All of those
  produce a green run that tested the wrong system.
- **Once running, nothing skips for want of a capability.** Each test asserts
  what should be true of the platform it finds itself on: paths use the
  native separator, and the memory-measuring call exists exactly where it
  should. A capability that should be absent is asserted absent, so a
  platform quietly losing one is noticed.
- **The wrapper belongs to the bundle, not to gwyconvert.** The wheel is
  reached through a shell wrapper on Linux and macOS that sets its library
  paths before exec-ing the real binary, and directly as a plain `.exe` on
  Windows. A converter built against a system Gwyddion finds its libraries
  the ordinary way and is correctly a bare executable, so that test asks the
  installed package for its own binary and skips where no wheel is installed
  — the two source-building CI jobs. What is asserted of *any* converter, in
  every job, is that it is an executable file that runs.
- **No stored format lists per platform.** An earlier draft recorded them and
  compared; it was dropped as needless upkeep. Agreement about content
  already follows from every platform running the same measurements against
  the same references. What is checked live is that the build carries the
  readers the measurements need.
- **CI:** a `pytest-built-wheel` matrix runs on Linux, both macOS variants
  and Windows, installing the converter wheel the way a user would. That is
  also the only place the §2.10 packaging tests run. Linux additionally
  generates a comma-decimal locale, without which §2.11 cannot prove
  anything.
- **The wheel it installs is built from the branch**, by calling
  `build-converter.yml` rather than by pulling the converter from an index.
  An earlier version installed the published wheel, which meant these legs
  tested the last *release*: a change to `gwyconvert.c` or to a build recipe
  could not be checked until after it had shipped. Four real bugs reached
  users that way — macOS arm64 registering eight formats fewer than x86_64,
  unreadable non-ASCII paths on Windows, numbers returned with commas there,
  and a GLib assertion on every run — none of which any leg could have
  caught. Building the converter here is what makes this a gate on the
  change under review rather than a report on an artifact that change
  cannot affect.

### 2.10 The packaging layer — **done**

`gwyddionpy-converter/tests/test_packaging.py`, run against the really
installed wheel.

- `binary_path()` returns an absolute path that exists, is executable, sits
  inside the package, and actually runs.
- A missing bundle gives a clear error, because gwyddionpy treats that as
  "look somewhere else" — a confusing message here surfaces much later as a
  converter that simply cannot be found.
- The seam between the two packages is covered: with nothing else configured,
  gwyddionpy finds this binary.

`setup.py`'s wheel-tag logic is **not** pinned by a test yet. It was
hardcoded when these tests were written; the multi-platform version has since
arrived, so this is now worth doing.

### 2.11 Language and region settings — **done**

`converter/test_locale.py`; fixed in `_run.py`.

- **Bug found and fixed, and it was already causing harm.** Gwyddion formats
  numbers using the computer's language settings, so a JPK duty cycle came
  back as `0,881` on one machine and `0.881` on another — from the same file.
  The development machine was set to German numbers, so the references were
  captured **with commas in them** and the suite failed on a machine set to
  plain English. It would have failed in CI on the first run.
- The converter now always runs with numeric formatting pinned. Only numbers
  are pinned — forcing everything would risk the µm and °C characters that
  fill vendor metadata.
- **A second, subtler bug:** the setting that pins numbers is outranked by a
  broader one, so pinning it alone still lost to a caller who had set the
  broader variable. The fix spreads that caller's choice across the other
  categories and removes the override, leaving everything intact except the
  decimal mark.
- The tests first prove the comma setting is genuinely active. A locale that
  is not installed silently falls back, and the comparison would then be
  plain English against itself — passing while proving nothing.

### 2.12 Same file, same answer — **done**

`converter/test_determinism.py`.

- Reading the same measurement two and three times agrees on every element.
  Pixel values are compared **exactly**, with no tolerance: two readings on
  one machine have no excuse to differ, and that is the comparison that would
  expose uninitialised memory.
- A reading in a separate program is compared with one in this program, so
  nothing cached inside a single run can hide a difference.
- Channel order, detected format and the format list are all pinned.
- **Byte-identical output is not possible, and now we know why.** Two
  conversions differ in exactly 11 bytes: the timestamp Gwyddion writes into
  the file. A test keeps that difference confined to one short timestamp, so
  a build that either became fully reproducible or started varying some new
  way would be noticed.

### 2.13 Several separate programs at once — **done**

`converter/test_process_isolation.py`.

This section originally asked about two programs racing to download a
converter into a shared cache. That is no longer the main route — the wheel
is — so the question was replaced by the situation that really happens: a
shared analysis machine, or a parallel test runner, reading several files at
once.

- The same measurement read by eight programs at once gives one answer.
- Different measurements do not mix.
- Each call gets its own temporary folder, and none survives.
- One program failing does not disturb the others.

The old race was real, and the download route is **kept but deprecated**, so
it is recorded as an open item in §4 rather than dismissed.

### 2.14 Leaving nothing behind — **done**

`converter/test_resource_hygiene.py`. Nothing here fails on a single reading;
every check repeats an operation and looks at what piled up — which is what a
long batch job would eventually hit.

- **Open files:** none leak across repeated readings, repeated failures,
  repeated format listings, or repeated native `.gwy` readings.
- **Temporary folders:** none survive success, failure or a timeout. One test
  watches a folder being created and then removed, so the others cannot pass
  by counting something that never existed.
- **Held memory:** a discarded reading is released, including after an error,
  whose traceback could otherwise pin a whole measurement for anyone logging
  failures.
- **Both measuring techniques are proved to work first**, against a
  deliberate leak. Without that, a check that cannot fail is worse than none.
- **Leftover processes** are covered by checking that the bundle's wrapper
  `exec`s the real binary (§2.9), rather than by listing processes — which
  has no portable form.

### 2.15 Generated inputs — **done, and it paid for itself**

`unit/test_parse_properties.py`. Instead of files a person thought of, these
are generated: random bytes, cuts at many offsets, single-byte edits.
Generation is repeatable, so a failure can be reproduced exactly.

**Three bugs, none of which the hand-written cases in §2.4 reached:**

1. **The §2.4 fix was incomplete.** It guarded the file-opening call only,
   but the reading library builds a channel's array *lazily*, when first
   touched — long after the file appears to have been read. One changed byte
   still produced a bare `ValueError`. Truncating a single file at every
   offset leaked four different uncatchable error types. The fix now covers
   the whole read.
2. **A damaged file can hang the reader for ever.** The reading library takes
   an item count straight from the file without checking it, so a corrupted
   count sends it round a loop up to four billion times. Two of twenty tested
   truncation points do this — a 106-byte file is enough. Nothing interrupts
   it; only killing the process works. **This is a bug in the `gwyfile`
   library and should be reported there.** The two cases are marked as known
   failures so a fix announces itself, and damaged files are read in a
   separate program here so the suite cannot hang.
3. **A NUL character in metadata produces an unreadable file.** The format
   stores text NUL-terminated, so writing one produces a file this package
   then refuses to read. It should refuse at writing time instead. Not yet
   fixed.

Still ahead, as separate CI work: fuzzing the C binary itself, sharing a
build with the sanitiser work in §2.20.

### 2.16 Awkward but legal data — **done**

`unit/test_export_edge_cases.py`, using built files so no converter or
measurement data is needed.

- Shapes from 1×1 to 2048×2; gaps preserved rather than turned into zeros;
  entirely flat channels; numbers from 1e-300 to 1e300; files with no
  channels at all.
- Recorded: a 32-bit source is widened to 64-bit, because the format stores
  doubles.

**Three bugs found and fixed**, all invisible to the earlier export tests
because those only used well-behaved data:

1. **One-character text was corrupted when writing.** The library guesses a
   component's type from its value and picks a single-character type for any
   text of length one. A metadata value of `"0"` came back as `48` — its
   character code — which is exactly the short flag values vendor headers are
   full of. Worse, a one-character non-ASCII value such as `"Å"` was written
   as two bytes and read back as one, leaving the whole file unreadable: the
   Igor measurement produced a `.gwy` that gwyddionpy itself could not open.
   Both symptoms had this one cause. The writer now states explicitly that
   text is text.

   Worth remembering: the container **copies** the type map it is given, so
   it must be complete before the container is created. Filling it in
   afterwards silently does nothing — a mistake the channel-title tests
   caught during this work.
2. **Two channels could collapse into one.** `/` becomes `_` for HDF5, so
   `"A/B"` and `"A_B"` landed on the same key: `to_dict()` **dropped one
   channel without a word**, and `to_hdf5()` failed part-way through. Both
   exports now share one naming helper that keeps them apart.
3. **Vendor text was turned into numbers it never was.** The old code called
   `int()`/`float()` on raw text, and both accept more than an instrument
   ever writes: `"1_000"` became `1000`, and full-width digits became ASCII
   ones. Parsing is now restricted to numbers as instruments actually write
   them.

### 2.17 Making sure the tests really ran — **done, by policy**

The worry: a suite that skips its way to green looks identical to one that
passed.

Settled by not skipping for anything that would make the run meaningless. A
missing converter or a missing measurement file **fails**. There is no
setting that lets the suite pass without having read the real files.

Two deliberate exceptions remain, and both announce themselves in the skip
message:

- the cross-platform tests (§2.9), which are opt-in because they only mean
  something when the platform is known and controlled
- the direct two-build comparison (§2.8), which needs a second converter
  build that most machines do not have

Both are about optional tooling being absent, never about the suite's own
subject matter being missing.

### 2.18 Testing the documentation — **removed**

An earlier version extracted the examples from the READMEs and ran them, so a
renamed method would break the published snippet. That file was removed
before the work was committed.

Worth reconsidering if the documented examples drift: it caught a renamed
method and a documented command that was never packaged.

### 2.19 Speed limits — **dropped**

Large-file memory is covered by §2.20, which bounds cost as a multiple of the
data and so scales to any file size without needing a huge sample. The other
half was a timing floor, and that is not worth its upkeep: run times move
with the machine and with CI load, so the threshold would be either too loose
to catch a real slowdown or tight enough to fail at random.

The number is kept rather than reused, so references to §2.20 elsewhere keep
meaning what they say.

### 2.20 Memory correctness in the C code — **partly done**

The converter is C built on large graphics libraries, so leaks are the
obvious worry. Most leaks in it **do not matter**: it reads one file and
exits, and the operating system takes everything back. Three cases are
exceptions:

1. A leak *inside one conversion* grows with the measurement, so a large scan
   runs out of memory rather than merely wasting some.
2. Leaks usually travel with worse faults — use-after-free, buffer overruns —
   which corrupt data whatever the process lifetime.
3. If many files are ever converted in one process, leaks stop being
   harmless.

**Done — the cheap part**, `converter/test_memory_footprint.py`. Cost is split
into the fixed part (starting up and registering readers) and the part that
grows with the data, because only the second is a leak signal:

| | measured | limit in the test |
|---|---|---|
| fixed | ~23–37 MB | 150 MB |
| per megabyte of pixels | ~1.1–2.0 MB | 4.0 MB |

Comparing the largest measurement against the smallest cancels the fixed cost
out, so a bigger graphics library does not move it while a leak that grows
with the file does. **Sensitivity, honestly:** the per-data cost has to
roughly triple before this complains. It guards against a change in kind, not
a budget.

**Not done — the thorough part**, which cannot live in the normal suite:

- **Valgrind** works on the shipped binary with no rebuild, but the graphics
  libraries leak by design at exit, so "zero bytes lost" would be permanently
  red. It needs the suppression file those libraries ship, and it is ~20×
  slower — a separate scheduled job.
- **AddressSanitizer** catches more and is only ~2× slower, but needs the
  converter *and* Gwyddion rebuilt for it — a dedicated build, shared with
  the fuzzing work in §2.15.
- Both should compare a small file against a large one rather than demanding
  zero, for the same reason the cheap test does.
- Windows cannot measure a child's peak memory without extra dependencies, so
  the footprint tests do not run there.

---

## 3. Order of work

1. ~~§2.1 Compare against stored references~~ — done, plus tests for the
   comparison machinery itself.
2. ~~§2.4 + §2.5 Broken input and time limits~~ — done; both found real bugs.
3. ~~§2.11 + §2.12 Locale and determinism~~ — done; the locale check caught a
   live bug that had already spoiled the stored references.
4. ~~§2.3 + §2.16 Export chain and awkward data~~ — done; found three export
   bugs, including a channel disappearing silently.
5. ~~§2.7 Command-line contract~~ — done; exit codes held, the error stream
   did not.
6. ~~§2.13 + §2.14 Separate programs and leftovers~~ — done; no leaks found.
7. **§2.2 More vendors and formats** — the only outstanding item. Needs
   sample files, not code.
8. ~~§2.6, §2.8, §2.10, §2.15~~ — done; generated inputs found three bugs,
   one of them a hang.
9. ~~§2.17~~ done by policy. §2.18 was written and then removed.
10. ~~§2.9 Cross-platform~~ — done. §2.20's valgrind and sanitiser legs
    remain as separate CI work.

---

## 4. Decisions and open questions

**Settled**

- References are **JSON of extracted fields**, stored beside the raw file.
- Raw files and their references are **committed** under
  `gwyddionpy/tests/data/<vendor>/`, and that is the tests' only data source.
  Nothing is downloaded while testing: a file from elsewhere is fetched by
  hand, checksummed into the registry, and committed. The suite stays
  offline, and a network outage cannot look like a test failure.
- Nothing skips for a missing converter or a missing measurement — see §2.17
  for the two deliberate exceptions.
- Tests run against the **installed** converter wheel, not a locally built
  binary and not a stand-in.
- The GitHub-release download route is **deprecated but kept**, to be removed
  in a future release. Until then it stays, is tested, and says so. When it
  goes, its tests and the "Option 2" section of `docs/user/how-to.md` go too.

**Still open**

- **The `gwyfile` hang (§2.15) should be reported upstream.** It is the most
  serious thing here: one damaged file stops a reader for ever.
- **A NUL in metadata** makes writing produce a file we cannot read back
  (§2.15). Writing should refuse instead.
- **The download route extracts straight into its shared cache**, so a second
  program can see a half-written binary and run it (measured: a 60 MB bundle
  visible from 128 KB upwards). Fixing it means extracting alongside and
  moving the finished result into place. Worth doing while the code ships, or
  consciously accepting.
- **Platform tests are not wired into the publish workflow.** They run in
  `pytest.yml`, but publishing to PyPI should be gated on them passing on all
  four targets first. The macOS and Windows legs are written but have never
  been executed.
- **`setup.py`'s wheel-tag logic has no test** (§2.10), now that the
  multi-platform version has landed.
- **Repository size**: ~30 MB of measurements, kept in history for ever.
  Acceptable now; revisit if §2.2 grows it a lot.
- **Is `UnsupportedFormatError` the right type for a damaged `.gwy`?** It
  reads correctly and avoids adding public API, but it inherits from
  `ConversionError` when no conversion happened.
- **Confirming the non-Bruker references independently** (§2.1).

---

## 5. How the files are arranged

Tests are grouped by what they are about. Data is grouped by vendor, with
each raw file and its reference kept together.

```
gwyddionpy/tests/
  conftest.py           shared fixtures, and the platform declaration check
  make_reference.py     captures the references (run deliberately, read the diff)
  helpers/              the shared machinery, importable from anywhere
      gwy_builder.py    builds .gwy files for tests
      specimens.py      the registry — one entry per raw file
      content.py        the reference format: extract, save, compare
      platforms.py      which platform this is, and what it can do
      requirements.py   a measurement is present and unaltered
  data/                 raw files and their references, by vendor
      bruker_nanoscope/  bruker_spmlab/  jpk/  wsxm/  igor_asylum/  nanonis/
  unit/                 parsing, model and exports on built inputs
  converter/            finding and running the converter
  formats/              reading the real measurements
```

- `helpers/` is importable everywhere via `pythonpath = ["tests"]` in
  `gwyddionpy/pyproject.toml`.
- **Adding a vendor costs one registry entry plus the file** — and a captured
  reference — never new test code, because every format test works from the
  registry. That is what makes §2.2 cheap to grow.
- Tests for the packaging layer live in `gwyddionpy-converter/tests/`, beside
  the code they cover.
- The valgrind and sanitiser work (§2.20) belongs in separate CI jobs: it
  needs its own build and runs far too slowly to sit with the rest.
