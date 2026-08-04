"""Fixtures shared across the suite.

Directory layout:
  unit/       parsing, model and export behaviour on purpose-built inputs
  converter/  locating and running the gwyconvert binary
  formats/    reading the real vendor files under data/
  helpers/    registry, reference schema and fixture builders
  data/       raw measurement files and their golden references, by vendor

Every test expects a working gwyconvert, which comes from the
gwyddionpy-converter package installed alongside gwyddionpy.
"""
import numpy as np
import pytest

from helpers.gwy_builder import make_gwy


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
