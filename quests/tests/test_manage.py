from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from items.models import Item
from quests.models import Quest, QuestCompletion, QuestRequirement, QuestReward

TODAY = timezone.localdate


def _post(reqs=(), rews=(), **fields):
    """reqs: (item_id, qty). rews: dict of rew-row fields (item, quantity, pp, gp, sp, cp)."""
    data = {"name": "Test quest", "description": "d", **fields}
    data = {k: ("" if v is None else v) for k, v in data.items()}
    data.update({"req-TOTAL_FORMS": len(reqs), "req-INITIAL_FORMS": 0})
    data.update({"rew-TOTAL_FORMS": len(rews), "rew-INITIAL_FORMS": 0})
    for i, (item, qty) in enumerate(reqs):
        data[f"req-{i}-item"] = item.pk if item else ""
        data[f"req-{i}-quantity"] = qty
    for i, row in enumerate(rews):
        item = row.get("item")
        data[f"rew-{i}-item"] = item.pk if item else ""
        data[f"rew-{i}-quantity"] = row.get("quantity", 0)
        for suffix in ("pp", "gp", "sp", "cp"):
            data[f"rew-{i}-coins_{suffix}"] = row.get(suffix, "")
    return data


def _url(name, club, *args):
    return reverse(f"quests:{name}", args=[club.slug, *args])


@pytest.fixture
def admin_client(login, club_admin):
    return login(club_admin)


def _create(client, club, **kw):
    return client.post(_url("create", club), _post(**kw))


def _all_errors(resp):
    ctx = resp.context
    if not ctx:
        return None
    return ctx["form"].errors, ctx["reqs"].errors, ctx["rews"].errors, ctx["reqs"].non_form_errors()


@pytest.mark.story("Q1")
def test_create_with_mixed_rewards(admin_client, club, item, reward_item):
    other = Item.objects.create(club=club, name="Pelt", value_cp=10)
    resp = _create(
        admin_client,
        club,
        reqs=[(item, 2), (other, 1)],
        rews=[
            {"item": reward_item, "quantity": 1},
            {"pp": 1, "gp": 2, "sp": 3, "cp": 4},
            {"item": other, "quantity": 2, "gp": 1},
        ],
    )
    assert resp.status_code == 302, _all_errors(resp)
    q = Quest.objects.get(name="Test quest")
    assert q.club == club
    assert q.requirements.count() == 2
    rewards = list(q.rewards.order_by("pk"))
    assert (rewards[0].item, rewards[0].quantity, rewards[0].coins) == (reward_item, 1, 0)
    assert (rewards[1].item, rewards[1].quantity, rewards[1].coins) == (None, 0, 1234)
    assert (rewards[2].item, rewards[2].quantity, rewards[2].coins) == (other, 2, 100)


@pytest.mark.story("Q1")
@pytest.mark.parametrize("who", ["player", "game_master"])
def test_non_admins_get_403(request, login, club, quest, who):
    client = login(request.getfixturevalue(who))
    assert client.get(_url("manage", club)).status_code == 403
    assert client.get(_url("create", club)).status_code == 403
    assert client.post(_url("create", club), {}).status_code == 403
    assert client.get(_url("edit", club, quest.pk)).status_code == 403
    assert client.post(_url("delete", club, quest.pk)).status_code == 403
    assert Quest.objects.filter(pk=quest.pk).exists()


@pytest.mark.story("Q1")
def test_no_requirement(admin_client, club, item):
    resp = _create(admin_client, club, rews=[{"cp": 5}])
    assert resp.status_code == 200
    assert "Add at least one requirement." in str(resp.context["reqs"].non_form_errors())
    assert not Quest.objects.exists()


@pytest.mark.story("Q1")
def test_no_reward(admin_client, club, item):
    resp = _create(admin_client, club, reqs=[(item, 1)])
    assert resp.status_code == 200
    assert "Add at least one reward." in str(resp.context["rews"].non_form_errors())
    assert not Quest.objects.exists()


@pytest.mark.story("Q1")
def test_requirement_quantity_zero(admin_client, club, item):
    resp = _create(admin_client, club, reqs=[(item, 0)], rews=[{"cp": 5}])
    assert resp.status_code == 200
    assert not Quest.objects.exists()


