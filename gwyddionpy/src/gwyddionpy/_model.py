"""Data model returned by gwyddionpy: GwyData holding named Channels."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np


@dataclass
class Channel:
    """One image channel: physical values plus dimensions and units."""

    name: str
    data: np.ndarray            # shape (rows, cols), physical values
    xreal: float = 1.0          # physical width, in si_unit_xy
    yreal: float = 1.0          # physical height, in si_unit_xy
    si_unit_xy: str = ""        # e.g. "m"
    si_unit_z: str = ""         # e.g. "m", "V", "deg"
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class GwyData:
    """Parsed content of one raw file."""

    channels: Dict[str, Channel]
    source_format: Optional[str] = None   # Gwyddion module that parsed the file

    @property
    def metadata(self) -> Dict[str, str]:
        """Union of per-channel metadata; on key collisions the first
        channel (in file order) wins. Per-channel values stay in
        ``channel.meta``."""
        merged: Dict[str, str] = {}
        for channel in self.channels.values():
            for key, value in channel.meta.items():
                merged.setdefault(key, value)
        return merged

    def to_hdf5(self, path, **kwargs) -> None:
        """Write channels + metadata to a plain HDF5 file (needs h5py).

        Vendor metadata keys are unfolded into nested groups by default;
        pass ``hierarchical_meta=False`` for flat attributes."""
        from .export.hdf5 import write

        write(self, path, **kwargs)

    def to_gwy(self, path) -> None:
        """Write a Gwyddion-native .gwy file (opens in the Gwyddion GUI)."""
        from .export.gwy import write

        write(self, path)

    def to_dict(self, hierarchical_meta: bool = True) -> dict:
        """Return channels + metadata as a plain Python dict (no file I/O),
        structurally mirroring ``to_hdf5`` — same channel fields, same
        sanitized-name keying, same vendor-metadata grouping. Matches the
        shape pynxtools-spm's reader adapter is expected to consume (see
        docs/EXTENDING.md)."""
        from .export.dict import to_dict

        return to_dict(self, hierarchical_meta=hierarchical_meta)
