import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def nexconnect_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response

    request = context.get("request")
    path = getattr(request, "path", "")
    if isinstance(exc, KeyError) and "/orders/create/" in path:
        logger.error("Order creation failed because checkout pricing data was incomplete.", exc_info=True)
        return Response(
            {
                "error": "We could not place your order because checkout pricing was incomplete. Please refresh checkout and try again.",
                "code": "checkout_pricing_incomplete",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    logger.error("Unhandled API exception.", exc_info=True)
    return Response(
        {
            "error": "Something went wrong while processing your request. Please try again.",
            "code": "server_error",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
