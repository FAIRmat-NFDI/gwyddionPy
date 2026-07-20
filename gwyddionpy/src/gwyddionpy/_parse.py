"""Parsing a .gwy file (serialized GwyContainer) into the gwyddionpy model.

Relies on the pure-Python ``gwyfile`` package. Container layout, as written
by Gwyddion: ``/N/data`` (GwyDataField), ``/N/data/title`` (str),
``/N/meta`` (string-valued GwyContainer), for channel numbers N.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

import gwyfile
import numpy as np

from ._model import Channel, GwyData

_DATA_KEY = re.compile(r"^/(?P<num>\d+)/data$")


def _unit_string(datafield, key: str) -> str:
    unit = datafield.get(key)
    if unit is None:
        return ""
    return unit.get("unitstr", "")


def _decode_meta(container) -> Dict[str, str]:
    if container is None:
        return {}
    return {str(k): str(v) for k, v in container.items()}


def _unique_name(name: str, taken) -> str:
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


def parse_gwy(path) -> GwyData:
    """Parse a .gwy file into GwyData (channels as NumPy + metadata)."""
    obj = gwyfile.load(str(Path(path)))

    numbers = sorted(
        int(m.group("num")) for k in obj if (m := _DATA_KEY.match(k))
    )
    channels: Dict[str, Channel] = {}
    for num in numbers:
        datafield = obj[f"/{num}/data"]
        title = str(obj.get(f"/{num}/data/title", f"Channel {num}"))
        name = _unique_name(title, channels)
        channels[name] = Channel(
            name=name,
            data=np.asarray(datafield.data),
            xreal=float(datafield.get("xreal", 1.0)),
            yreal=float(datafield.get("yreal", 1.0)),
            si_unit_xy=_unit_string(datafield, "si_unit_xy"),
            si_unit_z=_unit_string(datafield, "si_unit_z"),
            meta=_decode_meta(obj.get(f"/{num}/meta")),
        )

    return GwyData(channels=channels)
