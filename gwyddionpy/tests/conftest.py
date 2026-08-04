"""Root fixtures and the collection-time skip policy.

Layout (see FullTestPlan.md §5):
  unit/       pure Python, no converter binary, no sample data — always runs
  converter/  needs a built gwyconvert
  formats/    needs gwyconvert *and* the real vendor files in test-data/
  helpers/    the framework itself (importable via pyproject's `pythonpath`)
  golden/     JSON reference content, one file per sample
"""
import numpy as np
import pytest

from helpers.gwy_builder import make_gwy
from helpers.requirements import HAVE_CONVERTER, STRICT


def pytest_collection_modifyitems(config, items):
    """Auto-skip anything marked `converter` when no binary is available, so
    individual modules don't each repeat a skipif. In strict mode nothing is
    skipped — the tests run and fail, which is the point.

    Checks the marker via get_closest_marker rather than `in item.keywords`:
    keywords also contain the enclosing directory names, so the latter would
    match every test under converter/ — including the discovery tests that
    deliberately run *without* a binary.
    """
    if HAVE_CONVERTER or STRICT:
        return
    marker = pytest.mark.skip(reason="gwyconvert not available")
    for item in items:
        if item.get_closest_marker("converter") is not None:
            item.add_marker(marker)


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
