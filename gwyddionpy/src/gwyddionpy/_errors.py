"""Typed exceptions raised by gwyddionpy."""


class GwyddionPyError(Exception):
    """Base class for all gwyddionpy errors."""


class ConverterNotFoundError(GwyddionPyError):
    """The gwyconvert binary could not be located.

    Set the GWYDDIONPY_CONVERT environment variable or put gwyconvert on PATH.
    """


class ConversionError(GwyddionPyError):
    """gwyconvert ran but failed; the converter's stderr is in the message."""


class UnsupportedFormatError(ConversionError):
    """No Gwyddion file module could load the input file."""


class ConverterFetchError(GwyddionPyError):
    """Downloading/verifying/extracting a prebuilt gwyconvert release failed."""
