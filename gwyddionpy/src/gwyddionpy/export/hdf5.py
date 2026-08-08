"""Plain-HDF5 export of GwyData.

Layout: one group per channel under /channels, image as a compressed
dataset ``data``, physical dimensions/units as group attributes, vendor
metadata under the ``meta`` subgroup. The grouping and value/unit-splitting
rules live in ``gwyddionpy._metatree``, shared with the dict export so the
two stay structurally identical — change one and check the other. This is
plain HDF5, not NeXus; NeXus output is pynxtools-spm's job.

With ``hierarchical_meta=True`` (default) vendor metadata keys are
unfolded into nested HDF5 groups and each entry is stored as a scalar
*dataset* (so it is visible in viewer trees such as H5Web); values of the
form "<number> <unit>" have the number stored as the dataset value and the
unit string put in a ``unit`` attribute on the dataset.

With ``hierarchical_meta=False`` every entry stays a raw-string attribute on
the flat ``meta`` group — much more compact, no value/unit splitting.
"""
from __future__ import annotations

from .._metatree import MetaLeaf, build_tree


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
        for name, ch in data.channels.items():
            # "/" is the HDF5 path separator and cannot appear in a name.
            group = root.create_group(name.replace("/", "_"))
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
