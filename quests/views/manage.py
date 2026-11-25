from datetime import date

from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.htmx import hx_response, is_htmx, render_modal_or_page
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


def _date_param(request):
    try:
        return date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return None


def _form_view(request, quest):
    club = request.club
    instance = quest or Quest(club=club)
    initial = {}
    if quest is None and (day := _date_param(request)):
        initial["start_date"] = day
    kwargs = {"instance": instance, "form_kwargs": {"club": club}}
    data = request.POST if request.method == "POST" else None
    form = QuestForm(data, instance=instance, club=club, initial=initial)
    reqs = RequirementFormSet(data, prefix="req", **kwargs)
    rews = RewardFormSet(data, prefix="rew", **kwargs)

    # Compute reward total: sum of item value * quantity for each
    # reward with an item. For stacked items, value_cp is for
    # value_units units, so per-unit value = value_cp / value_units.
    reward_total_cp = 0

    def _item_value_cp(item, quantity):
        if item.is_stacked and item.value_units:
            return (item.value_cp * quantity) // item.value_units
        return item.value_cp * quantity

    if request.method == "POST":
        # Use cleaned_data after validation
        for f in rews.forms:
            cd = getattr(f, "cleaned_data", None)
            if cd and not cd.get("DELETE"):
                item = cd.get("item")
                quantity = cd.get("quantity") or 0
                if item:
                    reward_total_cp += _item_value_cp(item, quantity)
    else:
        # GET request: compute from existing instance
        if quest:
            for reward in quest.rewards.all():
                if reward.item:
                    reward_total_cp += _item_value_cp(reward.item, reward.quantity)

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
            if is_htmx(request):
                return hx_response(trigger={"appModalClose": True, "agendaChanged": True})
            return redirect("quests:manage", club_slug=club.slug)
    return render_modal_or_page(
        request,
        "quests/manage/_form_modal.html",
        "quests/manage/form.html",
        {
            "form": form,
            "reqs": reqs,
            "rews": rews,
            "quest": quest,
            "reward_total_cp": reward_total_cp,
        },
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
