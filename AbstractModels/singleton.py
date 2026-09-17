from django.core.cache import cache
from django.db import models


class SingletonModel(models.Model):
    CACHE_TIMEOUT = 300

    class Meta:
        abstract = True

    @classmethod
    def _cache_key(cls):
        return f"singleton:{cls._meta.label_lower}:pk1"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)
        cache.set(self._cache_key(), self, timeout=self.CACHE_TIMEOUT)

    def delete(self, *args, **kwargs):
        cache.delete(self._cache_key())
        return super().delete(*args, **kwargs)

    @classmethod
    def load(cls):
        cache_key = cls._cache_key()
        obj = cache.get(cache_key)
        if obj is not None:
            return obj

        obj, created = cls.objects.get_or_create(pk=1)
        cache.set(cache_key, obj, timeout=cls.CACHE_TIMEOUT)
        return obj
