"""Custom security exceptions for the Smriti platform.

These exceptions provide structured error handling for authentication,
authorization, and rate limiting failures.
"""


class AuthenticationError(Exception):
    """Raised when authentication fails.

    Examples: invalid JWT, expired token, malformed token,
    missing credentials.
    """

    def __init__(self, detail: str = "Authentication failed") -> None:
        self.detail = detail
        super().__init__(self.detail)


class AuthorizationError(Exception):
    """Raised when an authenticated user lacks required permissions.

    Examples: insufficient role, accessing another user's resource,
    attempting admin-only operations.
    """

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        self.detail = detail
        super().__init__(self.detail)


class RateLimitExceededError(Exception):
    """Raised when a client exceeds their rate limit.

    Attributes:
        retry_after: Seconds until the rate limit window resets.
    """

    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        self.detail = detail
        self.retry_after = retry_after
        super().__init__(self.detail)
