"""Player dashboard view: contextual quick actions for between-session tasks."""

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from accounts.dashboard_providers import get_provider, get_providers
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_get_object_or_404
from downtime import services as downtime_services
from player_characters.inventory import coin_summary
from player_characters.junk import junk_rows, junk_value
from player_characters.models import Character
from player_characters.selection import selected_character

# =============================================================================
# Dashboard Context Building (Uses Unified Provider System)
# =============================================================================


def _get_dashboard_context(request, club, character, membership):
    """Build the context dictionary for the player dashboard using providers."""
    providers = []
    for provider in get_providers():
        if provider.should_show(request, club, character, membership):
            ctx = provider.get_context(request, club, character, membership)
            providers.append(
                {
                    "key": provider.key,
                    "order": provider.order,
                    "template": provider.template,
                    "ctx": ctx,
                }
            )

    # Build header context
    coin_sum = coin_summary(character)
    downtime_balance = downtime_services.balance(character)
    junk = junk_rows(character)
    junk_val = junk_value(character, junk)

    from accounts.models import Message

    unread_count = (
        Message.objects.for_club(club)
        .filter(status=Message.Status.OPEN)
        .exclude(sender=membership)
        .count()
    )

    return {
        "character": character,
        "coin_summary": coin_sum,
        "downtime_balance": downtime_balance,
        "junk_count": len(junk),
        "junk_value": junk_val,
        "unread_count": unread_count,
        "membership": membership,
        "dashboard_providers": providers,
    }


@club_member_required
def player_dashboard(request, club_slug):
    """Player dashboard with contextual quick actions for between-session tasks."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    # If user is GM or admin, redirect to club home (navigation cards)
    if is_game_master(request.user, club) or is_club_admin(request.user, club):
        from django.shortcuts import redirect

        return redirect("club_home", club_slug=club.slug)

    # If no character selected, show character selector prompt
    if character is None:
        return render(
            request,
            "accounts/dashboard_no_character.html",
            {
                "club": club,
                "membership": membership,
            },
        )

    ctx = _get_dashboard_context(request, club, character, membership)
    return render(request, "accounts/dashboard.html", ctx)


# =============================================================================
# HTMX Partial Endpoints
# =============================================================================


@club_member_required
def dashboard_partial(request, club_slug, provider_key):
    """HTMX partial endpoint for a dashboard provider."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    if character is None:
        raise Http404("No character selected.")

    provider = get_provider(provider_key)
    if provider is None:
        raise Http404(f"Provider '{provider_key}' not found.")

    if not provider.should_show(request, club, character, membership):
        raise Http404(f"Provider '{provider_key}' not available.")

    ctx = provider.get_context(request, club, character, membership)
    html = render_to_string(provider.template, ctx, request=request)
    return HttpResponse(html)


# =============================================================================
# Character Preview Endpoint
# =============================================================================


@club_member_required
def character_preview(request, club_slug, pk):
    """Character preview endpoint returning JSON for tooltip."""
    membership = request.membership
    character = club_get_object_or_404(request, Character, pk=pk)

    # Verify ownership
    if character.owner_id != membership.id:
        raise Http404("Not your character.")

    # Build preview data
    coin_sum = coin_summary(character)
    downtime_balance = downtime_services.balance(character)
    junk = junk_rows(character)
    junk_val = junk_value(character, junk)

    return JsonResponse(
        {
            "name": character.name,
            "level": character.level,
            "char_class": character.char_class,
            "species": character.species,
            "coins_available": coin_sum.available,
            "junk_count": len(junk),
            "junk_value": junk_val,
            "downtime_balance": downtime_balance,
        }
    )


@club_member_required
def print_session_pack_modal(request, club_slug, pk):
    """HTMX partial endpoint for the Print Session Pack options modal."""
    character = club_get_object_or_404(request, Character, pk=pk)

    # Verify ownership
    if character.owner_id != request.membership.id:
        raise Http404("Not your character.")

    return render(
        request,
        "accounts/_print_session_pack_modal.html",
        {
            "club": request.club,
            "character": character,
        },
    )
