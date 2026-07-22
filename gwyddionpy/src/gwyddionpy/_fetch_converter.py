"""Download a prebuilt gwyconvert binary (user-triggered only, D6).

gwyconvert is GPL-2.0-or-later (it links Gwyddion); this module ships as
plain Apache-2.0 Python containing no GPL code. It never runs on its own —
not from a pip install hook, not on import — only when the user explicitly
calls ``gwyddionpy.ensure_converter()`` or runs the console script
``gwyddionpy-fetch-converter``. It never touches apt/dnf/brew/sudo; it only
downloads an already-built binary tarball over HTTPS from a GitHub Release.

Release tarballs are tagged the same as the Python package release (see
CONTEXT.md D6/OQ7) and named ``gwyconvert-<platform>-<arch>.tar.gz``, each
with a sibling ``.sha256`` checksum file.
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
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from platformdirs import user_cache_dir

from ._errors import ConverterFetchError

GITHUB_REPO = "FAIRmat-NFDI/gwyddionPy"
# Override for testing (a local HTTP server) or a self-hosted mirror.
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
            "— build it yourself instead (docs/BUILD.md)"
        )
    return f"{system}-{machine}"


def _asset_name() -> str:
    return f"gwyconvert-{_platform_tag()}.tar.gz"


def _release_tag() -> str:
    """The GitHub Release tag to fetch from: the installed package's own
    version, or "latest" for dev/editable installs with no matching tag."""
    try:
        installed = version("gwyddionpy")
    except PackageNotFoundError:
        return "latest"
    if "dev" in installed or "+" in installed:
        return "latest"
    return installed


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


def cached_converter_path() -> Optional[Path]:
    """The cached gwyconvert binary's path, if one was already fetched."""
    binary_name = "gwyconvert.exe" if platform.system() == "Windows" else "gwyconvert"
    candidate = converter_cache_dir() / binary_name
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
    """Extract, rejecting members that would escape dest or are links —
    tarfile.extractall() follows/writes them as-is otherwise (CVE-2007-4559
    class path-traversal), and this needs to run on Python 3.9, before the
    3.12 ``filter="data"`` guard existed."""
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

    User-triggered only — call this explicitly (or run the
    ``gwyddionpy-fetch-converter`` console script); it never runs on
    import or as a side effect of ``pip install``. Returns the cached
    binary immediately if one is already present, unless ``force=True``.
    """
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
        "(GPL-2.0-or-later, fetched separately from the gwyddionpy package).",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-download even if already cached"
    )
    args = parser.parse_args(argv)

    try:
        path = ensure_converter(force=args.force)
    except ConverterFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(path)


if __name__ == "__main__":
    _main()
