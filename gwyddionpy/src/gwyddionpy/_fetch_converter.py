"""Download a prebuilt gwyconvert binary from a GitHub Release.

**Deprecated, and kept only for the transition.** Installing the wheel —
``pip install "gwyddionpy[converter]"`` — is the supported way to get a
converter, and this module is scheduled for removal in a future release.
It still works, and is still tested, so that anyone relying on it is not
stranded mid-version; nothing new should be built on it.

An alternative to ``pip install "gwyddionpy[converter]"`` for anyone who
wants the binary without adding a GPL package to their environment. The
tarball is built by .github/workflows/build-converter.yml's `linux` job and
attached to the release as ``gwyconvert-<os>-<arch>.tar.gz``, with a
sibling ``.sha256``; releases carry the same tag as the Python package, so
version resolution needs nothing but the installed version. Only
linux-x86_64 is published this way — the other platforms ship as wheels.

User-triggered, always: this runs only from an explicit
``gwyddionpy.ensure_converter()`` call or the ``gwyddionpy-fetch-converter``
console script — never on import, never from a pip install hook. It touches
no package manager and needs no privileges; it is an HTTPS download,
checksum check and extract.

The module itself is plain Apache-2.0 Python containing no GPL code; what
it downloads is the GPL-2.0-or-later artifact.
"""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import warnings
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from platformdirs import user_cache_dir

from ._errors import ConverterFetchError

#: Shown once per call rather than at import, so merely having gwyddionpy
#: installed does not nag anyone who never touches this path.
_DEPRECATION = (
    "gwyddionpy.ensure_converter() and the gwyddionpy-fetch-converter "
    "command are deprecated and will be removed in a future release. "
    "Install the converter as a wheel instead: "
    'pip install "gwyddionpy[converter]".'
)

GITHUB_REPO = "FAIRmat-NFDI/gwyddionPy"
# Override for testing (tests/test_fetch_converter.py points it at a local
# HTTP server) or for a self-hosted mirror.
BASE_URL_ENV_VAR = "GWYDDIONPY_CONVERTER_BASE_URL"

_SYSTEM_NAMES = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}
_MACHINE_NAMES = {
    "x86_64": "x86_64", "amd64": "x86_64", "aarch64": "arm64", "arm64": "arm64",
}


def _platform_tag() -> str:
    """Return this machine's ``<os>-<arch>`` tag, e.g. "linux-x86_64"."""
    system = _SYSTEM_NAMES.get(platform.system())
    machine = _MACHINE_NAMES.get(platform.machine().lower())
    if system is None or machine is None:
        raise ConverterFetchError(
            f"no prebuilt gwyconvert for {platform.system()}/{platform.machine()} "
            "— install `gwyddionpy[converter]` or build it yourself "
            "(docs/user/how-to.md)"
        )
    return f"{system}-{machine}"


def _asset_name() -> str:
    """The release asset for this machine. Must match the name
    ci/build-linux.sh gives the tarball it uploads."""
    return f"gwyconvert-{_platform_tag()}.tar.gz"


def _release_tag() -> str:
    """The GitHub Release tag to fetch from: the installed package's own
    version, or "latest" for dev and editable installs, whose versions
    correspond to no release.

    Release tags are "v"-prefixed (v0.0.1) while setuptools-scm versions are
    not (0.0.1), so the "v" is added back here. publish.yml strips it in the
    other direction when pinning the converter.
    """
    try:
        installed = version("gwyddionpy")
    except PackageNotFoundError:
        return "latest"
    if "dev" in installed or "+" in installed:
        return "latest"
    return f"v{installed}"


def _base_url() -> str:
    override = os.environ.get(BASE_URL_ENV_VAR)
    if override:
        return override.rstrip("/")
    tag = _release_tag()
    path = "releases/latest/download" if tag == "latest" else f"releases/download/{tag}"
    return f"https://github.com/{GITHUB_REPO}/{path}"


def converter_cache_dir() -> Path:
    """Where a fetched gwyconvert is cached (platform-appropriate)."""
    return Path(user_cache_dir("gwyddionpy")) / "converter"


