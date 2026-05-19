"""Provider registry without importing concrete adapters into core."""

from collections.abc import Callable
from typing import Any


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Callable[..., Any]]] = {}

    def register(self, category: str, name: str, factory: Callable[..., Any]) -> None:
        self._providers.setdefault(category, {})[name] = factory

    def create(self, category: str, name: str, **kwargs: Any) -> Any:
        try:
            factory = self._providers[category][name]
        except KeyError as exc:
            available = sorted(self._providers.get(category, {}))
            raise LookupError(
                f"Provider '{name}' is not registered for '{category}'. "
                f"Available: {available}"
            ) from exc
        return factory(**kwargs)

    def available(self, category: str) -> tuple[str, ...]:
        return tuple(sorted(self._providers.get(category, {})))
