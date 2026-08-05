"""gwyddionpy — read any Gwyddion-supported SPM raw file into NumPy.

Pipeline: raw file -> gwyconvert subprocess -> .gwy -> gwyfile -> GwyData.
Native .gwy inputs skip the converter and are parsed directly.

The public surface is everything in ``__all__``; names prefixed with an
underscore are internal and may change without notice.
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
    """Load a raw SPM file of any Gwyddion-supported format.

    ``converter`` is an explicit path to gwyconvert; when omitted, it is
    discovered by ``_run.find_converter()``. A .gwy input is read directly
    and needs no converter at all. ``timeout`` caps how long the converter
    may run, in seconds; the default is ``gwyddionpy._run.DEFAULT_TIMEOUT``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() == ".gwy":
        return parse_gwy(path)

    # The temporary directory is removed on the way out whether the
    # conversion succeeds, fails or times out.
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
