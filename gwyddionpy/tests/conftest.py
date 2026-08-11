"""Fixtures shared across the suite, which needs the gwyconvert from the
installed converter package.

  unit/  built inputs   converter/  finding and running the binary
  data/  vendor files   formats/    reading those files
                        helpers/    registry, schema, fixture builders
"""
import numpy as np
import pytest

from helpers import platforms
from helpers.gwy_builder import make_gwy


def pytest_addoption(parser):
    parser.addoption(
        "--require-platform", action="store", default="", metavar="NAME",
        help=("declare which platform this run is meant to be (linux, macos, "
              "windows). Running anywhere else then stops the run instead of "
              "quietly passing. Also settable as "
              f"{platforms.REQUIRE_ENV_VAR}."),
    )


def declared_platform(config):
    """The platform this run says it is, or None if it did not say."""
    declared = config.getoption("--require-platform") or ""
    try:
        return (platforms.normalize(declared) if declared
                else platforms.required())
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error


def pytest_collection_modifyitems(config, items):
    """Leave the cross-platform tests out unless a platform was declared.

    They only mean something on a known, controlled platform. Each CI leg
    declares itself, so they run there.
    """
    if declared_platform(config) is not None:
        return
    skip = pytest.mark.skip(
        reason=("cross-platform test: pass --require-platform (or set "
                f"{platforms.REQUIRE_ENV_VAR}) to run it")
    )
    for item in items:
        if item.get_closest_marker("platform") is not None:
            item.add_marker(skip)


def pytest_configure(config):
    """Stop immediately if this run is not the platform it claims to be.

    A changed image or a `runs-on` typo produces a green run that tested the
    wrong system, and nothing in the output would show it.
    """
    expected = declared_platform(config)
    if expected is None:
        return

    actual = platforms.current()
    if actual != expected:
        raise pytest.UsageError(
            f"this run was told it is the {expected} leg but it is running on "
            f"{platforms.describe()}. Either the declaration is wrong or the "
            f"job is running on the wrong image; nothing here would have "
            f"tested {expected}."
        )


@pytest.fixture(scope="session")
def required_platform(pytestconfig):
    """The platform this run declared, by either route, so a test never has
    to know whether the option or the environment variable was used."""
    return declared_platform(pytestconfig)


@pytest.fixture
def two_channel_gwy(tmp_path):
    return make_gwy(
        tmp_path / "two_channel.gwy",
        [
            {
                "name": "Height",
                "data": np.arange(12).reshape(3, 4) * 1e-9,
                "xreal": 2e-6,
                "yreal": 1.5e-6,
                "unit_xy": "m",
                "unit_z": "m",
                "meta": {"Scan Rate": "1.0", "Tip": "RTESPA-300"},
            },
            {
                "name": "Phase",
                "data": np.linspace(-90.0, 90.0, 12).reshape(3, 4),
                "xreal": 2e-6,
                "yreal": 1.5e-6,
                "unit_xy": "m",
                "unit_z": "deg",
                "meta": {"Scan Rate": "2.0"},
            },
        ],
    )