@pytest.mark.story("Q1")
def test_duplicate_requirement_items(admin_client, club, item):
    resp = _create(admin_client, club, reqs=[(item, 1), (item, 2)], rews=[{"cp": 5}])
    assert resp.status_code == 200
    assert "only once" in str(resp.context["reqs"].non_form_errors())


@pytest.mark.story("Q1")
def test_empty_reward_row_rejected(admin_client, club, item):
    resp = _create(admin_client, club, reqs=[(item, 1)], rews=[{"cp": 5}, {"quantity": 3}])
    assert resp.status_code == 200
    assert "Give an item or coins." in str(resp.context["rews"].forms[1].errors)


@pytest.mark.story("Q1")
def test_reward_item_quantity_zero(admin_client, club, item, reward_item):
    resp = _create(
        admin_client, club, reqs=[(item, 1)], rews=[{"item": reward_item, "quantity": 0}]
    )
    assert resp.status_code == 200
    assert "Quantity must be 1 or more." in str(resp.context["rews"].forms[0].errors)


@pytest.mark.story("Q1")
def test_untouched_extra_reward_row_is_ignored(admin_client, club, item):
    data = _post(reqs=[(item, 1)], rews=[{"cp": 5}, {}])
    resp = admin_client.post(_url("create", club), data)
    assert resp.status_code == 302, _all_errors(resp)
    assert Quest.objects.get().rewards.count() == 1


@pytest.mark.story("Q1")
def test_delete_without_completions(admin_client, club, quest):
    resp = admin_client.post(_url("delete", club, quest.pk))
    assert resp.status_code == 302
    assert not Quest.objects.filter(pk=quest.pk).exists()


@pytest.mark.story("Q1")
def test_delete_with_completions_refused(admin_client, club, quest, character):
    QuestCompletion.objects.create(quest=quest, character=character, date=TODAY())
    resp = admin_client.post(_url("delete", club, quest.pk), follow=True)
    assert Quest.objects.filter(pk=quest.pk).exists()
    assert "has completions" in resp.content.decode()


@pytest.mark.story("Q1")
def test_retired_item_not_offered_and_rejected(admin_client, club, item):
    retired = Item.objects.create(club=club, name="Old", value_cp=1, retired=True)
    resp = admin_client.get(_url("create", club))
    choices = [c[0].value for c in resp.context["reqs"].forms[0].fields["item"].choices if c[0]]
    assert item.pk in choices and retired.pk not in choices
    resp = _create(admin_client, club, reqs=[(retired, 1)], rews=[{"cp": 5}])
    assert resp.status_code == 200
    assert not Quest.objects.exists()


@pytest.mark.story("Q1")
def test_existing_retired_item_kept_on_edit(admin_client, club, quest, item):
    item.retired = True
    item.save()
    req = quest.requirements.get()
    rews = list(quest.rewards.order_by("pk"))
    data = {
        "name": "Renamed",
        "description": "",
        "req-TOTAL_FORMS": 1,
        "req-INITIAL_FORMS": 1,
        "req-0-id": req.pk,
        "req-0-quest": quest.pk,
        "req-0-item": item.pk,
        "req-0-quantity": 3,
        "rew-TOTAL_FORMS": len(rews),
        "rew-INITIAL_FORMS": len(rews),
    }
    for i, r in enumerate(rews):
        data[f"rew-{i}-id"] = r.pk
        data[f"rew-{i}-quest"] = quest.pk
        data[f"rew-{i}-item"] = r.item_id or ""
        data[f"rew-{i}-quantity"] = r.quantity
        data[f"rew-{i}-coins_pp"] = "1" if r.coins else ""
    resp = admin_client.post(_url("edit", club, quest.pk), data)
    assert resp.status_code == 302, resp.context["reqs"].errors if resp.context else ""
    assert QuestRequirement.objects.get(pk=req.pk).quantity == 3
    quest.refresh_from_db()
    assert quest.name == "Renamed"
    assert QuestReward.objects.filter(quest=quest, coins=1000).exists()


