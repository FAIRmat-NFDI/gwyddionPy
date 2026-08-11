"""Export GwyData metadata as JSON. No pixel data, no dependencies.

The layout of ``export/dict.py`` with each channel's ``data`` array replaced
by its ``shape``, so the result is a readable metadata sidecar rather than a
second copy of the image. Derived from ``to_dict()`` output rather than
walking the metadata again, so the two cannot drift apart.

This module is ``gwyddionpy.export.json``; the ``import json`` below is the
standard library, since Python 3 imports absolutely.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from gwyddionpy.export.dict import to_dict


def _encode(node):
    """Replace non-finite floats with string tags, recursively.

    JSON has no literal for NaN or the infinities, and Python's bare
    ``NaN``/``Infinity`` output is not valid JSON that other parsers accept.
    Tagged as strings — the same convention as the test reference files in
    ``tests/helpers/content.py`` — ``float()`` parses every tag back.
    """
    if isinstance(node, dict):
        return {key: _encode(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_encode(item) for item in node]
    if isinstance(node, float) and not math.isfinite(node):
        if math.isnan(node):
            return "NaN"
        return "Infinity" if node > 0 else "-Infinity"
    return node


def _without_pixels(channel: dict) -> dict:
    """One channel's fields, the image swapped for its dimensions.

    Written in place so ``shape`` sits where ``data`` did and the field
    order still matches the dict and HDF5 exports.
    """
    fields = dict(channel)
    fields["data"] = list(np.shape(fields["data"]))
    return {("shape" if key == "data" else key): value
            for key, value in fields.items()}


def to_metadata_dict(data, hierarchical_meta: bool = True) -> dict:
    """The JSON payload as a plain dict: ``to_dict()`` without the arrays."""
    payload = to_dict(data, hierarchical_meta=hierarchical_meta)
    payload["channels"] = {
        key: _without_pixels(channel)
        for key, channel in payload["channels"].items()
    }
    return _encode(payload)


def write(data, path, hierarchical_meta: bool = True, indent: int = 2) -> None:
    """Write the metadata to ``path`` as UTF-8 JSON.

    ``allow_nan=False`` so a non-finite value that escaped ``_encode``
    raises here instead of writing a file no strict parser will read.
    """
    Path(path).write_text(
        json.dumps(
            to_metadata_dict(data, hierarchical_meta=hierarchical_meta),
            indent=indent,
            ensure_ascii=False,   # vendor metadata is full of µ, ° and Å
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )
