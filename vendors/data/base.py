from django.db import models

class BaseRepository:
    """Base generic repository for single-model data access."""
    def __init__(self, model: type[models.Model]):
        self.model = model

    def get_by_id(self, obj_id, prefetch=None, select_related=None):
        qs = self.model.objects.all()
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        try:
            return qs.get(pk=obj_id)
        except self.model.DoesNotExist:
            return None

    def create(self, **kwargs):
        return self.model.objects.create(**kwargs)

    def filter(self, **kwargs):
        return self.model.objects.filter(**kwargs)

    def all(self):
        return self.model.objects.all()
