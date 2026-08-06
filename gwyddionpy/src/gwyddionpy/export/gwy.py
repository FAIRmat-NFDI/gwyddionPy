"""Export GwyData back to a Gwyddion-native .gwy file.

The result opens directly in the Gwyddion GUI and round-trips through
``gwyddionpy.load()``. Written with the pure-Python ``gwyfile`` package —
no converter binary involved.
"""
from __future__ import annotations


def write(data, path) -> None:
    from gwyfile.objects import GwyContainer, GwyDataField, GwySIUnit

    # Every text component is written with an explicit "s" (string) typecode.
    # gwyfile otherwise infers the type from the value, and infers Gwyddion's
    # single-character "c" type for any string of length one — which reads
    # back as that character's numeric code, turning a metadata value of "0"
    # into 48 and a channel titled "Z" into 90. Vendor headers are full of
    # one-character values, so the inference has to be overridden rather than
    # relied on.
    # GwyContainer copies the mapping it is given, so it has to be complete
    # before the container exists — adding entries afterwards has no effect.
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
        # Make the channel visible when the file is opened in the GUI.
        container[f"/{num}/data/visible"] = True
        if channel.meta:
            meta = GwyContainer(
                typecodes={key: "s" for key in channel.meta}
            )
            for key, value in channel.meta.items():
                meta[key] = value
            container[f"/{num}/meta"] = meta

    container.tofile(str(path))
