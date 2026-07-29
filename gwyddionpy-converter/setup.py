"""Tags the wheel for the platform its bundled gwyconvert was built on.

The bundle (gwyconvert + its rewritten shared libraries, built by
FAIRmat-NFDI/gwyddionPy's build-converter.yml) is copied in as prebuilt data,
not compiled here, so setuptools has no C extension to auto-detect a platform
tag from. Overriding bdist_wheel.get_tag() is the standard pattern for
binary-bundling wheels with no Python extension module (the `patchelf` PyPI
package does the same for its own bundled binary).

The Python side of the tag is always ``py3-none``: the payload is a
standalone executable run via subprocess, so it depends on no Python ABI and
one wheel serves every Python. Verified 2026-07-29 that cibuildwheel accepts
this even though its own build identifiers are always version-specific — it
builds once with the pinned interpreter and ships the py3-none wheel
unchanged.

The *platform* half used to be hardcoded to ``manylinux_2_28_x86_64``. That
was wrong the moment more than one platform was built, and it failed in a
genuinely dangerous way rather than loudly: in the same 2026-07-29 spike,
cibuildwheel's default Linux set built both a manylinux *and* a musllinux
wheel, the hardcoded tag labelled both ``manylinux_2_28_x86_64``, they landed
on identical filenames, and the musl-built binary silently overwrote the
glibc one. A wheel claiming glibc compatibility while containing musl-linked
binaries would fail at runtime on every user's machine. Hence the resolution
order below, which always reflects the environment actually being built in.
"""
from __future__ import annotations

import os
import sysconfig
from pathlib import Path

from setuptools import setup
from setuptools.dist import Distribution

# Where publish.yml (and cibuildwheel's before-all) stage the built bundle.
BIN_DIR = Path(__file__).parent / "src" / "gwyddionpy_converter" / "bin"

# Explicit override, checked first so CI can always be unambiguous.
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

    # Set by every official manylinux/musllinux image and therefore by
    # cibuildwheel's Linux builds — verified 2026-07-29 that
    # manylinux_2_28_x86_64 and musllinux_1_2_x86_64 report themselves
    # correctly here. This is what keeps the two apart.
    auditwheel_plat = os.environ.get("AUDITWHEEL_PLAT")
    if auditwheel_plat:
        return _normalize(auditwheel_plat)

    plat = _normalize(sysconfig.get_platform())

    # A bare `linux_x86_64` tag is not a distributable tag: PyPI rejects it
    # outright, because it promises nothing about the glibc/musl baseline the
    # binaries were linked against. Reaching here on Linux means the build is
    # running outside a manylinux container with no override set, so fail
    # rather than produce a wheel that cannot be uploaded.
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

    Without this the build happily produces an empty wheel that only fails
    much later, at import time on a user's machine. It also makes the failure
    mode of `pip install` from a source tree obvious: this package is not
    buildable from source alone, it packages an artifact built beforehand by
    ci/build-*.sh.
    """
    if not BIN_DIR.is_dir() or not any(BIN_DIR.iterdir()):
        raise RuntimeError(
            f"no prebuilt gwyconvert bundle found at {BIN_DIR}. This package "
            "does not build the converter itself — it packages a bundle "
            "produced beforehand by gwyddionpy-converter/ci/build-*.sh (see "
            "docs/BUILD.md). Run that first, or install a released wheel."
        )


try:
    # setuptools >= 70.1 owns bdist_wheel; importing it from `wheel` is
    # deprecated and warns (FutureWarning). pyproject.toml already requires
    # setuptools >= 78.1.1, so the first import is the one that runs — the
    # fallback only matters for an unexpectedly old build environment.
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
