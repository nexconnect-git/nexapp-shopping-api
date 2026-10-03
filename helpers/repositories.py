"""Model-neutral repository base shared by the application's data layers."""

from django.db import models


class BaseRepository:
    """Base generic repository for single-model data access."""

    def __init__(self, model: type[models.Model]):
        self.model = model

    def get_by_id(self, obj_id, prefetch=None, select_related=None):
        query = self.model.objects.all()
        if select_related:
            query = query.select_related(*select_related)
        if prefetch:
            query = query.prefetch_related(*prefetch)
        return query.filter(pk=obj_id).first()

    def create(self, **kwargs):
        return self.model.objects.create(**kwargs)

    def filter(self, **kwargs):
        return self.model.objects.filter(**kwargs)

    def all(self):
        return self.model.objects.all()
