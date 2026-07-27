"""Forces a manylinux platform tag for the bundled gwyconvert binary.

The bundle (gwyconvert + its patchelf-rewritten shared libraries, built in
FAIRmat-NFDI/gwyddionPy's build-converter.yml on rockylinux:8 — glibc 2.28
floor, the manylinux_2_28 baseline) is copied in as prebuilt data, not
compiled here, so setuptools has no C extension to auto-detect a platform
tag from. Overriding bdist_wheel.get_tag() is the standard pattern for
binary-bundling wheels with no Python extension module (the `patchelf`
PyPI package does the same for its own bundled binary).
"""
from setuptools import setup
from setuptools.dist import Distribution

try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            super().finalize_options()
            self.root_is_pure = False

        def get_tag(self):
            return "py3", "none", "manylinux_2_28_x86_64"

except ImportError:
    bdist_wheel = None


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


setup(
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel} if bdist_wheel else {},
)
