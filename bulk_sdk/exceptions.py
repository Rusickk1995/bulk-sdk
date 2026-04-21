"""Exceptions for the BULK Exchange HTTP MVP."""

from __future__ import annotations


class BulkError(Exception):
    """Base exception for BULK SDK errors."""


class BulkAPIError(BulkError):
    """Raised when the BULK API returns an error response."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        raw: object | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.raw = raw

    def __str__(self) -> str:
        if self.status_code is None:
            return self.message

        return f"{self.message} (status_code={self.status_code})"


# Backward-compatible aliases for the existing scaffold.
BulkSDKError = BulkError
BulkConfigurationError = BulkError
BulkHTTPError = BulkAPIError
