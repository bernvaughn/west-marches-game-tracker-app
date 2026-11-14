"""Edit plan names, limits and prices here. No payment processing."""

TBD = "To be decided"

_LIMIT_LABELS = ("Clubs", "Players per club", "Characters", "Storage")

PLANS = [
    {
        "key": "free",
        "name": "Free",
        "price": "Free",
        "summary": "Limited use for a small club.",
        "limits": [(label, TBD) for label in _LIMIT_LABELS],
    },
    {
        "key": "subscription",
        "name": "Subscription",
        "price": TBD,
        "summary": "Heavier use. It pays for the servers and supports the owner.",
        "limits": [(label, TBD) for label in _LIMIT_LABELS],
    },
]
