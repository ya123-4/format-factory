"""Conversion error taxonomy (spec §7)."""


class ConversionError(Exception):
    """Base class for all conversion errors."""


class UnsupportedFormat(ConversionError):
    """Unrecognizable input or unsupported target combination."""


class InputCorrupt(ConversionError):
    """Source file damaged or unreadable."""


class ToolMissing(ConversionError):
    """Required external tool not found."""


class ConversionFailed(ConversionError):
    """External tool exited non-zero; carries exit_code and stderr tail."""

    def __init__(self, message: str, exit_code: int, stderr_tail: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail


class DiskFull(ConversionError):
    """Output disk out of space."""


class FileNotFound(ConversionError):
    """Source file removed/moved before execution."""


class PermissionDenied(ConversionError):
    """No read/write permission on source or output path."""


class PathTooLong(ConversionError):
    """Windows path exceeds MAX_PATH."""
