"""Export GwyData back to a Gwyddion-native .gwy file.

The result opens in the Gwyddion application and round-trips through
``gwyddionpy.load()``. Written with the pure-Python ``gwyfile`` package, so
no converter binary is involved.
"""
from __future__ import annotations


def write(data, path) -> None:
    from gwyfile.objects import GwyContainer, GwyDataField, GwySIUnit

    # Text gets an explicit "s" typecode: left to infer, gwyfile stores a
    # one-character string as Gwyddion's "c" type, so "0" reads back as 48.
    # The mapping is copied, so it must be complete before the container.
    container = GwyContainer(typecodes={
        f"/{num}/data/title": "s" for num in range(len(data.channels))
    })
    for num, channel in enumerate(data.channels.values()):
        container[f"/{num}/data"] = GwyDataField(
            channel.data.astype("f8"),
            xreal=channel.xreal,
            yreal=channel.yreal,
            si_unit_xy=(
                GwySIUnit(unitstr=channel.si_unit_xy)
                if channel.si_unit_xy else None
            ),
            si_unit_z=(
                GwySIUnit(unitstr=channel.si_unit_z)
                if channel.si_unit_z else None
            ),
        )
        container[f"/{num}/data/title"] = channel.name
        # Show the channel when the file is opened in Gwyddion.
        container[f"/{num}/data/visible"] = True
        if channel.meta:
            meta = GwyContainer(
                typecodes={key: "s" for key in channel.meta}
            )
            for key, value in channel.meta.items():
                meta[key] = value
            container[f"/{num}/meta"] = meta

    container.tofile(str(path))
