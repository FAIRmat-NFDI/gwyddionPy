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

#: Seconds to let the converter run before giving up. Generous on purpose:
#: it turns a hang into a reported failure, and is not a performance budget.
#: A caller who needs longer passes ``timeout=``.
DEFAULT_TIMEOUT = 300.0

#: Why a raw file might not be claimed by any module. The converter's own
#: message only says that nothing could load it.
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

#: Empty file that GdkPixbuf is pointed at. It lives in the cache directory
#: because that is what it is: created once, reused, safe to delete.
_PIXBUF_CACHE_NAME = "no-pixbuf-loaders.cache"


def _empty_pixbuf_loader_cache() -> str:
    """Return an empty file to use as GdkPixbuf's loader cache.

    Must be a real readable file: the null device makes Windows print a
    GLib assertion, and a missing path triggers an "installation is broken"
    warning. Falls back to the null device on an unwritable cache directory.
    """
    from platformdirs import user_cache_dir

    try:
        directory = Path(user_cache_dir("gwyddionpy"))
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / _PIXBUF_CACHE_NAME
        if not path.is_file():
            path.touch()
        return str(path)
    except OSError:
        return os.devnull


def converter_environment() -> dict:
    """Build the environment the converter subprocess runs in.

    Pins the decimal mark only, so metadata numbers do not follow the
    machine's locale. LC_ALL is spread across the other categories and then
    removed, since it would otherwise outrank LC_NUMERIC.
    """
    env = dict(os.environ)
    lc_all = env.pop("LC_ALL", None)
    if lc_all:
        for category in _OTHER_LOCALE_CATEGORIES:
            env[category] = lc_all
    env["LC_NUMERIC"] = "C"

    # Keep stderr for real diagnostics: GTK and GdkPixbuf otherwise warn on
    # every run. gwyconvert draws nothing, so clearing them changes no output.
    env["GTK_MODULES"] = ""
    env["GDK_PIXBUF_MODULE_FILE"] = _empty_pixbuf_loader_cache()
    return env


def find_converter(explicit: Optional[str] = None) -> str:
    """Resolve the gwyconvert binary: the ``explicit`` argument, then
    ``GWYDDIONPY_CONVERT``, ``PATH``, the installed converter wheel, and
    finally a binary fetched by ``ensure_converter()``.

    The first two raise when they point at no file rather than falling
    through, since a wrong override is worth reporting.
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
        "binary. Full instructions: https://github.com/FAIRmat-NFDI/"
        "gwyddionPy/blob/main/docs/user/how-to.md"
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
        # subprocess.run has already killed and reaped the child by now.
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
