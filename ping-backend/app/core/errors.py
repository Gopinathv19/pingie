"""Domain errors, translated into HTTP responses by handlers in main.py.

Same shape as Memora: services raise these and never import FastAPI, so the
service layer runs unchanged from a background task, a script or a test.
"""


class PingError(Exception):
    """Base class for expected, client-visible failures."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(PingError):
    status_code = 404
    code = "not_found"


class ConflictError(PingError):
    status_code = 409
    code = "conflict"


class ValidationError(PingError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(PingError):
    status_code = 401
    code = "unauthenticated"


class PermissionError_(PingError):
    status_code = 403
    code = "forbidden"


class QuotaExceededError(PingError):
    """A plan limit (bots, monthly messages, sources) was reached."""

    status_code = 402
    code = "quota_exceeded"


class PlanRestrictionError(PingError):
    """A feature is not available on the current plan."""

    status_code = 402
    code = "plan_restriction"


class RateLimitedError(PingError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(PingError):
    """Memora or the LLM provider is not configured or not reachable."""

    status_code = 503
    code = "service_unavailable"
