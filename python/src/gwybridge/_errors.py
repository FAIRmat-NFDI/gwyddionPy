"""Typed exceptions raised by gwybridge."""


class GwybridgeError(Exception):
    """Base class for all gwybridge errors."""


class ConverterNotFoundError(GwybridgeError):
    """The gwyconvert binary could not be located.

    Set the GWYBRIDGE_CONVERT environment variable or put gwyconvert on PATH.
    """


class ConversionError(GwybridgeError):
    """gwyconvert ran but failed; the converter's stderr is in the message."""


class UnsupportedFormatError(ConversionError):
    """No Gwyddion file module could load the input file."""
