"""Export backends for GwyData. Reached through GwyData.to_*()."""
from __future__ import annotations

from typing import Dict, Iterable


def channel_keys(names: Iterable[str]) -> Dict[str, str]:
    """Map channel names onto the keys the exports store them under.

    "/" cannot appear in an HDF5 group name and becomes "_", which can land
    two channels on one key ("A/B" and "A_B"); a clash gets a " (n)" suffix
    so every channel keeps a distinct key. Shared by both exports.
    """
    keys: Dict[str, str] = {}
    taken = set()
    for name in names:
        base = name.replace("/", "_")
        key = base
        suffix = 2
        while key in taken:
            key = f"{base} ({suffix})"
            suffix += 1
        taken.add(key)
        keys[name] = key
    return keys
