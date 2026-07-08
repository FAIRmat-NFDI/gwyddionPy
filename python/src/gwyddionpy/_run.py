"""Locating and running the gwyconvert helper binary."""
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
    """Resolve the gwyconvert binary: explicit argument, then the
    GWYDDIONPY_CONVERT environment variable, then PATH."""
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

    raise ConverterNotFoundError(
        f"cannot find {BINARY_NAME!r}: set {ENV_VAR} or add it to PATH "
        "(build instructions: gwyddionpy/docs/BUILD.md)"
    )


def run_converter(
    input_path: Path, output_path: Path, converter: Optional[str] = None
) -> Optional[str]:
    """Convert input_path to a .gwy file at output_path.

    Returns the name of the Gwyddion module that parsed the file.
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
