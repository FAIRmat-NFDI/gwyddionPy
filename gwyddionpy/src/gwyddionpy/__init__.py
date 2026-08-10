"""Read any scanning probe microscopy (SPM) raw file that Gwyddion supports.

Pipeline: raw file -> gwyconvert subprocess -> .gwy -> gwyfile -> GwyData.
A .gwy input skips the converter. Everything in ``__all__`` is public;
underscore-prefixed names are internal. Gwyddion: http://gwyddion.net
"""
from __future__ import annotations

import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from ._errors import (
    ConversionError,
    ConverterFetchError,
    ConverterNotFoundError,
    GwyddionPyError,
    UnsupportedFormatError,
)
from ._fetch_converter import ensure_converter
from ._model import Channel, GwyData
from ._parse import parse_gwy
from ._run import query_formats, run_converter

try:
    __version__ = version("gwyddionpy")
except PackageNotFoundError:  # pragma: no cover — not installed, e.g. running from a source checkout
    __version__ = "unknown"

__all__ = [
    "load",
    "list_formats",
    "parse_gwy",
    "ensure_converter",
    "GwyData",
    "Channel",
    "GwyddionPyError",
    "ConverterNotFoundError",
    "ConversionError",
    "UnsupportedFormatError",
    "ConverterFetchError",
]


def load(
    path, *, converter: Optional[str] = None, timeout: Optional[float] = None
) -> GwyData:
    """Load a raw file of any Gwyddion-supported format.

    ``converter`` is a path to gwyconvert, otherwise discovered by
    ``_run.find_converter()``; a .gwy input needs none. ``timeout`` caps the
    converter's run time, defaulting to ``_run.DEFAULT_TIMEOUT``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() == ".gwy":
        return parse_gwy(path)

    # Removed on the way out, whether the conversion succeeds or not.
    with tempfile.TemporaryDirectory(prefix="gwyddionpy-") as tmpdir:
        converted = Path(tmpdir, "converted.gwy")
        module = run_converter(path, converted, converter=converter,
                               timeout=timeout)
        data = parse_gwy(converted)
    data.source_format = module
    return data


def list_formats(
    converter: Optional[str] = None, timeout: Optional[float] = None
) -> list:
    """List the file formats the converter supports (dicts with name,
    description, can_load, can_save, detectable)."""
    return query_formats(converter, timeout=timeout)
