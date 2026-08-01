"""Custom exception hierarchy for RepoLens."""


class RepoLensError(Exception):
    """Base exception for all RepoLens errors."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidURLError(RepoLensError):
    """Raised when the provided repository URL is invalid."""

    exit_code = 2


class RepositoryNotFoundError(RepoLensError):
    """Raised when the repository does not exist or is private."""

    exit_code = 3


class RateLimitError(RepoLensError):
    """Raised when GitHub API rate limit is exhausted."""

    exit_code = 4

    def __init__(self, message: str, reset_time: str | None = None) -> None:
        self.reset_time = reset_time
        super().__init__(message)


class NetworkError(RepoLensError):
    """Raised when GitHub is unreachable after retries."""

    exit_code = 5


class MissingAPIKeyError(RepoLensError):
    """Raised when LLM API key is required but not configured."""

    exit_code = 6


class ConfigurationError(RepoLensError):
    """Raised when configuration is invalid."""

    exit_code = 1
