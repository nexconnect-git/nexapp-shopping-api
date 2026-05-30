"""HTTP middleware for request-level log context and request metrics."""

import logging
import time
import uuid

from helpers.logging_context import clear_log_context, set_log_context

request_logger = logging.getLogger("backend.request")


class RequestLoggingMiddleware:
    """Attach username/request-id context to all logs emitted during the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        username = self._resolve_username(request)
        username_token, request_token = set_log_context(username, request_id)
        start_time = time.monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            request_logger.exception(
                "request_failed method=%s path=%s elapsed_ms=%s",
                request.method,
                request.get_full_path(),
                elapsed_ms,
            )
            raise
        else:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            response["X-Request-ID"] = request_id
            request_logger.info(
                "request_completed method=%s path=%s status=%s elapsed_ms=%s",
                request.method,
                request.get_full_path(),
                response.status_code,
                elapsed_ms,
            )
            return response
        finally:
            clear_log_context(username_token, request_token)

    @staticmethod
    def _resolve_username(request):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return "anonymous"
        return getattr(user, "username", "") or getattr(user, "email", "") or str(user.id)

