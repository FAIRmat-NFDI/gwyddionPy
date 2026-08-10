"""Return GwyData as a plain Python dict. No file I/O, no dependencies.

``{"source_format": ..., "channels": {<sanitized name>: {"name", "xreal",
"yreal", "si_unit_xy", "si_unit_z", "data", "meta"}}}``, where a metadata
leaf is a plain value or ``{"value", "unit"}``. Mirrors ``export/hdf5.py``
field for field, so change either and check the other.
"""
from __future__ import annotations

from .._metatree import MetaLeaf, build_tree
from . import channel_keys


def _tree_to_plain(tree):
    plain = {}
    for name, node in tree.items():
        if isinstance(node, MetaLeaf):
            plain[name] = (node.value if node.unit is None
                            else {"value": node.value, "unit": node.unit})
        else:
            plain[name] = _tree_to_plain(node)
    return plain


def to_dict(data, hierarchical_meta: bool = True) -> dict:
    # Sanitized the same way as in the HDF5 export, so both lay channels out
    # identically. The original name is kept in the "name" field below.
    keys = channel_keys(data.channels)
    return {
        "source_format": data.source_format,
        "channels": {
            keys[name]: {
                "name": name,
                "xreal": channel.xreal,
                "yreal": channel.yreal,
                "si_unit_xy": channel.si_unit_xy,
                "si_unit_z": channel.si_unit_z,
                "data": channel.data,
                "meta": _tree_to_plain(
                    build_tree(channel.meta, hierarchical_meta)
                ),
            }
            for name, channel in data.channels.items()
        },
    }
