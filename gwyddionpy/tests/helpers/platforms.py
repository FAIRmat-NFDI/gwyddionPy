"""Which platform the suite runs on, and which one it was told to expect.

Differences are asserted rather than skipped past, since a leg that skips
its own tests looks like one that passes them. A run told which platform it
is meant to be errors if it finds itself anywhere else.
"""
from __future__ import annotations

import os
import platform
import sys

#: Set by CI to declare which leg this is. A mismatch stops the run.
REQUIRE_ENV_VAR = "GWYDDIONPY_REQUIRE_PLATFORM"

LINUX, MACOS, WINDOWS = "linux", "macos", "windows"
KNOWN = (LINUX, MACOS, WINDOWS)

_FROM_SYS_PLATFORM = {"linux": LINUX, "darwin": MACOS, "win32": WINDOWS}

#: Aliases people actually type, so a CI file saying "macos-15" or "ubuntu"
#: does not fail for the wrong reason.
_ALIASES = {
    "linux": LINUX, "ubuntu": LINUX, "manylinux": LINUX, "musllinux": LINUX,
    "macos": MACOS, "darwin": MACOS, "osx": MACOS, "mac": MACOS,
    "windows": WINDOWS, "win": WINDOWS, "win32": WINDOWS, "win_amd64": WINDOWS,
}


def current() -> str:
    """The platform this process is running on."""
    name = _FROM_SYS_PLATFORM.get(sys.platform)
    if name is None:
        raise RuntimeError(
            f"unsupported platform {sys.platform!r}: the converter is built "
            f"for {', '.join(KNOWN)} only"
        )
    return name


def normalize(label: str) -> str:
    """Turn a CI-ish platform label into one of the three names."""
    cleaned = label.strip().lower().replace("_", "-")
    for prefix, name in _ALIASES.items():
        if cleaned == prefix or cleaned.startswith(prefix + "-"):
            return name
    raise ValueError(
        f"cannot tell which platform {label!r} means; expected one of "
        f"{', '.join(KNOWN)}"
    )


def required() -> str | None:
    """The platform this run was told to be, if it was told."""
    declared = os.environ.get(REQUIRE_ENV_VAR, "").strip()
    return normalize(declared) if declared else None


def describe() -> str:
    return (f"{current()} ({sys.platform}, {platform.machine()}, "
            f"python {platform.python_version()})")


#: What each platform can do. A missing capability is recorded here, not a
#: reason to skip: tests assert presence and absence alike.
CAPABILITIES = {
    LINUX:   {"wrapper_script": True,  "peak_memory": True,  "posix_paths": True},
    MACOS:   {"wrapper_script": True,  "peak_memory": True,  "posix_paths": True},
    WINDOWS: {"wrapper_script": False, "peak_memory": False, "posix_paths": False},
}


def supports(capability: str) -> bool:
    try:
        return CAPABILITIES[current()][capability]
    except KeyError as error:
        raise KeyError(
            f"unknown capability {capability!r}; known: "
            f"{sorted(CAPABILITIES[current()])}"
        ) from error
