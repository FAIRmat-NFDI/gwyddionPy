"""Tags the wheel for the platform its bundled gwyconvert was built on.

This package compiles nothing. The bundle — gwyconvert plus its relocated
shared libraries, produced by ci/build-*.sh and staged into
src/gwyddionpy_converter/bin/ — is copied in as prebuilt package data, so
setuptools has no C extension to infer a platform tag from. Overriding
``bdist_wheel.get_tag()`` is the standard pattern for wheels that bundle a
binary without shipping a Python extension module; the ``patchelf`` PyPI
package does the same.

Tag shape: ``py3-none-<platform>``. The Python half is fixed because the
payload is a standalone executable invoked via subprocess and so depends on
no Python ABI — one wheel serves every interpreter.

The platform half is *resolved*, never hardcoded. A fixed tag is not merely
imprecise, it is unsafe: cibuildwheel's default Linux set builds both a
manylinux and a musllinux wheel, and one hardcoded tag gives them identical
filenames, so the musl-linked binary silently overwrites the glibc one and
the published wheel promises a compatibility it does not have.
https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/
"""
from __future__ import annotations

import os
import sysconfig
from pathlib import Path

from setuptools import setup
from setuptools.dist import Distribution

# Where ci/bundle-*.sh stage the built bundle. Changing this path means
# changing those scripts, MANIFEST.in, and gwyddionpy_converter/__init__.py.
BIN_DIR = Path(__file__).parent / "src" / "gwyddionpy_converter" / "bin"

# Explicit override, checked first so a build can always be unambiguous.
PLAT_ENV_VAR = "GWYDDIONPY_WHEEL_PLAT"


def _normalize(tag: str) -> str:
    """``macosx-11.0-arm64`` -> ``macosx_11_0_arm64``.

    Wheel filename components may only contain alphanumerics and
    underscores, while sysconfig reports dots and hyphens.
    """
    return tag.replace("-", "_").replace(".", "_")


def platform_tag() -> str:
    """Resolve the wheel's platform tag for the environment we're building in.

    Order: explicit override, then the manylinux/musllinux container's own
    declaration, then the interpreter's idea of its platform.
    """
    override = os.environ.get(PLAT_ENV_VAR)
    if override:
        return _normalize(override)

    # Set by every official manylinux/musllinux image, and so by every
    # cibuildwheel Linux build. This is what keeps the two apart: sysconfig
    # below reports only "linux_x86_64" for both.
    auditwheel_plat = os.environ.get("AUDITWHEEL_PLAT")
    if auditwheel_plat:
        return _normalize(auditwheel_plat)

    plat = _normalize(sysconfig.get_platform())

    # A bare `linux_x86_64` tag is not distributable — PyPI rejects it,
    # because it says nothing about the glibc/musl baseline the binaries
    # were linked against. Reaching here on Linux means building outside a
    # manylinux container with no override set, so fail now rather than
    # produce a wheel that cannot be uploaded.
    if plat.startswith("linux_"):
        raise RuntimeError(
            f"refusing to tag a Linux wheel {plat!r}: PyPI rejects bare "
            "linux_* tags. Build inside a manylinux/musllinux container "
            f"(which sets AUDITWHEEL_PLAT), or set {PLAT_ENV_VAR} explicitly "
            "to the intended tag, e.g. manylinux_2_28_x86_64."
        )
    return plat


def _check_bundle_present() -> None:
    """Fail fast if the prebuilt bundle was never staged.

    Without this, the build would happily emit an empty wheel that only
    fails much later, at run time on a user's machine. It also makes the
    limitation explicit: this package cannot be built from source alone, it
    only packages an artifact that ci/build-*.sh produced beforehand.
    """
    if not BIN_DIR.is_dir() or not any(BIN_DIR.iterdir()):
        raise RuntimeError(
            f"no prebuilt gwyconvert bundle found at {BIN_DIR}. This package "
            "does not build the converter itself — it packages a bundle "
            "produced beforehand by gwyddionpy-converter/ci/build-*.sh. Run "
            "the script for your platform first, or install a released wheel."
        )


try:
    # setuptools >= 70.1 owns bdist_wheel; importing it from `wheel` is
    # deprecated. pyproject.toml requires setuptools >= 78.1.1, so the first
    # import is the one that runs; the fallback covers only an unexpectedly
    # old build environment.
    try:
        from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
    except ImportError:  # pragma: no cover - legacy build environments only
        from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            super().finalize_options()
            # Not a pure-Python wheel: it carries platform-specific binaries.
            self.root_is_pure = False

        def get_tag(self):
            _check_bundle_present()
            return "py3", "none", platform_tag()

except ImportError:  # pragma: no cover - wheel is a declared build dep
    bdist_wheel = None


class BinaryDistribution(Distribution):
    """Marks the distribution as platform-specific despite having no
    ext_modules, so setuptools doesn't label the wheel as pure Python."""

    def has_ext_modules(self):
        return True


setup(
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel} if bdist_wheel else {},
)
