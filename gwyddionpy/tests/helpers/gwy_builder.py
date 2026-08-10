"""Build real .gwy files with the gwyfile writer.

No mocks. The library that parses production files parses these too, so a
built fixture exercises the same code path a real file does.
"""
import numpy as np
from gwyfile.objects import GwyContainer, GwyDataField, GwySIUnit


def make_gwy(path, channels):
    """Write a .gwy file.

    ``channels`` is a list of dicts with the keys name, data, xreal, yreal,
    unit_xy, unit_z and meta. All are optional except data.
    """
    # Text gets an explicit "s" typecode, as in gwyddionpy.export.gwy: left
    # to infer, gwyfile stores a one-character string as Gwyddion's char
    # type and it reads back as a number. GwyContainer copies the mapping,
    # so it must be complete before the container exists.
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
