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
        """Union of per-channel metadata. On a key clash the first channel
        in file order wins; per-channel values stay in ``channel.meta``."""
        merged: Dict[str, str] = {}
        for channel in self.channels.values():
            for key, value in channel.meta.items():
                merged.setdefault(key, value)
        return merged

    def to_hdf5(self, path, **kwargs) -> None:
        """Write channels and metadata to a plain HDF5 file. Needs h5py.

        Metadata keys unfold into nested groups by default. Pass
        ``hierarchical_meta=False`` for flat attributes instead.
        """
        from gwyddionpy.export.hdf5 import write

        write(self, path, **kwargs)

    def to_gwy(self, path) -> None:
        """Write a Gwyddion-native .gwy file, which opens in Gwyddion."""
        from gwyddionpy.export.gwy import write

        write(self, path)

    def to_json(self, path, **kwargs) -> None:
        """Write channel metadata to a JSON file. Carries no pixel data.

        The layout of ``to_dict``, with each channel's ``data`` array
        replaced by its ``shape``. Metadata keys unfold into nested objects
        by default; pass ``hierarchical_meta=False`` for the flat vendor
        keys instead.
        """
        from gwyddionpy.export.json import write

        write(self, path, **kwargs)

    def to_dict(self, hierarchical_meta: bool = True) -> dict:
        """Return channels and metadata as a plain dict, with no file I/O.

        Structurally mirrors ``to_hdf5``. Downstream readers such as
        pynxtools-spm consume this shape, so keep the two in step.
        """
        from gwyddionpy.export.dict import to_dict

        return to_dict(self, hierarchical_meta=hierarchical_meta)
