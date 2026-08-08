"""Prebuilt gwyconvert binary bundle (GPL-2.0-or-later).

Ships the platform-specific gwyconvert bundle as wheel data, so
``pip install "gwyddionpy[converter]"`` needs no separate download or build
step. One wheel per platform: Linux x86_64, macOS arm64/x86_64, Windows
x86_64.

This is a separate distribution rather than part of gwyddionpy because
gwyconvert links Gwyddion and is therefore GPL-2.0-or-later, while
gwyddionpy stays Apache-2.0 — it only ever runs this binary as a
subprocess. Keeping the GPL artifact behind an opt-in extra is what
preserves that boundary. See the repository README for the full reasoning.
"""
from __future__ import annotations

from pathlib import Path

_BIN_DIR = Path(__file__).parent / "bin"

# Unix bundles ship a wrapper shell script named `gwyconvert`, which sets
# GWYDDION_LIBDIR (and, on Linux, LD_LIBRARY_PATH) before exec-ing
# lib/gwyconvert.real. Windows needs no such indirection — DLLs beside the
# .exe are found by the loader — so it ships `gwyconvert.exe` directly.
# These names come from ci/bundle-{linux,macos,windows}.sh; rename them
# there and this tuple must follow.
_CANDIDATES = ("gwyconvert", "gwyconvert.exe")


def binary_path() -> Path:
    """Return the path to the bundled gwyconvert executable or wrapper."""
    for name in _CANDIDATES:
        path = _BIN_DIR / name
        if path.is_file():
            return path
    tried = ", ".join(str(_BIN_DIR / name) for name in _CANDIDATES)
    raise FileNotFoundError(
        f"gwyconvert binary not found (tried: {tried}) - this platform's "
        "gwyddionpy-converter wheel may not have been built correctly"
    )
