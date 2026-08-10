"""Parse a .gwy file (a serialized GwyContainer) into the gwyddionpy model,
using the pure-Python ``gwyfile`` package.

Layout per channel N: ``/N/data`` (GwyDataField), ``/N/data/title`` (str),
``/N/meta`` (string-valued GwyContainer).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

import gwyfile
import numpy as np

from ._errors import UnsupportedFormatError
from ._model import Channel, GwyData

_DATA_KEY = re.compile(r"^/(?P<num>\d+)/data$")

#: Why a .gwy file will not open. gwyfile reports damage as whichever
#: low-level failure the corruption happens to trigger, and a message like
#: "unpack requires a buffer of 4 bytes" is no help to the caller.
_DAMAGE_CAUSES = (
    "the file is empty",
    "it was truncated before the end of its header",
    "its data block is incomplete",
    "its contents were altered or corrupted in storage or transfer",
    "it is not a Gwyddion container at all, despite the file name",
)


def _damage_report(path: Path, error: Exception) -> str:
    """Explain, in terms a caller can act on, why a .gwy would not open."""
    detail = f"{type(error).__name__}: {error}".strip().rstrip(":").strip()
    try:
        if path.stat().st_size == 0:
            # The one cause that can be identified outright rather than guessed.
            detail = "the file is empty"
    except OSError:
        pass
    return (
        f"{path} could not be read as a .gwy file ({detail}). "
        f"Possible reasons: {'; '.join(_DAMAGE_CAUSES)}."
    )


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
    path = Path(path)
    try:
        return _parse(path)
    except Exception as error:
        # gwyfile raises whatever the damage happens to break — AssertionError,
        # ValueError, struct.error — so all of it becomes one typed error. The
        # whole read is wrapped, not just the load, because gwyfile reshapes a
        # channel lazily and a corrupt shape surfaces only on first access.
        raise UnsupportedFormatError(_damage_report(path, error)) from error


def _parse(path: Path) -> GwyData:
    obj = gwyfile.load(str(path))

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
