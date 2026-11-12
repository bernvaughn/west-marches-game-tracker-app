from django.contrib import messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required, is_club_admin
from accounts.scoping import club_get_object_or_404
from ledger.services import InsufficientItems
from player_characters.selection import selected_character
from quests import services
from quests.models import Quest


def _is_admin(request):
    return request.user.is_superuser or is_club_admin(request.user, request.club)


@club_member_required
def index(request, club_slug):
    quests = list(
        Quest.objects.for_club(request.club)
        .live_on(timezone.localdate())
        .prefetch_related("requirements__item", "rewards__item")
        .annotate(done=Count("completions"))
    )
    for q in quests:
        q.left = None if q.max_completions is None else max(0, q.max_completions - q.done)
    return render(request, "quests/index.html", {"quests": quests, "is_admin": _is_admin(request)})


@club_member_required
def detail(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    if not quest.is_live_on(timezone.localdate()):
        raise Http404
    character = selected_character(request)
    row = None
    if character is not None:
        missing = services.missing_items(quest, character)
        left = services.character_completions_left(quest, character)
        row = {
            "missing": missing,
            "limit_reached": left == 0,
            "ready": not missing and left != 0,
        }
    return render(
        request,
        "quests/play/detail.html",
        {
            "quest": quest,
            "requirements": quest.requirements.select_related("item"),
            "rewards": quest.rewards.select_related("item"),
            "character": character,
            "row": row,
            "club_left": services.completions_left(quest),
            "is_admin": _is_admin(request),
        },
    )


def _missing_text(missing):
    return "Missing " + ", ".join(f"{n} x {item}" for item, n in missing) + "."


@club_member_required
@require_POST
def turn_in(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    detail_url = redirect("quests:detail", club_slug=request.club.slug, pk=pk)
    character = selected_character(request)
    if character is None:
        messages.error(request, "You have no character in this club.")
        return detail_url
    try:
        services.turn_in(quest, character, request.user)
    except InsufficientItems:
        messages.error(request, _missing_text(services.missing_items(quest, character)))
    except services.QuestNotLive as e:
        messages.error(request, str(e))
        return redirect("quests:index", club_slug=request.club.slug)
    except services.QuestError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"{character} completed {quest.name}.")
    return detail_url
