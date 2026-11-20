"""Tests for starting equipment entry management views."""

import pytest
from django.urls import reverse

from character_options.models import CharacterClass
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
    StartingEquipmentLevelCoins,
)

pytestmark = [pytest.mark.django_db]


def url(name, club, template_pk=None, pk=None):
    args = [club.slug]
    if template_pk is not None:
        args.append(template_pk)
    if pk is not None:
        args.append(pk)
    return reverse(f"starting_equipment:{name}", args=args)


def formset_data(total=1, initial=0, **extra):
    data = {
        "lines-TOTAL_FORMS": str(total),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    for key, value in extra.items():
        data[f"lines-0-{key}"] = str(value)
    return data


# ---------------------------------------------------------------------------
# Class entries
# ---------------------------------------------------------------------------


class TestClassEntry:
    def test_list(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("class_entry_list", club, template.pk))
        assert r.status_code == 200

    def test_create(self, login, club_admin, club, template, class_item, class_option_fighter):
        c = login(club_admin)
        # Reuse the seeded Paladin class option to test creation
        paladin_class = CharacterClass.objects.get(club=club, name="Paladin")
        data = {
            "class_option": str(paladin_class.pk),
            "min_level": 1,
            "max_level": 20,
            "coins_cp": 500,
            **formset_data(item=class_item.pk, quantity="1", choice_group=""),
        }
        r = c.post(url("class_entry_create", club, template.pk), data)
        assert r.status_code == 302
        entry = StartingEquipmentClassEntry.objects.get(template=template, char_class="Paladin")
        assert entry.coins_cp == 500
        assert entry.class_option == paladin_class
        assert entry.lines.filter(item=class_item, quantity=1).exists()

    def test_edit(self, login, club_admin, club, template, class_item, class_option_fighter):
        entry = StartingEquipmentClassEntry.objects.create(
            template=template,
            char_class="Ranger",
            class_option=class_option_fighter,
            min_level=1,
            max_level=20,
            coins_cp=100,
        )
        c = login(club_admin)
        r = c.get(url("class_entry_edit", club, template.pk, entry.pk))
        assert r.status_code == 200
        data = {
            "class_option": str(class_option_fighter.pk),
            "min_level": 3,
            "max_level": 10,
            "coins_cp": 750,
            **formset_data(item=class_item.pk, quantity="2", choice_group=""),
        }
        r = c.post(url("class_entry_edit", club, template.pk, entry.pk), data)
        assert r.status_code == 302
        entry.refresh_from_db()
        assert entry.min_level == 3 and entry.max_level == 10 and entry.coins_cp == 750
        assert entry.class_option == class_option_fighter
        assert entry.lines.filter(item=class_item, quantity=2).exists()

    def test_delete(self, login, club_admin, club, template):
        entry = StartingEquipmentClassEntry.objects.create(
            template=template, char_class="Bard", min_level=1, max_level=20, coins_cp=50
        )
        c = login(club_admin)
        r = c.post(url("class_entry_delete", club, template.pk, entry.pk))
        assert r.status_code == 302
        assert not StartingEquipmentClassEntry.objects.filter(pk=entry.pk).exists()

    def test_form_renders_class_option_picker(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("class_entry_create", club, template.pk))
        assert r.status_code == 200
        html = r.content.decode()
        assert "<select" in html
        assert 'name="class_option"' in html


# ---------------------------------------------------------------------------
# Background entries
# ---------------------------------------------------------------------------


class TestBackgroundEntry:
    def test_list(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("background_entry_list", club, template.pk))
        assert r.status_code == 200

    def test_create(self, login, club_admin, club, template, class_item, bg_option_acolyte):
        c = login(club_admin)
        data = {
            "background_option": str(bg_option_acolyte.pk),
            "coins_cp": 300,
            **formset_data(item=class_item.pk, quantity="1", choice_group=""),
        }
        r = c.post(url("background_entry_create", club, template.pk), data)
        assert r.status_code == 302
        entry = StartingEquipmentBackgroundEntry.objects.get(
            template=template, background="Acolyte"
        )
        assert entry.coins_cp == 300
        assert entry.background_option == bg_option_acolyte
        assert entry.lines.filter(item=class_item, quantity=1).exists()

    def test_edit(self, login, club_admin, club, template, class_item, bg_option_acolyte):
        entry = StartingEquipmentBackgroundEntry.objects.create(
            template=template, background="Sage", background_option=bg_option_acolyte, coins_cp=100
        )
        c = login(club_admin)
        data = {
            "background_option": str(bg_option_acolyte.pk),
            "coins_cp": 400,
            **formset_data(item=class_item.pk, quantity="3", choice_group=""),
        }
        r = c.post(url("background_entry_edit", club, template.pk, entry.pk), data)
        assert r.status_code == 302
        entry.refresh_from_db()
        assert entry.coins_cp == 400
        assert entry.background_option == bg_option_acolyte
        assert entry.lines.filter(item=class_item, quantity=3).exists()

    def test_delete(self, login, club_admin, club, template):
        entry = StartingEquipmentBackgroundEntry.objects.create(
            template=template, background="Sage", coins_cp=100
        )
        c = login(club_admin)
        r = c.post(url("background_entry_delete", club, template.pk, entry.pk))
        assert r.status_code == 302
        assert not StartingEquipmentBackgroundEntry.objects.filter(pk=entry.pk).exists()

    def test_form_renders_background_option_picker(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("background_entry_create", club, template.pk))
        assert r.status_code == 200
        html = r.content.decode()
        assert "<select" in html
        assert 'name="background_option"' in html


# ---------------------------------------------------------------------------
# Level coins
# ---------------------------------------------------------------------------


class TestLevelCoins:
    def test_list(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("level_coins_list", club, template.pk))
        assert r.status_code == 200

    def test_create(self, login, club_admin, club, template):
        c = login(club_admin)
        data = {"level": "3", "coins_cp": "900"}
        r = c.post(url("level_coins_create", club, template.pk), data)
        assert r.status_code == 302
        assert StartingEquipmentLevelCoins.objects.get(template=template, level=3, coins_cp=900)

    def test_edit(self, login, club_admin, club, template):
        entry = StartingEquipmentLevelCoins.objects.create(template=template, level=3, coins_cp=900)
        c = login(club_admin)
        data = {"level": "5", "coins_cp": "2500"}
        r = c.post(url("level_coins_edit", club, template.pk, entry.pk), data)
        assert r.status_code == 302
        entry.refresh_from_db()
        assert entry.level == 5 and entry.coins_cp == 2500

    def test_delete(self, login, club_admin, club, template):
        entry = StartingEquipmentLevelCoins.objects.create(template=template, level=3, coins_cp=900)
        c = login(club_admin)
        r = c.post(url("level_coins_delete", club, template.pk, entry.pk))
        assert r.status_code == 302
        assert not StartingEquipmentLevelCoins.objects.filter(pk=entry.pk).exists()


# ---------------------------------------------------------------------------
# Magic item options
# ---------------------------------------------------------------------------


class TestMagicOption:
    def test_list(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("magic_option_list", club, template.pk))
        assert r.status_code == 200

    def test_create(self, login, club_admin, club, template, magic_item):
        c = login(club_admin)
        data = {"item": magic_item.pk, "max_per_character": "2", "notes": "Level 5+ only"}
        r = c.post(url("magic_option_create", club, template.pk), data)
        assert r.status_code == 302
        assert MagicItemStartingOption.objects.get(
            template=template, item=magic_item, max_per_character=2, notes="Level 5+ only"
        )

    def test_edit(self, login, club_admin, club, template, magic_item, class_item):
        entry = MagicItemStartingOption.objects.create(
            template=template, item=magic_item, max_per_character=1, notes="old"
        )
        c = login(club_admin)
        data = {"item": class_item.pk, "max_per_character": "3", "notes": "new"}
        r = c.post(url("magic_option_edit", club, template.pk, entry.pk), data)
        assert r.status_code == 302
        entry.refresh_from_db()
        assert entry.item_id == class_item.pk
        assert entry.max_per_character == 3
        assert entry.notes == "new"

    def test_delete(self, login, club_admin, club, template, magic_item):
        entry = MagicItemStartingOption.objects.create(
            template=template, item=magic_item, max_per_character=1
        )
        c = login(club_admin)
        r = c.post(url("magic_option_delete", club, template.pk, entry.pk))
        assert r.status_code == 302
        assert not MagicItemStartingOption.objects.filter(pk=entry.pk).exists()

    def test_form_renders_item_picker(self, login, club_admin, club, template):
        c = login(club_admin)
        r = c.get(url("magic_option_create", club, template.pk))
        assert r.status_code == 200
        html = r.content.decode()
        assert "<select" in html
        assert "Browse catalogue" in html


# ---------------------------------------------------------------------------
# Permissions: non-admin users get 403 on every entry page
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "class_entry_list",
        "class_entry_create",
        "background_entry_list",
        "background_entry_create",
        "level_coins_list",
        "level_coins_create",
        "magic_option_list",
        "magic_option_create",
    ],
)
def test_non_admin_get_403(request, login, club, template, name):
    c = login(request.getfixturevalue("player"))
    assert c.get(url(name, club, template.pk)).status_code == 403


