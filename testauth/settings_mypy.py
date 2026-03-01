from allianceauth.utils import cache as aa_cache

from testauth.settings.local import *  # noqa: F403

# Keep mypy/django-stubs initialization offline and deterministic.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aa-todo-mypy",
    }
}


class _MypyRedisClient:
    def ping(self) -> bool:
        return True

    def delete(self, *args: object, **kwargs: object) -> None:
        return None

    def incr(self, *args: object, **kwargs: object) -> int:
        return 0

    def zadd(self, *args: object, **kwargs: object) -> None:
        return None

    def zcount(self, *args: object, **kwargs: object) -> int:
        return 0

    def zrangebyscore(self, *args: object, **kwargs: object) -> list[bytes]:
        return []

    def info(self) -> dict[str, str]:
        return {"redis_version": "7.0.0"}


aa_cache.get_redis_client = lambda: _MypyRedisClient()
