"""Reading a file must not depend on the machine's number formatting: a
German-configured machine returns "0,881" where an English one gives
"0.881", and the stored references had a comma baked in until this was
pinned. Pinned twice — in the environment and inside gwyconvert — and only
the second holds on Windows, so these environment-driven tests skip there.
"""
import os
import subprocess
import sys

import pytest

import gwyddionpy
from helpers import content as content_mod
from helpers.requirements import require_specimen
from helpers.specimens import IMAGE_SPECIMENS, SPECIMENS_BY_ID

#: Windows reads its locale from the operating system and ignores LC_ALL
#: and LC_NUMERIC, so no environment set here could change the converter's
#: number formatting. The guarantee still holds there through gwyconvert's
#: own setlocale call; only this way of provoking the failure does not.
LOCALE_IS_TAKEN_FROM_THE_ENVIRONMENT = os.name != "nt"

#: Several, because which ones exist varies between machines and CI images.
COMMA_LOCALE_CANDIDATES = (
    "de_DE.UTF-8", "de_DE.utf8", "fr_FR.UTF-8", "fr_FR.utf8",
    "es_ES.UTF-8", "it_IT.UTF-8", "pt_BR.UTF-8", "nl_NL.UTF-8",
    "de_AT.UTF-8", "fi_FI.UTF-8",
)

JPK = "jpk/sample_0.jpk"


def decimal_point_under(locale_name: str) -> str:
    """What a child process really uses as its decimal separator. Asked
    rather than assumed: an uninstalled locale silently falls back to C, and
    comparing C with itself proves nothing."""
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
            "converter pins LC_NUMERIC in the process itself; see gwyconvert.c."
        )
    if COMMA_LOCALE is None:
        pytest.fail(
            "no comma-decimal locale is installed, so locale independence "
            "cannot be demonstrated on this machine. Install one, e.g. "
            "`sudo locale-gen de_DE.UTF-8 && sudo update-locale`. "
            "Candidates tried: " + ", ".join(COMMA_LOCALE_CANDIDATES)
        )
    return COMMA_LOCALE


@pytest.fixture
def under_locale(monkeypatch, comma_locale):
    """Run the rest of the test with the process configured for commas."""
    monkeypatch.setenv("LC_ALL", comma_locale)
    return comma_locale


def test_the_chosen_locale_really_uses_commas(comma_locale):
    """The control the rest rest on: without it they would be comparing the
    C locale with itself."""
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
    """The value that exposed the problem: a duty cycle of "0,881" cannot be
    read as a number downstream."""
    specimen = SPECIMENS_BY_ID[JPK]
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)

    duty = next(iter(data.channels.values())).meta.get("Duty Cycle")
    assert duty is not None, "the JPK measurement no longer reports a duty cycle"
    assert "," not in duty, f"locale leaked into the metadata: {duty!r}"
    assert float(duty.strip()) == pytest.approx(0.881)


def test_non_ascii_metadata_survives_the_pinned_locale(under_locale):
    """Only numeric formatting is pinned; pinning the whole locale to C
    would put the µ and ° in vendor metadata at risk."""
    specimen = SPECIMENS_BY_ID["jpk/sample_0.jpk-qi-image"]
    require_specimen(specimen)
    data = gwyddionpy.load(specimen.path)

    origin = next(iter(data.channels.values())).meta.get("Origin X", "")
    assert "µ" in origin, f"non-ASCII characters were lost: {origin!r}"
    assert "," not in origin, f"locale leaked into the metadata: {origin!r}"


def test_lc_all_does_not_override_the_pinned_decimal_separator(under_locale):
    """LC_ALL outranks LC_NUMERIC, so setting one without handling the other
    leaves the caller's locale in charge."""
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
