"""Dashboard provider system for extensible dashboard widgets."""

from typing import Protocol

from django.http import HttpRequest


class DashboardProvider(Protocol):
    """Protocol for a dashboard widget/section provider."""

    key: str
    order: int
    template: str

    def get_context(self, request: HttpRequest, club, character, membership) -> dict:
        """Return context for this provider's template."""
        ...

    def should_show(self, request: HttpRequest, club, character, membership) -> bool:
        """Whether to render this provider for the current user."""
        return True


_providers: dict[str, DashboardProvider] = {}


def register_provider(provider: DashboardProvider) -> None:
    """Register a dashboard provider."""
    _providers[provider.key] = provider


def get_providers() -> list[DashboardProvider]:
    """Get all registered providers sorted by order."""
    return sorted(_providers.values(), key=lambda p: p.order)


def get_provider(key: str) -> DashboardProvider | None:
    """Get a specific provider by key."""
    return _providers.get(key)