"""Which platform the suite is running on, and which one it was told to expect.

The converter is built for Linux, macOS and Windows, and the three differ in
ways the tests care about: how the binary is launched, what a path looks like,
whether the system can report a child process's peak memory. Those differences
are worth asserting, not skipping past.

Skipping is what makes a cross-platform suite untrustworthy. A macOS leg that
quietly skips every macOS-specific test is indistinguishable from one that
passes, and a leg misconfigured to run on the wrong image looks fine either
way. So tests here are written to run everywhere and assert what is true of
the platform they find themselves on, and a run can additionally be told which
platform it is supposed to be — in which case being anywhere else is an error
rather than a shrug.
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


#: What each platform is expected to be able to do. Absence of a capability is
#: a property of the platform, recorded here, rather than a reason to skip:
#: a test asserts the capability where it should exist and asserts the
#: documented substitute where it should not.
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
