"""TTL-кэш для редкого обновляемых справочников и метаданных."""

from __future__ import annotations

import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class CacheItem(Generic[T]):
    """Элемент кэша с временем жизни."""

    def __init__(self, value: T, ttl: float) -> None:
        self.value: T = value
        self.expires_at: float = time.monotonic() + ttl

    @property
    def is_expired(self) -> bool:
        """Проверяет, истек ли TTL."""
        return time.monotonic() >= self.expires_at


class TTLCache:
    """Простой асинхронно-безопасный TTL-кэш в памяти."""

    def __init__(self, default_ttl: float = 3600.0) -> None:
        self.default_ttl = default_ttl
        self._store: dict[str, CacheItem[Any]] = {}

    def get(self, key: str) -> Any | None:
        """Возвращает значение из кэша или None, если значение отсутствует или истекло."""
        item = self._store.get(key)
        if item is None:
            return None
        if item.is_expired:
            del self._store[key]
            return None
        return item.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Сохраняет значение в кэш."""
        effective_ttl = ttl if ttl is not None else self.default_ttl
        self._store[key] = CacheItem(value, effective_ttl)

    def clear(self) -> None:
        """Очищает весь кэш."""
        self._store.clear()
