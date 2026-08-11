"""Tag the wheel ``py3-none-<platform>`` for the bundle it carries.

This package compiles nothing; ci/build-*.sh stages a prebuilt bundle into
src/gwyddionpy_converter/bin/, so setuptools has no extension to infer a tag
from. The Python half is fixed because the payload depends on no Python
application binary interface (ABI). The platform half is resolved, never
hardcoded: one fixed tag would give a manylinux and a musllinux wheel the
same filename, and the second would silently overwrite the first.

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
    """Resolve the wheel's platform tag for the environment being built in.

    Order: explicit override, the manylinux/musllinux container's own
    declaration, then the interpreter's idea of its platform.
    """
    override = os.environ.get(PLAT_ENV_VAR)
    if override:
        return _normalize(override)

    # Set by every official manylinux/musllinux image, so by every
    # cibuildwheel Linux build. It is what keeps the two apart: sysconfig
    # reports only "linux_x86_64" for both.
    auditwheel_plat = os.environ.get("AUDITWHEEL_PLAT")
    if auditwheel_plat:
        return _normalize(auditwheel_plat)

    plat = _normalize(sysconfig.get_platform())

    # PyPI rejects a bare `linux_x86_64` tag, because it says nothing about
    # which C library the binaries were linked against. Reaching here means
    # building on Linux outside a manylinux container with no override, so
    # fail now rather than produce a wheel that cannot be uploaded.
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

    Without this the build emits an empty wheel that only fails later, on a
    user's machine. It also states the limitation: this package cannot be
    built from source alone, it only packages what ci/build-*.sh produced.
    """
    if not BIN_DIR.is_dir() or not any(BIN_DIR.iterdir()):
        raise RuntimeError(
            f"no prebuilt gwyconvert bundle found at {BIN_DIR}. This package "
            "does not build the converter itself — it packages a bundle "
            "produced beforehand by gwyddionpy-converter/ci/build-*.sh. Run "
            "the script for your platform first, or install a released wheel."
        )


try:
    # setuptools >= 70.1 owns bdist_wheel, and importing it from `wheel` is
    # deprecated. pyproject.toml requires setuptools >= 78.1.1, so the first
    # import is the one that runs. The fallback covers an unexpectedly old
    # build environment only.
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
    """Mark the distribution as platform-specific despite having no
    ext_modules, so setuptools does not label the wheel as pure Python."""

    def has_ext_modules(self):
        return True


setup(
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel} if bdist_wheel else {},
)
