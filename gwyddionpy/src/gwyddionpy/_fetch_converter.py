"""Download a prebuilt gwyconvert binary from a GitHub Release.

**Deprecated**, and to be removed: installing ``gwyddionpy[converter]`` is
the supported route. Kept for anyone wanting the binary without a GPL
package in their environment (linux-x86_64 only). Runs only from
``ensure_converter()`` or ``gwyddionpy-fetch-converter``, never on import.
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

from gwyddionpy._errors import ConverterFetchError

#: Shown once per call rather than at import, so having gwyddionpy
#: installed does not nag anyone who never uses this route.
_DEPRECATION = (
    "gwyddionpy.ensure_converter() and the gwyddionpy-fetch-converter "
    "command are deprecated and will be removed in a future release. "
    "Install the converter as a wheel instead: "
    'pip install "gwyddionpy[converter]".'
)

GITHUB_REPO = "FAIRmat-NFDI/gwyddionPy"
# Points the download somewhere else: a self-hosted mirror, or a local
# server standing in for the release host during tests.
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
            "— install `gwyddionpy[converter]`, or build it yourself: "
            "https://github.com/FAIRmat-NFDI/gwyddionPy/blob/main/docs/user/"
            "how-to.md"
        )
    return f"{system}-{machine}"


def _asset_name() -> str:
    """The release asset for this machine. Must match the name
    ci/build-linux.sh gives the tarball it uploads."""
    return f"gwyconvert-{_platform_tag()}.tar.gz"


def _release_tag() -> str:
    """The release tag to fetch from: the installed version, or "latest" for
    development installs, which match no release. Tags carry a leading "v"
    while setuptools-scm versions do not, so it is added back here.
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
    """What the binary is called in the tarball, and so in the cache.

    Must match the name ci/bundle-{linux,macos,windows}.sh gives it.
    """
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
    """Extract, rejecting members that are links or escape ``dest``.

    Plain ``extractall()`` writes both as given (CVE-2007-4559). Python
    3.12's ``filter="data"`` would do this, but the package supports 3.9.
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
    """Download gwyconvert for this platform, verify it, cache it, and
    return its path. Returns an already-cached binary unless ``force=True``.

    .. deprecated:: Install ``gwyddionpy[converter]`` instead.
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

    # DeprecationWarning is invisible in a console script by default, so the
    # notice is printed where the person running it will see it.
    print(f"warning: {_DEPRECATION}", file=sys.stderr)

    try:
        path = ensure_converter(force=args.force)
    except ConverterFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(path)


if __name__ == "__main__":
    _main()
