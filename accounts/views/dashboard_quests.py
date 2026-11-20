"""Dashboard quest turn-in HTMX endpoint."""

from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.htmx import hx_response
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from ledger.services import InsufficientItems, available_items
from player_characters.selection import selected_character
from quests import services
from quests.models import Quest


@club_member_required
@require_http_methods(["GET", "POST"])
def dashboard_quest_turnin(request, club_slug, quest_pk):
    """HTMX partial endpoint for quest turn-in modal.

    GET: Returns the turn-in modal fragment (reusing quests/play/_turn_in_card.html)
    POST: Processes the turn-in using quests.services.turn_in(), returns HX-Trigger
          to close modal, show toast, and refresh dashboard
    """
    club = request.club
    character = selected_character(request)

    if character is None:
        raise Http404("No character selected.")

    quest = club_get_object_or_404(request, Quest, pk=quest_pk)
    today = timezone.localdate()

    # Verify quest is live
    if not quest.is_live_on(today):
        raise Http404("Quest is not live.")

    # Build turn-in rows and check readiness
    have = available_items(character)

    turnin_rows = []
    blocked_reason = None

    for req in quest.requirements.select_related("item"):
        has = have.get(req.item_id, 0)
        turnin_rows.append(
            {
                "item": req.item,
                "needed": req.quantity,
                "has": has,
                "short": max(0, req.quantity - has),
            }
        )

    # Check blockers (same logic as quests.views.play.detail)
    club_left = services.completions_left(quest)
    char_left = services.character_completions_left(quest, character)
    missing = services.missing_items(quest, character)

    if not turnin_rows:
        blocked_reason = "This quest has no requirements."
    elif club_left == 0:
        blocked_reason = "This quest is full."
    elif char_left == 0:
        blocked_reason = f"{character} has completed this quest the maximum number of times."
    elif missing:
        blocked_reason = _missing_text(missing)

    if request.method == "GET":
        ctx = {
            "club": club,
            "quest": quest,
            "character": character,
            "turnin_rows": turnin_rows,
            "blocked_reason": blocked_reason,
        }
        html = render_to_string("quests/play/_turn_in_card.html", ctx, request=request)
        return HttpResponse(html)

    # POST - process turn-in
    try:
        services.turn_in(quest, character, request.user)
    except InsufficientItems:
        # Re-render modal with error
        ctx = {
            "club": club,
            "quest": quest,
            "character": character,
            "turnin_rows": turnin_rows,
            "blocked_reason": _missing_text(services.missing_items(quest, character)),
        }
        html = render_to_string("quests/play/_turn_in_card.html", ctx, request=request)
        response = HttpResponse(html)
        response.status_code = 400
        return response
    except services.QuestNotLive:
        return hx_response(
            trigger={"toast": {"message": "Quest is no longer live.", "type": "error"}},
            status=400,
        )
    except services.QuestError as e:
        ctx = {
            "club": club,
            "quest": quest,
            "character": character,
            "turnin_rows": turnin_rows,
            "blocked_reason": str(e),
        }
        html = render_to_string("quests/play/_turn_in_card.html", ctx, request=request)
        response = HttpResponse(html)
        response.status_code = 400
        return response

    # Success - return 204 with HX-Trigger to close modal, show toast, refresh dashboard
    return hx_response(
        trigger={
            "appModalClose": True,
            "toast": {"message": "Quest turned in successfully.", "type": "success"},
            "dashboardRefresh": True,
        }
    )


def _missing_text(missing):
    return "Missing " + ", ".join(f"{n} x {item}" for item, n in missing) + "."
