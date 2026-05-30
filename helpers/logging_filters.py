"""Logging filters that enrich log records with request context."""

import logging

from helpers.logging_context import get_log_context


class RequestContextFilter(logging.Filter):
    """Inject username/request_id into all records."""

    def filter(self, record):
        context = get_log_context()
        record.username = getattr(record, "username", None) or context["username"]
        record.request_id = getattr(record, "request_id", None) or context["request_id"]
        return True

