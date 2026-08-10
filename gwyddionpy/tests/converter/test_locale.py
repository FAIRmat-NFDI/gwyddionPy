"""Reading a file must not depend on how the machine is configured.

Gwyddion formats numeric metadata through the C library, so on a machine set
up for German or French numbers the same measurement comes back with "0,881"
where an English one gives "0.881". Anything downstream that reads those
values as numbers then behaves differently depending on whose laptop it runs
on, which is why the decimal separator is pinned rather than inherited.

context part: this is the classic failure of C code that reaches for strtod
where g_ascii_strtod is meant, and it is not hypothetical here — the metadata
of the JPK measurements really does change with the locale, and the stored
references had a comma baked into them until this was pinned.

Each test states which locale it is running under and checks that the locale
genuinely took effect, so a machine without the locale installed fails loudly
instead of comparing the C locale against itself and passing.

context part: the separator is pinned twice over, and the two are not
interchangeable. converter_environment() sets LC_NUMERIC=C in the
environment it hands the converter, which is a POSIX mechanism; gwyconvert
also pins LC_NUMERIC in the process itself, which is what carries the
guarantee on Windows, where the C runtime ignores the environment. These
tests provoke the failure through the environment and so run only where that
is meaningful.
"""
import os
import subprocess
import sys

import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS, SPECIMENS_BY_ID

#: Whether a locale can be imposed on a child process through the
#: environment at all. This is a POSIX mechanism: the Microsoft C runtime's
#: setlocale(LC_ALL, "") reads the user's OS locale and ignores LC_ALL and
#: LC_NUMERIC, so on Windows no environment this suite can construct changes
#: how the converter formats numbers, and a test that set one would be
#: comparing the default locale against itself.
#:
#: The guarantee itself still holds there, by a different route: gwyconvert
#: pins LC_NUMERIC in the process on start-up, which works the same way on
#: every platform. What cannot be demonstrated on Windows is this suite's
#: way of provoking the failure, not the behaviour being relied on.
LOCALE_IS_TAKEN_FROM_THE_ENVIRONMENT = os.name != "nt"

#: Locales whose decimal separator is a comma. Several are listed because
#: which ones exist varies between machines and CI images.
COMMA_LOCALE_CANDIDATES = (
    "de_DE.UTF-8", "de_DE.utf8", "fr_FR.UTF-8", "fr_FR.utf8",
    "es_ES.UTF-8", "it_IT.UTF-8", "pt_BR.UTF-8", "nl_NL.UTF-8",
    "de_AT.UTF-8", "fi_FI.UTF-8",
)

JPK = "jpk/sample_0.jpk"


