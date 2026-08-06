"""Return GwyData as a plain Python dict, mirroring the HDF5 export layout.

Structure: ``{"source_format": ..., "channels": {<sanitized name>: {"name":
<original name>, "xreal", "yreal", "si_unit_xy", "si_unit_z", "data":
ndarray, "meta": <tree>}}}`` — same fields, same sanitized-name keying
("/" replaced by "_") and the same vendor-metadata grouping as
``export/hdf5.py`` (see ``gwyddionpy._metatree``): nested dicts for
groups, a plain value for a unitless leaf, and ``{"value", "unit"}`` for a
leaf with a parsed unit. No file I/O, no extra dependencies.
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
    # Keys are sanitized the same way the HDF5 export does it, so both
    # exports lay channels out identically (original name kept below).
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
