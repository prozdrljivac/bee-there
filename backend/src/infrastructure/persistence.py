"""Storage errors exposed to application code."""


class PersistenceError(RuntimeError):
    """A persistence operation failed."""


class PersistenceConflictError(PersistenceError):
    """Persisted data conflicts with an existing record or constraint."""
