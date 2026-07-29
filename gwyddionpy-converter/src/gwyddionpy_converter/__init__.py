"""Prebuilt gwyconvert binary bundle (GPL-2.0-or-later).

Ships the platform-specific gwyconvert bundle built in
FAIRmat-NFDI/gwyddionPy's build-converter.yml (Rocky Linux 8, glibc 2.28
floor) as wheel data, so `pip install "gwyddionpy[converter]"` needs no
separate download step. See license_discussion.md in the source repo for
why this lives in its own GPL package rather than inside gwyddionpy itself
(the subprocess boundary is what keeps gwyddionpy Apache-2.0).
"""
from __future__ import annotations

from pathlib import Path

_BIN_DIR = Path(__file__).parent / "bin"

# Unix bundles ship a wrapper shell script named `gwyconvert` (it sets
# GWYDDION_LIBDIR/LD_LIBRARY_PATH before exec-ing lib/gwyconvert.real);
# Windows has no such indirection — DLLs beside the .exe are found
# automatically — so it ships `gwyconvert.exe` directly.
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
