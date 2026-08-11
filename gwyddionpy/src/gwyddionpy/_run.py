"""Locating and running the gwyconvert helper binary.

gwyconvert is a separate GPL-2.0-or-later executable; this module only ever
launches it as a subprocess, which is what keeps gwyddionpy Apache-2.0.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ._errors import ConversionError, ConverterNotFoundError, UnsupportedFormatError

ENV_VAR = "GWYDDIONPY_CONVERT"
BINARY_NAME = "gwyconvert"


def find_converter(explicit: Optional[str] = None) -> str:
    """Resolve the gwyconvert binary, in this order:

    1. the ``explicit`` argument,
    2. the ``GWYDDIONPY_CONVERT`` environment variable,
    3. ``gwyconvert`` on ``PATH``,
    4. the ``gwyddionpy-converter`` wheel, if installed,
    5. a binary previously downloaded by ``gwyddionpy.ensure_converter()``.

    The two explicit overrides (1 and 2) raise when set but pointing at no
    file, rather than falling through — a wrong override is a mistake worth
    reporting, not something to silently paper over with another candidate.
    """
    if explicit is not None:
        if Path(explicit).is_file():
            return str(explicit)
        raise ConverterNotFoundError(f"converter not found at {explicit!r}")

    env = os.environ.get(ENV_VAR)
    if env:
        if Path(env).is_file():
            return env
        raise ConverterNotFoundError(
            f"{ENV_VAR} points to a nonexistent file: {env!r}"
        )

    found = shutil.which(BINARY_NAME)
    if found:
        return found

    try:
        from gwyddionpy_converter import binary_path

        return str(binary_path())
    except (ImportError, FileNotFoundError):
        pass

    from ._fetch_converter import cached_converter_path

    cached = cached_converter_path()
    if cached is not None:
        return str(cached)

    raise ConverterNotFoundError(
        f"cannot find {BINARY_NAME!r}: install it with "
        f"`pip install 'gwyddionpy[converter]'`, set {ENV_VAR}, add it to "
        "PATH, or run `gwyddionpy-fetch-converter` to download a prebuilt "
        "binary. See docs/user/how-to.md for the full instructions."
    )


def run_converter(
    input_path: Path, output_path: Path, converter: Optional[str] = None
) -> Optional[str]:
    """Convert ``input_path`` to a .gwy file at ``output_path``.

    Returns the name of the Gwyddion file module that parsed the input, or
    None if the converter did not report one.
    """
    binary = find_converter(converter)
    proc = subprocess.run(
        [binary, str(input_path), str(output_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or f"exit code {proc.returncode}"
        if "cannot load" in message:
            raise UnsupportedFormatError(message)
        raise ConversionError(message)

    try:
        return json.loads(proc.stdout).get("module") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def query_formats(converter: Optional[str] = None) -> list:
    """Return the converter's --list-formats output as a list of dicts."""
    binary = find_converter(converter)
    proc = subprocess.run(
        [binary, "--list-formats"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise ConversionError(proc.stderr.strip() or "cannot list formats")
    return json.loads(proc.stdout)
