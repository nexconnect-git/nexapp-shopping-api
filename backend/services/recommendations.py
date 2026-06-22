import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class RecommendationServiceClient:
    """Internal client for the ML recommendation microservice."""

    def __init__(self):
        self.base_url = getattr(settings, "RECOMMENDATION_SERVICE_URL", "").rstrip("/")
        self.timeout = float(getattr(settings, "RECOMMENDATION_SERVICE_TIMEOUT_SECONDS", 1.5))
        self.enabled = bool(getattr(settings, "RECOMMENDATION_SERVICE_ENABLED", False) and self.base_url)

    def user_recommendations(
        self,
        *,
        user_id: str | None,
        limit: int,
        recommendation_type: str,
        location: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        payload = {
            "user_id": user_id,
            "limit": limit,
            "recommendation_type": recommendation_type,
            "location": location,
        }
        try:
            response = requests.post(
                f"{self.base_url}/v1/recommendations/user",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning("Recommendation service unavailable: %s", exc)
            return []
        except ValueError as exc:
            logger.warning("Recommendation service returned invalid JSON: %s", exc)
            return []

        items = data.get("items", [])
        if not isinstance(items, list):
            return []
        return [
            item for item in items
            if isinstance(item, dict) and item.get("product_id")
        ]

    def store_recommendations(
        self,
        *,
        user_id: str | None,
        limit: int,
        location: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        payload = {
            "user_id": user_id,
            "limit": limit,
            "location": location,
        }
        try:
            response = requests.post(
                f"{self.base_url}/v1/recommendations/stores",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning("Recommendation service store ranking unavailable: %s", exc)
            return []
        except ValueError as exc:
            logger.warning("Recommendation service returned invalid store JSON: %s", exc)
            return []

        items = data.get("items", [])
        if not isinstance(items, list):
            return []
        return [
            item for item in items
            if isinstance(item, dict) and item.get("store_id")
        ]
