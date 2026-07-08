"""Plain-HDF5 export of GwyData.

Layout: one group per channel under /channels, image as a compressed
dataset ``data``, physical dimensions/units as group attributes, vendor
metadata under the ``meta`` subgroup. NeXus output is not done here — that
goes through pynxtools-spm (docs/EXTENDING.md).

Metadata hierarchy: vendor keys often encode structure — a numeric group
prefix ("2:AmplitudeLimit") and/or "/"-separated paths ("Samps/line", as in
Bruker headers). With ``hierarchical_meta=True`` (default) those become
nested HDF5 groups with the leaf stored as an attribute; if two keys
collapse onto the same node, the later one keeps its original flat key.
"""
from __future__ import annotations

import re

_GROUP_PREFIX = re.compile(r"^(\d+):(.+)$")


def _meta_path(key):
    """Split a vendor metadata key into (group path, attribute name)."""
    parts = key.split("/")
    prefixed = _GROUP_PREFIX.match(parts[0])
    if prefixed:
        parts = [f"group {prefixed.group(1)}", prefixed.group(2), *parts[1:]]
    parts = [p for p in (p.strip() for p in parts) if p] or [key]
    return parts[:-1], parts[-1]


def _write_meta(parent, meta, hierarchical):
    group = parent.create_group("meta")
    if not hierarchical:
        for key, value in meta.items():
            group.attrs[key] = value
        return
    for key, value in meta.items():
        path, attr = _meta_path(key)
        target = group
        for part in path:
            target = target.require_group(part)
        if attr in target.attrs:  # two keys collapsing onto one node
            target.attrs[key] = value
        else:
            target.attrs[attr] = value


def write(data, path, compression: str = "gzip",
          hierarchical_meta: bool = True) -> None:
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "HDF5 export needs h5py: pip install 'gwyddionpy[hdf5]'"
        ) from exc

    with h5py.File(path, "w") as f:
        f.attrs["source_format"] = data.source_format or ""
        root = f.create_group("channels")
        for name, ch in data.channels.items():
            # "/" is the HDF5 path separator and cannot appear in a name.
            group = root.create_group(name.replace("/", "_"))
            group.attrs["name"] = name
            group.attrs["xreal"] = ch.xreal
            group.attrs["yreal"] = ch.yreal
            group.attrs["si_unit_xy"] = ch.si_unit_xy
            group.attrs["si_unit_z"] = ch.si_unit_z
            group.create_dataset("data", data=ch.data, compression=compression)
            _write_meta(group, ch.meta, hierarchical_meta)