@pytest.mark.parametrize(
    "name",
    [
        "class_entry_create",
        "background_entry_create",
        "level_coins_create",
        "magic_option_create",
    ],
)
def test_non_admin_post_403(request, login, club, template, name):
    c = login(request.getfixturevalue("player"))
    assert c.post(url(name, club, template.pk), {}).status_code == 403


# ---------------------------------------------------------------------------
# Cross-club isolation: another club's template/entry is 404
# ---------------------------------------------------------------------------


def test_cross_club_404(login, club_admin, club, other_club):
    from starting_equipment.models import StartingEquipmentTemplate

    foreign = StartingEquipmentTemplate.objects.create(
        club=other_club, name="Foreign", is_active=True
    )
    c = login(club_admin)
    for name in (
        "class_entry_list",
        "class_entry_create",
        "background_entry_list",
        "level_coins_list",
        "magic_option_list",
    ):
        assert c.get(url(name, club, foreign.pk)).status_code == 404
    # An entry belonging to another club's template is 404 too.
    entry = StartingEquipmentClassEntry.objects.create(
        template=foreign, char_class="Fighter", min_level=1, max_level=20, coins_cp=50
    )
    assert c.get(url("class_entry_edit", club, foreign.pk, entry.pk)).status_code == 404
    assert c.post(url("class_entry_delete", club, foreign.pk, entry.pk)).status_code == 404
