from functools import lru_cache

from ...config import settings
from .base import Storage
from .local import LocalStorage


@lru_cache
def get_storage() -> Storage:
    return LocalStorage(settings.storage_dir)
