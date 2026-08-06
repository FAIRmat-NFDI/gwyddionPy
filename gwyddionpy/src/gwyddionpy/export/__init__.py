"""Export backends consuming GwyData. Reached through GwyData.to_*()."""
from __future__ import annotations

from typing import Dict, Iterable


def channel_keys(names: Iterable[str]) -> Dict[str, str]:
    """Map channel names onto the keys the exports store them under.

    "/" is HDF5's path separator and cannot appear in a group name, so it
    becomes "_". That substitution can land two different channels on the
    same key — "A/B" and "A_B" — which silently lost one of them in the dict
    export and aborted the HDF5 one part-way through. A clash now gets the
    same " (n)" suffix already used for duplicate channel titles and
    duplicate metadata keys, so every channel survives under a distinct key.

    Shared by both exports so they keep the identical layout their docstrings
    promise.
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
