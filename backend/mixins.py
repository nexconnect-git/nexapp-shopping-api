"""Shared view mixins for NexConnect Django views."""

from typing import Optional, Type


class BaseDetailView:
    """Mixin that provides a generic object-lookup helper for detail views.

    Intended to be mixed into DRF APIView subclasses that need to look up a
    model instance by arbitrary keyword arguments without raising an exception
    on miss (returning ``None`` instead so the caller can return a 404
    response explicitly).
    """

    @staticmethod
    def get_object_or_none(model_class: Type, **kwargs) -> Optional[object]:
        """Fetch a single model instance or return None if not found.

        Args:
            model_class: The Django model class to query.
            **kwargs: Lookup keyword arguments forwarded to ``.get()``.

        Returns:
            The matching model instance, or ``None`` if it does not exist.
        """
        try:
            return model_class.objects.get(**kwargs)
        except model_class.DoesNotExist:
            return None
