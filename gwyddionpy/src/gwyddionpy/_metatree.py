"""Vendor-metadata hierarchy shared by the hdf5 and dict exports.

Vendor keys often encode structure — a numeric group prefix
("2:AmplitudeLimit") and/or "/"-separated paths ("Samps/line", as in
Bruker headers). ``build_tree`` unfolds those into a nested tree so every
export format that wants a hierarchical layout builds it the same way
instead of re-deriving the grouping/collision rules. Leaves keep a
"<number> <unit>" split ("0 mV" -> value 0, unit "mV") when
``hierarchical=True``; ``hierarchical=False`` returns a flat map of raw
values (no splitting), mirroring a flat-attributes layout.

Keys that collapse onto an already-occupied tree node fall back to their
original flat key ("/" replaced by "_") at the tree root; a further
collision there gets a " (n)" suffix.
"""
from __future__ import annotations

import re
from typing import Dict, NamedTuple, Optional, Union

_GROUP_PREFIX = re.compile(r"^(\d+):(.+)$")
# "<number> <unit>" where the unit must not itself start like a number,
# so list-valued entries such as "0.05 0.05" stay whole strings.
_NUMBER_WITH_UNIT = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s+([^\s\d+.-].*)$")


class MetaLeaf(NamedTuple):
    """One metadata entry: its parsed value plus an optional unit string."""

    value: object
    unit: Optional[str]


MetaTree = Dict[str, Union["MetaTree", MetaLeaf]]


def split_value(value):
    """Parse a vendor value string into (stored value, unit or None)."""
    if not isinstance(value, str):
        return value, None
    s = value.strip()
    for cast in (int, float):
        try:
            return cast(s), None
        except ValueError:
            pass
    m = _NUMBER_WITH_UNIT.match(s)
    if m:
        number, unit = m.groups()
        try:
            return int(number), unit
        except ValueError:
            return float(number), unit
    return value, None


def _meta_path(key):
    """Split a vendor metadata key into (group path, leaf name)."""
    parts = key.split("/")
    prefixed = _GROUP_PREFIX.match(parts[0])
    if prefixed:
        parts = [f"group {prefixed.group(1)}", prefixed.group(2), *parts[1:]]
    parts = [p for p in (p.strip() for p in parts) if p] or [key]
    return parts[:-1], parts[-1]


def _place_leaf(target, name, value):
    if name in target:  # keep both entries: suffix like duplicate channels
        n = 2
        while f"{name} ({n})" in target:
            n += 1
        name = f"{name} ({n})"
    stored, unit = split_value(value)
    target[name] = MetaLeaf(stored, unit)


def build_tree(meta: Dict[str, str], hierarchical: bool = True) -> MetaTree:
    """Unfold flat vendor metadata into the group/leaf tree shared by every
    export that wants a hierarchical layout."""
    if not hierarchical:
        return {key: MetaLeaf(value, None) for key, value in meta.items()}

    root: MetaTree = {}
    for key, value in meta.items():
        path, field = _meta_path(key)
        target = root
        fallback = False
        for part in path:
            nxt = target.get(part)
            if nxt is None:
                nxt = target[part] = {}
            elif not isinstance(nxt, dict):
                fallback = True
                break
            target = nxt
        if fallback:  # a leaf already occupies a path component
            target, field = root, key.replace("/", "_")
        if field in target:  # the node is already occupied by another entry
            target, field = root, key.replace("/", "_")
        _place_leaf(target, field, value)
    return root
