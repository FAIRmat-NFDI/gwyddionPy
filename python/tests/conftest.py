"""Shared fixtures. Fixtures build real .gwy files with the gwyfile writer —
no mocks: the same library that parses production files parses these."""
import numpy as np
import pytest
from gwyfile.objects import GwyContainer, GwyDataField, GwySIUnit


def make_gwy(path, channels):
    """Write a .gwy file. channels: list of dicts with keys
    name, data, xreal, yreal, unit_xy, unit_z, meta (all optional but data)."""
    container = GwyContainer()
    for num, spec in enumerate(channels):
        field = GwyDataField(
            np.asarray(spec["data"], dtype="f8"),
            xreal=spec.get("xreal", 1.0),
            yreal=spec.get("yreal", 1.0),
            si_unit_xy=(
                GwySIUnit(unitstr=spec["unit_xy"]) if "unit_xy" in spec else None
            ),
            si_unit_z=(
                GwySIUnit(unitstr=spec["unit_z"]) if "unit_z" in spec else None
            ),
        )
        container[f"/{num}/data"] = field
        if "name" in spec:
            container[f"/{num}/data/title"] = spec["name"]
        if "meta" in spec:
            meta = GwyContainer()
            for key, value in spec["meta"].items():
                meta[key] = value
            container[f"/{num}/meta"] = meta
    container.tofile(str(path))
    return path


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
