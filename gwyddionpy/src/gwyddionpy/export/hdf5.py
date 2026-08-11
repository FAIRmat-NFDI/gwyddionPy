"""Plain-HDF5 export of GwyData. Not NeXus; that is pynxtools-spm's job.

One group per channel under /channels: the image as a compressed ``data``
dataset, dimensions and units as attributes, vendor metadata under ``meta``.
``hierarchical_meta=True`` (default) unfolds metadata into nested groups of
scalar datasets; ``False`` leaves flat string attributes. Mirrors
``export/dict.py``, so change either and check the other.
"""
from __future__ import annotations

from gwyddionpy._metatree import MetaLeaf, build_tree
from gwyddionpy.export import channel_keys


def _write_tree(group, tree):
    for name, node in tree.items():
        if isinstance(node, MetaLeaf):
            dset = group.create_dataset(name, data=node.value)
            if node.unit is not None:
                dset.attrs["unit"] = node.unit
        else:
            _write_tree(group.create_group(name), node)


def _write_flat(group, tree):
    for name, leaf in tree.items():
        group.attrs[name] = leaf.value


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
        # "/" cannot appear in a group name. channel_keys also keeps two
        # channels that sanitize alike apart.
        keys = channel_keys(data.channels)
        for name, ch in data.channels.items():
            group = root.create_group(keys[name])
            group.attrs["name"] = name
            group.attrs["xreal"] = ch.xreal
            group.attrs["yreal"] = ch.yreal
            group.attrs["si_unit_xy"] = ch.si_unit_xy
            group.attrs["si_unit_z"] = ch.si_unit_z
            group.create_dataset("data", data=ch.data, compression=compression)
            tree = build_tree(ch.meta, hierarchical_meta)
            meta_group = group.create_group("meta")
            if hierarchical_meta:
                _write_tree(meta_group, tree)
            else:
                _write_flat(meta_group, tree)