@pytest.mark.story("Q2")
def test_future_quest_listed_upcoming(admin_client, club, item):
    start = TODAY() + timedelta(days=5)
    resp = _create(
        admin_client,
        club,
        reqs=[(item, 1)],
        rews=[{"cp": 5}],
        start_date=start.isoformat(),
    )
    assert resp.status_code == 302
    html = admin_client.get(_url("manage", club)).content.decode()
    assert "upcoming" in html


@pytest.mark.story("Q2")
def test_start_after_end_rejected(admin_client, club, item):
    resp = _create(
        admin_client,
        club,
        reqs=[(item, 1)],
        rews=[{"cp": 5}],
        start_date="2026-06-10",
        end_date="2026-06-01",
    )
    assert resp.status_code == 200
    assert "end_date" in resp.context["form"].errors
    assert not Quest.objects.exists()


@pytest.mark.story("Q2")
def test_list_labels(admin_client, club, quest, upcoming_quest, ended_quest):
    resp = admin_client.get(_url("manage", club))
    status = {r["quest"].name: r["status"] for r in resp.context["rows"]}
    assert status == {
        "Pelts for the Tanner": "live",
        "Upcoming quest": "upcoming",
        "Ended quest": "ended",
    }


@pytest.mark.story("Q3")
def test_limits_save_and_show(admin_client, club, item):
    resp = _create(
        admin_client,
        club,
        reqs=[(item, 1)],
        rews=[{"cp": 5}],
        max_completions=5,
        max_per_character=2,
    )
    assert resp.status_code == 302
    q = Quest.objects.get()
    assert (q.max_completions, q.max_per_character) == (5, 2)
    html = admin_client.get(_url("edit", club, q.pk)).content.decode()
    assert 'value="5"' in html and 'value="2"' in html


@pytest.mark.story("Q3")
def test_empty_limits_mean_no_limit(admin_client, club, item):
    _create(admin_client, club, reqs=[(item, 1)], rews=[{"cp": 5}])
    q = Quest.objects.get()
    assert q.max_completions is None and q.max_per_character is None
    assert "No limit" in admin_client.get(_url("manage", club)).content.decode()


@pytest.mark.story("Q3")
@pytest.mark.parametrize("field", ["max_completions", "max_per_character"])
def test_zero_limit_rejected(admin_client, club, item, field):
    resp = _create(admin_client, club, reqs=[(item, 1)], rews=[{"cp": 5}], **{field: 0})
    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert not Quest.objects.exists()


@pytest.mark.story("Q3")
def test_full_status(admin_client, club, limited_quest, character):
    QuestCompletion.objects.create(quest=limited_quest, character=character, date=TODAY())
    resp = admin_client.get(_url("manage", club))
    row = resp.context["rows"][0]
    assert row["status"] == "full" and row["count"] == 1


@pytest.mark.story("Q4")
def test_list_only_own_club(admin_client, club, quest, other_club_quest):
    resp = admin_client.get(_url("manage", club))
    names = [r["quest"].name for r in resp.context["rows"]]
    assert names == [quest.name]


@pytest.mark.story("Q4")
def test_other_club_quest_404(admin_client, club, other_club_quest):
    assert admin_client.get(_url("edit", club, other_club_quest.pk)).status_code == 404
    assert admin_client.post(_url("delete", club, other_club_quest.pk)).status_code == 404
    assert Quest.objects.filter(pk=other_club_quest.pk).exists()


@pytest.mark.story("Q4")
def test_other_club_items_not_offered_or_accepted(admin_client, club, item, other_club_quest):
    foreign = other_club_quest.requirements.get().item
    resp = admin_client.get(_url("create", club))
    for formset in (resp.context["reqs"], resp.context["rews"]):
        choices = [c[0].value for c in formset.forms[0].fields["item"].choices if c[0]]
        assert foreign.pk not in choices
    resp = _create(admin_client, club, reqs=[(foreign, 1)], rews=[{"cp": 5}])
    assert resp.status_code == 200
    resp = _create(admin_client, club, reqs=[(item, 1)], rews=[{"item": foreign, "quantity": 1}])
    assert resp.status_code == 200
    assert not Quest.objects.filter(name="Test quest").exists()
