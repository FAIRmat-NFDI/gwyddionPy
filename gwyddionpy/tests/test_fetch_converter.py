"""Tests for the D6 converter fetch helper.

Uses a real local HTTP server (not a mock) serving a fake release tarball,
so the actual download/checksum/extract code path in _fetch_converter.py
runs end-to-end — just against localhost instead of github.com. No network
access needed; nothing here touches the real ~/.cache/gwyddionpy.
"""
import functools
import hashlib
import http.server
import platform
import tarfile
import threading

import pytest

from gwyddionpy._errors import ConverterFetchError
from gwyddionpy._fetch_converter import (
    BASE_URL_ENV_VAR,
    _asset_name,
    _platform_tag,
    cached_converter_path,
    ensure_converter,
)

BINARY_NAME = "gwyconvert.exe" if platform.system() == "Windows" else "gwyconvert"


@pytest.fixture
def fake_cache_dir(tmp_path, monkeypatch):
    """Redirect the fetch helper's cache dir into tmp_path."""
    cache_root = tmp_path / "cache"
    monkeypatch.setattr(
        "gwyddionpy._fetch_converter.user_cache_dir", lambda name: str(cache_root)
    )
    return cache_root / "converter"


@pytest.fixture
def http_server(tmp_path):
    serve_dir = tmp_path / "serve"
    serve_dir.mkdir()
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(serve_dir)
    )
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield serve_dir, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def _build_release_assets(serve_dir, asset_name, corrupt_checksum=False):
    payload = serve_dir / "_payload"
    payload.mkdir()
    binary_path = payload / BINARY_NAME
    binary_path.write_bytes(b"#!/bin/sh\necho fake gwyconvert\n")
    binary_path.chmod(0o644)  # deliberately not executable yet

    tarball_path = serve_dir / asset_name
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(binary_path, arcname=BINARY_NAME)

    checksum = hashlib.sha256(tarball_path.read_bytes()).hexdigest()
    if corrupt_checksum:
        checksum = "0" * 64
    (serve_dir / f"{asset_name}.sha256").write_text(f"{checksum}  {asset_name}\n")
    return tarball_path


def test_ensure_converter_downloads_verifies_and_extracts(
    http_server, fake_cache_dir, monkeypatch
):
    serve_dir, base_url = http_server
    asset = _asset_name()
    _build_release_assets(serve_dir, asset)
    monkeypatch.setenv(BASE_URL_ENV_VAR, base_url)

    path = ensure_converter()

    assert path == fake_cache_dir / BINARY_NAME
    assert path.is_file()
    assert path.stat().st_mode & 0o111  # made executable by ensure_converter
    assert cached_converter_path() == path


def test_ensure_converter_returns_cached_copy_without_network(
    fake_cache_dir, monkeypatch
):
    # No BASE_URL_ENV_VAR set at all: success here proves the cached path
    # short-circuits before any network code runs.
    monkeypatch.delenv(BASE_URL_ENV_VAR, raising=False)
    fake_cache_dir.mkdir(parents=True)
    cached_binary = fake_cache_dir / BINARY_NAME
    cached_binary.write_bytes(b"already here")
    cached_binary.chmod(0o755)

    path = ensure_converter()

    assert path == cached_binary
    assert path.read_bytes() == b"already here"


def test_ensure_converter_rejects_checksum_mismatch(
    http_server, fake_cache_dir, monkeypatch
):
    serve_dir, base_url = http_server
    asset = _asset_name()
    _build_release_assets(serve_dir, asset, corrupt_checksum=True)
    monkeypatch.setenv(BASE_URL_ENV_VAR, base_url)

    with pytest.raises(ConverterFetchError, match="checksum mismatch"):
        ensure_converter()

    # checksum verification runs before extraction, so nothing was unpacked
    assert cached_converter_path() is None


def test_unsupported_platform_raises(monkeypatch):
    monkeypatch.setattr("gwyddionpy._fetch_converter.platform.system", lambda: "Plan9")
    with pytest.raises(ConverterFetchError, match="no prebuilt gwyconvert"):
        _platform_tag()
