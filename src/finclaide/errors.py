class FinclaideError(Exception):
    """Base application error."""


class ConfigError(FinclaideError):
    """Raised when required runtime config is missing."""


class DataIntegrityError(FinclaideError):
    """Raised when imported or synced data fails strict validation."""


class OperationInProgressError(FinclaideError):
    """Raised when a conflicting write operation is already running."""


class NotFoundError(FinclaideError):
    """Raised when a referenced entity does not exist."""