def _cached_binary_name() -> str:
    """What the binary is called inside the release tarball, and so in the
    cache once extracted: Windows executables carry .exe, nothing else does.
    Must match the name ci/bundle-{linux,macos,windows}.sh gives it."""
    return "gwyconvert.exe" if platform.system() == "Windows" else "gwyconvert"


def cached_converter_path() -> Optional[Path]:
    """The cached gwyconvert binary's path, if one was already fetched."""
    candidate = converter_cache_dir() / _cached_binary_name()
    return candidate if candidate.is_file() else None


def _download(url: str, dest: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=30) as response, open(dest, "wb") as f:
            shutil.copyfileobj(response, f)
    except urllib.error.HTTPError as exc:
        raise ConverterFetchError(f"download failed ({exc.code}) for {url}") from exc
    except urllib.error.URLError as exc:
        raise ConverterFetchError(f"download failed for {url}: {exc.reason}") from exc


def _download_text(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ConverterFetchError(f"download failed ({exc.code}) for {url}") from exc
    except urllib.error.URLError as exc:
        raise ConverterFetchError(f"download failed for {url}: {exc.reason}") from exc


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract, rejecting members that would escape ``dest`` or are links.

    Plain ``extractall()`` writes both as-is, which is the CVE-2007-4559
    path-traversal class. Python 3.12's ``filter="data"`` does this for us,
    but the package supports 3.9, so the check is written out here.
    https://docs.python.org/3/library/tarfile.html#extraction-filters
    """
    dest = dest.resolve()
    for member in tar.getmembers():
        member_path = (dest / member.name).resolve()
        if dest not in member_path.parents and member_path != dest:
            raise ConverterFetchError(f"unsafe path in archive: {member.name!r}")
        if member.issym() or member.islnk():
            raise ConverterFetchError(f"unsupported link entry in archive: {member.name!r}")
    tar.extractall(dest)  # noqa: S202 — members vetted above


def ensure_converter(*, force: bool = False) -> Path:
    """Download the prebuilt gwyconvert for this platform, verify its
    checksum, cache it locally, and return its path.

    Returns an already-cached binary immediately unless ``force=True``.
    Call this explicitly (or run ``gwyddionpy-fetch-converter``): it never
    runs on import or as a side effect of ``pip install``.

    .. deprecated::
        Install ``gwyddionpy[converter]`` instead. This will be removed in
        a future release.
    """
    warnings.warn(_DEPRECATION, DeprecationWarning, stacklevel=2)

    cached = cached_converter_path()
    if cached is not None and not force:
        return cached

    asset = _asset_name()
    base = _base_url()
    tarball_url = f"{base}/{asset}"
    checksum_url = f"{tarball_url}.sha256"

    cache_dir = converter_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="gwyddionpy-fetch-") as tmp:
        tarball_path = Path(tmp) / asset
        _download(tarball_url, tarball_path)

        expected = _download_text(checksum_url).split()[0].strip().lower()
        actual = _sha256_of(tarball_path)
        if actual != expected:
            raise ConverterFetchError(
                f"checksum mismatch for {asset}: expected {expected}, got {actual}"
            )

        with tarfile.open(tarball_path) as tar:
            _safe_extract(tar, cache_dir)

    result = cached_converter_path()
    if result is None:
        raise ConverterFetchError(
            f"gwyconvert not found in {asset} after extraction to {cache_dir}"
        )
    result.chmod(result.stat().st_mode | 0o111)
    return result


def _main(argv: Optional[list] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="gwyddionpy-fetch-converter",
        description="Download the prebuilt gwyconvert binary for this platform "
        "(GPL-2.0-or-later, fetched separately from the gwyddionpy package). "
        "Deprecated: install gwyddionpy[converter] instead; this command will "
        "be removed in a future release.",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-download even if already cached"
    )
    args = parser.parse_args(argv)

    # DeprecationWarning is silent by default in a console script, so the
    # notice is printed where the person running it will actually see it.
    print(f"warning: {_DEPRECATION}", file=sys.stderr)

    try:
        path = ensure_converter(force=args.force)
    except ConverterFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(path)


if __name__ == "__main__":
    _main()
