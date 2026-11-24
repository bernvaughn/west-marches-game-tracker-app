"""Club-scoped item search for the shared picker component."""

from django.db.models import Exists, OuterRef, Q

from .models import Item, RecentItemPick

DEFAULT_LIMIT = 30
RECENT_PICKS_LIMIT = 10


def search_items(
    club,
    membership,
    query: str = "",
    *,
    include_retired: bool = False,
    limit: int = DEFAULT_LIMIT,
):
    """
    Search items in a club, scoped to the membership's recent picks.

    Args:
        club: The club to search in.
        membership: The membership doing the search (for recent picks ordering).
        query: Search query string. Matches item name, magic type, or trait words.
        include_retired: Whether to include retired items.
        limit: Maximum number of results to return.

    Returns:
        QuerySet of Items ordered by recent picks first, then by name.
    """
    items = Item.objects.for_club(club)

    if not include_retired:
        items = items.filter(retired=False)

    if query:
        query = query.strip()
        # Split query into words for trait matching
        words = query.split()

        # Build Q objects for name, magic_type, and traits
        q_objects = Q(name__icontains=query) | Q(magic_type__iexact=query)
        for word in words:
            if len(word) >= 2:  # Only match trait words of length >= 2
                q_objects |= Q(traits__icontains=word)

        items = items.filter(q_objects)

    # Annotate with recent pick timestamp for this membership
    recent_subquery = RecentItemPick.objects.filter(
        membership=membership,
        item=OuterRef("pk"),
    ).order_by("-used_at")

    items = items.annotate(
        recent_pick_used_at=Exists(recent_subquery.values("used_at")[:1]),
    ).order_by("-recent_pick_used_at", "name")

    return items[:limit]


def record_pick(membership, item):
    """
    Record that a membership picked an item.

    Keeps only the last RECENT_PICKS_LIMIT picks per membership.
    """
    from django.utils import timezone

    # Use update_or_create to update the timestamp if the pick already exists
    RecentItemPick.objects.update_or_create(
        membership=membership,
        item=item,
        defaults={"used_at": timezone.now()},
    )

    # Trim to last RECENT_PICKS_LIMIT picks
    excess_pks = list(
        RecentItemPick.objects.filter(membership=membership)
        .order_by("-used_at")
        .values_list("pk", flat=True)[RECENT_PICKS_LIMIT:]
    )
    if excess_pks:
        RecentItemPick.objects.filter(pk__in=excess_pks).delete()
