"""Vendor-metadata hierarchy shared by the HDF5 and dict exports.

Vendor keys encode structure as a group prefix ("2:AmplitudeLimit") or a
path ("Samps/line"), which ``build_tree`` unfolds into a nested tree.
Leaves split "<number> <unit>" unless ``hierarchical=False``; a key landing
on an occupied node falls back to its flat form with a " (n)" suffix.
"""
from __future__ import annotations

import re
from typing import Dict, NamedTuple, Optional, Union

_GROUP_PREFIX = re.compile(r"^(\d+):(.+)$")
# "<number> <unit>" where the unit must not itself start like a number,
# so list-valued entries such as "0.05 0.05" stay whole strings.
_NUMBER_WITH_UNIT = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s+([^\s\d+.-].*)$", re.ASCII)
# Matched before calling int()/float(), which accept more than an instrument
# writes: int("1_000") is 1000 and int("２３") is 23, either of which would
# silently replace the recorded text. https://peps.python.org/pep-0515/
_PLAIN_NUMBER = re.compile(
    r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$", re.ASCII)
# "NaN" and "inf" mean "no reading here", which a consumer wants as a float.
_SPECIAL_NUMBER = re.compile(r"^[+-]?(?:nan|inf|infinity)$", re.IGNORECASE)


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
    if _PLAIN_NUMBER.match(s):
        try:
            return int(s), None
        except ValueError:
            return float(s), None
    if _SPECIAL_NUMBER.match(s):
        return float(s), None
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
    """Unfold flat vendor metadata into the shared group/leaf tree."""
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
