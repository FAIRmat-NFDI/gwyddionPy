"""Downloading a prebuilt converter from a release.

warning: this route is deprecated. Installing the wheel is the supported way
to get a converter, and this module is scheduled for removal. It is tested
anyway, and tested properly, because it still ships: code that is on its way
out is exactly the code nobody notices breaking, and a download-and-execute
path that breaks quietly is worse than most.

Nothing here reaches the network. The module takes its base URL from
GWYDDIONPY_CONVERTER_BASE_URL, so a local server standing in for the release
host exercises the real download, checksum and extraction code rather than a
stand-in for it.
"""
import hashlib
import http.server
import os
import tarfile
import threading
import warnings
from pathlib import Path

import pytest

from gwyddionpy import _fetch_converter as fetch
from gwyddionpy._errors import ConverterFetchError


# --------------------------------------------------------------------------
# A stand-in release host
# --------------------------------------------------------------------------
@pytest.fixture
def release_host(tmp_path, monkeypatch):
    """Serve a directory over HTTP and point the module at it."""
    served = tmp_path / "released"
    served.mkdir()

    handler = http.server.SimpleHTTPRequestHandler

    class Quiet(handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(served), **kwargs)

        def log_message(self, *args):        # keep the test output readable
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(fetch.BASE_URL_ENV_VAR,
                       f"http://127.0.0.1:{server.server_port}")
    try:
        yield served
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Redirect the converter cache somewhere disposable."""
    directory = tmp_path / "cache"
    monkeypatch.setattr(fetch, "converter_cache_dir", lambda: directory)
    return directory


def publish(served, body=b"#!/bin/sh\necho stub\n", name=None, checksum=None):
    """Put a tarball and its checksum where the module will look for them.

    The member is named the way a real release tarball names it — with .exe
    on Windows — taken from the module itself so the stand-in release and
    the code that looks for the extracted binary cannot drift apart.
    """
    asset = name or fetch._asset_name()
    member = fetch._cached_binary_name()
    staging = served / "staging"
    staging.mkdir(exist_ok=True)
    binary = staging / member
    binary.write_bytes(body)

    tarball = served / asset
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(binary, arcname=member)

    digest = checksum or hashlib.sha256(tarball.read_bytes()).hexdigest()
    (served / f"{asset}.sha256").write_text(f"{digest}  {asset}\n")
    return tarball


# --------------------------------------------------------------------------
# Deprecation
# --------------------------------------------------------------------------
def test_fetching_warns_that_the_route_is_going_away(release_host, cache):
    publish(release_host)
    with pytest.warns(DeprecationWarning, match="deprecated"):
        fetch.ensure_converter()


def test_the_warning_names_the_supported_route():
    assert "gwyddionpy[converter]" in fetch._DEPRECATION


def test_the_command_says_so_where_it_will_be_seen(release_host, cache, capsys):
    """context part: a DeprecationWarning is invisible in a console script by
    default, so the notice is also printed to stderr."""
    publish(release_host)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fetch._main([])
    assert "deprecated" in capsys.readouterr().err.lower()


# --------------------------------------------------------------------------
# Working out what to fetch
# --------------------------------------------------------------------------
@pytest.mark.parametrize("system,machine,expected", [
    ("Linux", "x86_64", "linux-x86_64"),
    ("Linux", "aarch64", "linux-arm64"),
    ("Darwin", "arm64", "macos-arm64"),
    ("Darwin", "x86_64", "macos-x86_64"),
    ("Windows", "AMD64", "windows-x86_64"),
])
def test_the_platform_tag_matches_the_published_asset_names(
    system, machine, expected, monkeypatch
):
    monkeypatch.setattr(fetch.platform, "system", lambda: system)
    monkeypatch.setattr(fetch.platform, "machine", lambda: machine)
    assert fetch._platform_tag() == expected
    assert fetch._asset_name() == f"gwyconvert-{expected}.tar.gz"


def test_an_unsupported_platform_says_so_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(fetch.platform, "system", lambda: "SunOS")
    monkeypatch.setattr(fetch.platform, "machine", lambda: "sparc")
    with pytest.raises(ConverterFetchError, match="no prebuilt"):
        fetch._platform_tag()


@pytest.mark.parametrize("installed,expected", [
    ("0.0.9", "v0.0.9"),
    ("1.2.3", "v1.2.3"),
    ("0.0.9.dev3", "latest"),
    ("0.0.9+local", "latest"),
])
def test_the_release_tag_follows_the_installed_version(installed, expected,
                                                       monkeypatch):
    """context part: release tags carry a leading v while the package version
    does not, and a development install has no matching release at all."""
    monkeypatch.setattr(fetch, "version", lambda _: installed)
    assert fetch._release_tag() == expected


def test_an_uninstalled_package_falls_back_to_the_latest_release(monkeypatch):
    def missing(_):
        raise fetch.PackageNotFoundError

    monkeypatch.setattr(fetch, "version", missing)
    assert fetch._release_tag() == "latest"


def test_the_base_url_can_be_pointed_elsewhere(monkeypatch):
    monkeypatch.setenv(fetch.BASE_URL_ENV_VAR, "https://example.invalid/files/")
    assert fetch._base_url() == "https://example.invalid/files"


def test_the_default_base_url_is_the_project_release_page(monkeypatch):
    monkeypatch.delenv(fetch.BASE_URL_ENV_VAR, raising=False)
    monkeypatch.setattr(fetch, "version", lambda _: "0.0.9")
    url = fetch._base_url()
    assert fetch.GITHUB_REPO in url
    assert url.endswith("releases/download/v0.0.9")


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def test_a_fetched_converter_lands_in_the_cache_and_is_executable(release_host,
                                                                  cache):
    publish(release_host)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = fetch.ensure_converter()

    assert result.is_file()
    assert cache in result.parents
    assert os.access(result, os.X_OK), "a downloaded converter must be runnable"


def test_an_already_fetched_converter_is_not_downloaded_again(release_host,
                                                              cache):
    publish(release_host)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        first = fetch.ensure_converter()
        marker = first.read_bytes()

        # Change what the host serves; a second call must not notice.
        publish(release_host, body=b"#!/bin/sh\necho different\n")
        second = fetch.ensure_converter()

    assert second == first
    assert second.read_bytes() == marker


def test_forcing_a_fetch_replaces_what_was_cached(release_host, cache):
    publish(release_host)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fetch.ensure_converter()
        publish(release_host, body=b"#!/bin/sh\necho newer\n")
        refreshed = fetch.ensure_converter(force=True)

    assert b"newer" in refreshed.read_bytes()


def test_a_wrong_checksum_stops_the_install(release_host, cache):
    publish(release_host, checksum="0" * 64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ConverterFetchError, match="checksum mismatch"):
            fetch.ensure_converter()

    assert fetch.cached_converter_path() is None, (
        "a converter that failed its checksum must not be left behind"
    )


def test_a_missing_release_is_reported_clearly(release_host, cache):
    # Nothing published: the host answers 404.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ConverterFetchError, match="download failed"):
            fetch.ensure_converter()


def test_an_unreachable_host_is_reported_clearly(cache, monkeypatch):
    monkeypatch.setenv(fetch.BASE_URL_ENV_VAR, "http://127.0.0.1:1/nothing")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ConverterFetchError, match="download failed"):
            fetch.ensure_converter()


# --------------------------------------------------------------------------
# Extraction, which handles an archive from the network
# --------------------------------------------------------------------------
def test_an_archive_cannot_write_outside_the_cache(tmp_path):
    """context part: tarfile.extractall() happily follows a member path that
    climbs out of the destination — the CVE-2007-4559 family. The guard is
    the reason this module can extract something it just downloaded."""
    escape = tmp_path / "escape.tar"
    victim = tmp_path / "payload"
    victim.write_text("owned")
    with tarfile.open(escape, "w") as archive:
        archive.add(victim, arcname="../../escaped")

    destination = tmp_path / "dest"
    destination.mkdir()
    with tarfile.open(escape) as archive:
        with pytest.raises(ConverterFetchError, match="unsafe path"):
            fetch._safe_extract(archive, destination)


def test_an_archive_cannot_smuggle_in_a_link(tmp_path):
    linked = tmp_path / "linked.tar"
    with tarfile.open(linked, "w") as archive:
        info = tarfile.TarInfo("gwyconvert")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        archive.addfile(info)

    destination = tmp_path / "dest"
    destination.mkdir()
    with tarfile.open(linked) as archive:
        with pytest.raises(ConverterFetchError, match="link entry"):
            fetch._safe_extract(archive, destination)


def test_an_ordinary_archive_extracts(tmp_path):
    plain = tmp_path / "plain.tar"
    source = tmp_path / "gwyconvert"
    source.write_text("binary")
    with tarfile.open(plain, "w") as archive:
        archive.add(source, arcname="gwyconvert")

    destination = tmp_path / "dest"
    destination.mkdir()
    with tarfile.open(plain) as archive:
        fetch._safe_extract(archive, destination)
    assert (destination / "gwyconvert").read_text() == "binary"


# --------------------------------------------------------------------------
# Where the rest of the package meets it
# --------------------------------------------------------------------------
def test_the_cache_is_reported_only_once_something_is_in_it(cache):
    assert fetch.cached_converter_path() is None
    cache.mkdir(parents=True)
    binary = cache / fetch._cached_binary_name()
    binary.write_text("#!/bin/sh\n")
    assert fetch.cached_converter_path() == binary


def test_discovery_falls_back_to_a_fetched_converter(release_host, cache,
                                                     tmp_path, monkeypatch):
    """The last step of find_converter(): with nothing else configured, a
    binary fetched earlier is what gets used."""
    from gwyddionpy._run import ENV_VAR, find_converter

    publish(release_host)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fetched = fetch.ensure_converter()

    monkeypatch.delenv(ENV_VAR, raising=False)
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setattr("gwyddionpy._fetch_converter.cached_converter_path",
                        lambda: fetched)

    # The installed wheel is found before the cache, so it is hidden here to
    # reach the step under test.
    import builtins

    real_import = builtins.__import__

    def without_the_wheel(name, *args, **kwargs):
        if name == "gwyddionpy_converter":
            raise ImportError("hidden for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_the_wheel)
    assert Path(find_converter()) == fetched
