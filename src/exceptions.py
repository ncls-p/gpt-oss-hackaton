"""
Custom exceptions for the application.
"""


class BaseAppError(Exception):
    """Base exception class for application errors."""

    pass


class LLMError(BaseAppError):
    """Exception raised for LLM-related errors."""

    pass


class FileRepositoryError(BaseAppError):
    """Exception raised for file repository errors."""

    pass


class ConfigurationError(BaseAppError):
    """Exception raised for configuration errors."""

    pass


class ApplicationError(BaseAppError):
    """Exception raised for application launching errors."""

    pass
