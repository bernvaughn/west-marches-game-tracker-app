from .models import DoNotEmail


def is_suppressed(address: str) -> bool:
    """Check if an address is suppressed (do-not-email or .invalid)."""
    normalized = address.strip().lower()
    if normalized.endswith(".invalid"):
        return True
    return DoNotEmail.objects.filter(address=normalized).exists()


def suppress(address: str, reason: str = "manual") -> DoNotEmail:
    """Add or update a suppressed address."""
    normalized = address.strip().lower()
    obj, created = DoNotEmail.objects.get_or_create(address=normalized, defaults={"reason": reason})
    if not created:
        obj.reason = reason
        obj.save(update_fields=["reason"])
    return obj


def clear(address: str) -> bool:
    """Remove a suppressed address. Returns True if deleted."""
    normalized = address.strip().lower()
    deleted, _ = DoNotEmail.objects.filter(address=normalized).delete()
    return deleted > 0