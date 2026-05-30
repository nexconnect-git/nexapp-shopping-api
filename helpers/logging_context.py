"""Shared logging context for per-request metadata."""

from contextvars import ContextVar

_LOG_USERNAME = ContextVar("log_username", default="system")
_LOG_REQUEST_ID = ContextVar("log_request_id", default="-")


def set_log_context(username, request_id):
    username_token = _LOG_USERNAME.set(username or "system")
    request_token = _LOG_REQUEST_ID.set(request_id or "-")
    return username_token, request_token


def clear_log_context(username_token, request_token):
    _LOG_USERNAME.reset(username_token)
    _LOG_REQUEST_ID.reset(request_token)


def get_log_context():
    return {
        "username": _LOG_USERNAME.get(),
        "request_id": _LOG_REQUEST_ID.get(),
    }

