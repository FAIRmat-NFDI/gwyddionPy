"""Checking that a test has the raw file it needs before it runs.

The files live in tests/data/ and are committed with the tests, so this is a
check rather than a fetch: nothing is downloaded and no test reaches outside
the repository. A missing or altered file is a failure, never a skip — these
tests exist to read real vendor files, so a run that passes without them would
be reporting nothing.
"""
import hashlib
from pathlib import Path

import pytest


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require_specimen(specimen):
    """Ensure the raw file is present and is the one the reference describes."""
    if not specimen.exists():
        pytest.fail(
            f"{specimen.relpath} is missing from tests/data/. Restore it from "
            "version control; the specimen files are committed with the tests."
        )
    if specimen.sha256:
        actual = checksum(specimen.path)
        assert actual == specimen.sha256, (
            f"{specimen.relpath} does not match its recorded checksum — the "
            f"file on disk is not the one the reference was captured from.\n"
            f"  expected {specimen.sha256}\n  got      {actual}"
        )


def require_golden(specimen):
    """Ensure both the raw file and its reference are available."""
    require_specimen(specimen)
    if not specimen.golden_path.is_file():
        pytest.fail(
            f"no reference for {specimen.relpath}. Capture one with "
            f"`python gwyddionpy/tests/make_golden.py {specimen.relpath}`, "
            "then review the result before committing it."
        )
