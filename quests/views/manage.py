from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404
from quests.forms import QuestForm, RequirementFormSet, RewardFormSet
from quests.models import Quest


@club_admin_required
def quest_list(request, club_slug):
    today = timezone.localdate()
    quests = (
        Quest.objects.for_club(request.club)
        .annotate(completion_count=Count("completions"))
        .prefetch_related("rewards__item", "requirements__item")
    )
    rows = []
    for quest in quests:
        status = quest.status_on(today)
        if (
            status == "live"
            and quest.max_completions
            and quest.completion_count >= quest.max_completions
        ):
            status = "full"
        rows.append({"quest": quest, "status": status, "count": quest.completion_count})
    return render(request, "quests/manage/list.html", {"rows": rows})


def _form_view(request, quest):
    club = request.club
    instance = quest or Quest(club=club)
    kwargs = {"instance": instance, "form_kwargs": {"club": club}}
    data = request.POST if request.method == "POST" else None
    form = QuestForm(data, instance=instance, club=club)
    reqs = RequirementFormSet(data, prefix="req", **kwargs)
    rews = RewardFormSet(data, prefix="rew", **kwargs)
    if request.method == "POST":
        valid = [form.is_valid(), reqs.is_valid(), rews.is_valid()]
        if all(valid):
            with transaction.atomic():
                saved = form.save()
                reqs.instance = saved
                rews.instance = saved
                reqs.save()
                rews.save()
            messages.success(request, f"Saved quest {saved.name}.")
            return redirect("quests:manage", club_slug=club.slug)
    return render(
        request,
        "quests/manage/form.html",
        {"form": form, "reqs": reqs, "rews": rews, "quest": quest},
    )


@club_admin_required
def quest_create(request, club_slug):
    return _form_view(request, None)


@club_admin_required
def quest_edit(request, club_slug, pk):
    return _form_view(request, club_get_object_or_404(request, Quest, pk=pk))


@club_admin_required
@require_POST
def quest_delete(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    if quest.completions.exists():
        messages.error(request, f"{quest.name} has completions. Set an end date instead.")
    else:
        quest.delete()
        messages.success(request, f"Deleted quest {quest.name}.")
    return redirect("quests:manage", club_slug=request.club.slug)
