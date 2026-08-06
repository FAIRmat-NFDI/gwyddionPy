"""Build real .gwy files with the gwyfile writer.

No mocks: the same library that parses production files parses these, so a
synthetic fixture exercises the identical code path a real file does.
"""
import numpy as np
from gwyfile.objects import GwyContainer, GwyDataField, GwySIUnit


def make_gwy(path, channels):
    """Write a .gwy file. channels: list of dicts with keys
    name, data, xreal, yreal, unit_xy, unit_z, meta (all optional but data)."""
    # Text components get an explicit "s" typecode: gwyfile would otherwise
    # store a one-character string as Gwyddion's char type, which reads back
    # as a number. Real files written by Gwyddion do not have that problem,
    # so neither should a constructed one.
    # The mapping is copied by GwyContainer, so it must be complete up front.
    container = GwyContainer(typecodes={
        f"/{num}/data/title": "s" for num in range(len(channels))
    })
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
            meta = GwyContainer(typecodes={key: "s" for key in spec["meta"]})
            for key, value in spec["meta"].items():
                meta[key] = value
            container[f"/{num}/meta"] = meta
    container.tofile(str(path))
    return path
