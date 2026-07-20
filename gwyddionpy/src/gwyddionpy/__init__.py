"""gwyddionpy — read any Gwyddion-supported SPM raw file into NumPy.

Pipeline: raw file -> gwyconvert subprocess -> .gwy -> gwyfile -> GwyData.
Native .gwy inputs are parsed directly, no converter needed.
"""
from __future__ import annotations

import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from ._errors import (
    ConversionError,
    ConverterNotFoundError,
    GwyddionPyError,
    UnsupportedFormatError,
)
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
    "GwyData",
    "Channel",
    "GwyddionPyError",
    "ConverterNotFoundError",
    "ConversionError",
    "UnsupportedFormatError",
]


def load(path, *, converter: Optional[str] = None) -> GwyData:
    """Load a raw SPM file of any Gwyddion-supported format.

    ``converter`` optionally overrides gwyconvert discovery (otherwise the
    GWYDDIONPY_CONVERT environment variable and PATH are searched).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() == ".gwy":
        return parse_gwy(path)

    with tempfile.TemporaryDirectory(prefix="gwyddionpy-") as tmpdir:
        converted = Path(tmpdir, "converted.gwy")
        module = run_converter(path, converted, converter=converter)
        data = parse_gwy(converted)
    data.source_format = module
    return data


def list_formats(converter: Optional[str] = None) -> list:
    """List the file formats the converter supports (dicts with name,
    description, can_load, can_save, detectable)."""
    return query_formats(converter)
