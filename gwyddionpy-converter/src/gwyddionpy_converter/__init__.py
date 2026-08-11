"""Prebuilt gwyconvert binary bundle (GPL-2.0-or-later), shipped as wheel
data so ``pip install "gwyddionpy[converter]"`` needs no build step.

A separate distribution because gwyconvert links Gwyddion and is therefore
GPL, while gwyddionpy stays Apache-2.0 by only running it as a subprocess.
https://github.com/FAIRmat-NFDI/gwyddionPy#license
"""
from __future__ import annotations

from pathlib import Path

_BIN_DIR = Path(__file__).parent / "bin"

# Linux and macOS bundles ship a wrapper shell script named `gwyconvert`,
# which sets the library paths before exec-ing lib/gwyconvert.real. Windows
# needs no wrapper, because the loader finds dynamic-link libraries (DLLs)
# sitting beside the .exe, so it ships `gwyconvert.exe` directly.
#
# These names come from ci/bundle-{linux,macos,windows}.sh. Rename them
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
