"""What a test needs from its environment, and what happens when it is absent.

Centralized so the policy is one decision rather than a skipif repeated in
every module — and so it can be flipped to strict mode in CI.
"""
import os

import pytest

from gwyddionpy._errors import ConverterNotFoundError
from gwyddionpy._run import find_converter

try:
    find_converter()
    HAVE_CONVERTER = True
except ConverterNotFoundError:
    HAVE_CONVERTER = False

#: Turns "skipped because the environment lacks X" into a hard failure.
#: A suite that silently skips its way to green is the failure mode this
#: guards against: CI sets this, so missing sample data or an unbuilt
#: converter can never masquerade as passing tests.
REQUIRE_ENV_VAR = "GWY_REQUIRE_CONVERTER"
STRICT = os.environ.get(REQUIRE_ENV_VAR, "") not in ("", "0")


def unavailable(reason: str):
    """Skip — or fail, when the suite is running in strict mode."""
    if STRICT:
        pytest.fail(f"{reason} (and {REQUIRE_ENV_VAR} is set)")
    pytest.skip(reason)


def require_converter():
    if not HAVE_CONVERTER:
        unavailable("gwyconvert not available")


def require_sample(sample):
    """Require a registry sample's raw data file to be present."""
    require_converter()
    if not sample.exists():
        unavailable(f"sample file missing: {sample.path} (see test-data/README.md)")


def require_golden(sample):
    """Require a committed golden reference for a sample.

    A sample with no golden yet is a tracked gap, not an error: a new vendor
    file lands in the registry before anyone has captured its reference.
    """
    require_sample(sample)
    if not sample.golden_path.is_file():
        unavailable(
            f"no golden reference for {sample.filename}; generate it with "
            f"`python gwyddionpy/tests/make_golden.py {sample.filename}`"
        )
