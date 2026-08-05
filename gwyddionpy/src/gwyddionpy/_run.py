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

#: Seconds to let the converter run before giving up on it. Deliberately
#: generous: it exists to turn an indefinite hang into a bounded, reported
#: failure, not to police how long a legitimate conversion may take. Large
#: scans are slow, and a caller who needs longer passes ``timeout=``.
DEFAULT_TIMEOUT = 300.0

#: Why a raw file that no module claims usually is not claimed. The
#: converter's own message says only that nothing could load the file, which
#: leaves the caller with nowhere to go next.
_UNREADABLE_CAUSES = (
    "the format is not one Gwyddion can read",
    "the file is empty, truncated, or incomplete",
    "its contents do not match what the file name suggests",
    "it was altered or corrupted in storage or transfer",
)


#: Locale categories other than LC_NUMERIC, in the order POSIX defines them.
_OTHER_LOCALE_CATEGORIES = (
    "LC_CTYPE", "LC_COLLATE", "LC_TIME", "LC_MONETARY", "LC_MESSAGES",
)


def converter_environment() -> dict:
    """The environment the converter subprocess runs in.

    The converter prints numbers the way the machine is configured to print
    them, so the same measurement yields "0,881" on a German-configured
    machine and "0.881" on an English one. Callers read that value as a
    number, so it has to mean the same thing everywhere: the decimal mark is
    pinned here, and nothing else is touched.

    A locale is not one setting but several independent ones:

        LC_NUMERIC  decimal mark, "." or ","     <- the only one to change
        LC_CTYPE    character encoding           <- µm and °C live here
        LC_TIME, LC_COLLATE, LC_MONETARY, LC_MESSAGES

    So not LC_ALL=C, which would set all of them at once and drop LC_CTYPE
    to ASCII, mangling the µm and °C this metadata is full of.

    Setting LC_NUMERIC on its own is not enough either. POSIX ranks LC_ALL
    above the individual categories, so a caller who exported
    LC_ALL=de_DE.UTF-8 would still get commas back. LC_ALL is therefore
    copied into the remaining categories and then removed, which preserves
    every choice the caller made except the decimal mark:

        caller sets  LC_ALL=de_DE.UTF-8
        converter gets  LC_NUMERIC=C            (numbers: "0.881")
                        LC_CTYPE=de_DE.UTF-8    (µm still works)
                        LC_TIME=de_DE.UTF-8     (and the rest unchanged)
    """
    env = dict(os.environ)
    lc_all = env.pop("LC_ALL", None)
    if lc_all:
        for category in _OTHER_LOCALE_CATEGORIES:
            env[category] = lc_all
    env["LC_NUMERIC"] = "C"
    return env


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
    input_path: Path,
    output_path: Path,
    converter: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Optional[str]:
    """Convert ``input_path`` to a .gwy file at ``output_path``.

    Returns the name of the Gwyddion file module that parsed the input, or
    None if the converter did not report one. Gives up after ``timeout``
    seconds (``DEFAULT_TIMEOUT`` when not given).
    """
    binary = find_converter(converter)
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    try:
        proc = subprocess.run(
            [binary, str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            check=False,      # the return code is inspected below
            timeout=timeout,
            env=converter_environment(),
        )
    except subprocess.TimeoutExpired as expired:
        # subprocess.run has already killed the child and reaped it, so
        # there is nothing left running by the time this is raised.
        raise ConversionError(
            f"{BINARY_NAME} did not finish within {timeout:g} s while reading "
            f"{input_path}, and was stopped. Pass a larger timeout= if the "
            "file is genuinely this slow to read."
        ) from expired

    if proc.returncode != 0:
        message = proc.stderr.strip() or f"exit code {proc.returncode}"
        if "cannot load" in message:
            raise UnsupportedFormatError(
                f"{message}\nPossible reasons: "
                f"{'; '.join(_UNREADABLE_CAUSES)}."
            )
        raise ConversionError(message)

    try:
        return json.loads(proc.stdout).get("module") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def query_formats(
    converter: Optional[str] = None, timeout: Optional[float] = None
) -> list:
    """Return the converter's --list-formats output as a list of dicts."""
    binary = find_converter(converter)
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    try:
        proc = subprocess.run(
            [binary, "--list-formats"],
            capture_output=True,
            text=True,
            check=False,      # the return code is inspected below
            timeout=timeout,
            env=converter_environment(),
        )
    except subprocess.TimeoutExpired as expired:
        raise ConversionError(
            f"{BINARY_NAME} did not list its formats within {timeout:g} s, "
            "and was stopped."
        ) from expired

    if proc.returncode != 0:
        raise ConversionError(proc.stderr.strip() or "cannot list formats")
    return json.loads(proc.stdout)
