"""
HTTP request utility functions.

Provides helpers for extracting data from Django HttpRequest objects,
shared across multiple apps.
"""


def get_client_ip(request) -> str | None:
    """Extract the real client IP address from a Django HTTP request.

    Respects the ``X-Forwarded-For`` header set by load balancers and
    reverse proxies before falling back to ``REMOTE_ADDR``.

    Args:
        request: The Django ``HttpRequest`` object.

    Returns:
        The client IP as a string, or ``None`` when unavailable.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
