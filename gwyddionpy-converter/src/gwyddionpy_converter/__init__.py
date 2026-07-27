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


def binary_path() -> Path:
    """Return the path to the bundled gwyconvert wrapper script."""
    path = _BIN_DIR / "gwyconvert"
    if not path.is_file():
        raise FileNotFoundError(
            f"gwyconvert binary not found at {path} - this platform's "
            "gwyddionpy-converter wheel may not have been built correctly"
        )
    return path