def decimal_point_under(locale_name: str) -> str:
    """What a child process actually uses as a decimal separator.

    Asking the operating system rather than assuming: setting a locale that
    is not installed silently falls back to C, and a test that compared the
    C locale with itself would pass while proving nothing.
    """
    result = subprocess.run(
        [sys.executable, "-c",
         "import locale; locale.setlocale(locale.LC_ALL, ''); "
         "print(locale.localeconv()['decimal_point'])"],
        capture_output=True, text=True, check=False,
        env={**os.environ, "LC_ALL": locale_name},
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def find_comma_locale():
    if not LOCALE_IS_TAKEN_FROM_THE_ENVIRONMENT:
        return None
    for name in COMMA_LOCALE_CANDIDATES:
        if decimal_point_under(name) == ",":
            return name
    return None


COMMA_LOCALE = find_comma_locale()


@pytest.fixture(scope="module")
def comma_locale():
    if not LOCALE_IS_TAKEN_FROM_THE_ENVIRONMENT:
        pytest.skip(
            "this platform does not take its locale from the environment, so "
            "the caller's number formatting cannot be varied from here. The "
            "converter pins LC_NUMERIC in the process itself, which is what "
            "holds on this platform; see gwyconvert.c."
        )
    if COMMA_LOCALE is None:
        pytest.fail(
            "no comma-decimal locale is installed, so locale independence "
            "cannot be demonstrated on this machine. Install one, e.g. "
            "`sudo locale-gen de_DE.UTF-8 && sudo update-locale`, or on a "
            "Debian/Ubuntu CI image add `locales` and run "
            "`locale-gen de_DE.UTF-8`. Candidates tried: "
            + ", ".join(COMMA_LOCALE_CANDIDATES)
        )
    return COMMA_LOCALE


@pytest.fixture
def under_locale(monkeypatch, comma_locale):
    """Run the rest of the test with the process configured for commas."""
    monkeypatch.setenv("LC_ALL", comma_locale)
    return comma_locale


def test_the_chosen_locale_really_uses_commas(comma_locale):
    """The control the other tests depend on: if this ever stops holding,
    everything below would be comparing the C locale against itself."""
    assert decimal_point_under(comma_locale) == ","


def test_the_c_locale_really_uses_dots():
    assert decimal_point_under("C") == "."


@pytest.mark.parametrize("specimen", IMAGE_SPECIMENS, ids=lambda s: s.id)
def test_content_is_the_same_under_a_comma_locale(specimen, under_locale,
                                                  monkeypatch):
    """Everything a caller can observe stays put when the locale changes."""
    require_specimen(specimen)
    with_commas = content_mod.extract_content(gwyddionpy.load(specimen.path))

    monkeypatch.setenv("LC_ALL", "C")
    with_dots = content_mod.extract_content(gwyddionpy.load(specimen.path))

    assert with_commas["channel_names"] == with_dots["channel_names"]
    for name, expected in with_dots["channels"].items():
        actual = with_commas["channels"][name]
        assert content_mod.float_diffs(
            {"xreal": expected["xreal"], "yreal": expected["yreal"]},
            {"xreal": actual["xreal"], "yreal": actual["yreal"]},
            where=f"{name}.",
        ) == []
        assert content_mod.float_diffs(expected["pixels"], actual["pixels"],
                                       where=f"{name} @ ") == []
        assert content_mod.meta_diffs(expected["meta"], actual["meta"]) == []


def test_numeric_metadata_keeps_a_dot_under_a_comma_locale(under_locale):
    """The value that exposed the problem: a JPK duty cycle reported as
    "0,881" cannot be read as a number by anything downstream."""
    specimen = SPECIMENS_BY_ID[JPK]
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)

    duty = next(iter(data.channels.values())).meta.get("Duty Cycle")
    assert duty is not None, "the JPK measurement no longer reports a duty cycle"
    assert "," not in duty, f"locale leaked into the metadata: {duty!r}"
    assert float(duty.strip()) == pytest.approx(0.881)


def test_non_ascii_metadata_survives_the_pinned_locale(under_locale):
    """context part: only numeric formatting is pinned. Pinning the whole
    locale to C would put characters like µ and ° at risk, and the vendor
    metadata is full of them."""
    specimen = SPECIMENS_BY_ID["jpk/sample_0.jpk-qi-image"]
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)

    origin = next(iter(data.channels.values())).meta.get("Origin X", "")
    assert "µ" in origin, f"non-ASCII characters were lost: {origin!r}"
    assert "," not in origin, f"locale leaked into the metadata: {origin!r}"


def test_lc_all_does_not_override_the_pinned_decimal_separator(under_locale):
    """LC_ALL outranks LC_NUMERIC in POSIX, so setting the one without
    handling the other leaves the caller's locale still in charge."""
    from gwyddionpy._run import converter_environment

    env = converter_environment()
    assert env["LC_NUMERIC"] == "C"
    assert "LC_ALL" not in env, "LC_ALL would take precedence over LC_NUMERIC"


def test_the_callers_other_locale_choices_are_left_alone(under_locale):
    """Pinning numbers must not quietly reset everything else."""
    from gwyddionpy._run import converter_environment

    env = converter_environment()
    assert env["LC_CTYPE"] == under_locale
    assert env["LC_TIME"] == under_locale


def test_listing_formats_is_unaffected_by_the_locale(under_locale, monkeypatch):
    under_comma = gwyddionpy.list_formats()
    monkeypatch.setenv("LC_ALL", "C")
    under_c = gwyddionpy.list_formats()
    assert under_comma == under_c
