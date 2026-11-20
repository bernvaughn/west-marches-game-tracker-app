"""Tests for the starting equipment choices step."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import Membership, User
from character_options.models import Background, CharacterClass
from items.models import Item
from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentTemplate,
)
from starting_equipment.services import (
    AlreadyClaimed,
    InvalidChoices,
    apply_starting_equipment,
    claim_starting_equipment,
    get_choice_groups,
)

pytestmark = [pytest.mark.django_db]


def choices_url(club, character):
    return reverse(
        "starting_equipment:choices",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def reveal_url(club, character):
    return reverse(
        "characters:starting_reveal",
        kwargs={"club_slug": club.slug, "pk": character.pk},
    )


def create_url(club):
    return reverse("characters:create", kwargs={"club_slug": club.slug})


def claim_url(club, character):
    return reverse(
        "starting_equipment:claim",
        kwargs={"club_slug": club.slug, "character_pk": character.pk},
    )


def flash_messages(response):
    """Return the list of flash message strings queued on the response's request."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def make_template(club, *, is_active=True):
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=is_active
    )


def make_class_entry(template, *, class_option, coins_cp=1000):
    return StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=class_option,
        min_level=1,
        max_level=20,
        coins_cp=coins_cp,
    )


def make_class_line(class_entry, item, *, is_choice=False, choice_group="", quantity=1):
    return StartingEquipmentClassLine.objects.create(
        class_entry=class_entry,
        item=item,
        quantity=quantity,
        is_choice=is_choice,
        choice_group=choice_group,
    )


def make_bg_entry(template, *, background_option, coins_cp=500):
    return StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=background_option,
        coins_cp=coins_cp,
    )


def make_bg_line(bg_entry, item, *, is_choice=False, choice_group="", quantity=1):
    return StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry,
        item=item,
        quantity=quantity,
        is_choice=is_choice,
        choice_group=choice_group,
    )


@pytest.fixture
def active_template(club):
    return make_template(club, is_active=True)


@pytest.fixture
def class_option_fighter(club):
    return CharacterClass.objects.get(club=club, name="Fighter")


@pytest.fixture
def bg_option_acolyte(club):
    return Background.objects.get(club=club, name="Acolyte")


@pytest.fixture
def character_with_choices(club, player, active_template, class_option_fighter, bg_option_acolyte):
    """Character with class and background choice groups."""
    owner, _ = Membership.objects.get_or_create(user=player, club=club)
    longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
    battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
    class_entry = make_class_entry(
        active_template, class_option=class_option_fighter, coins_cp=1000
    )
    make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
    make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
    holy_symbol = Item.objects.create(club=club, name="Holy Symbol", value_cp=500)
    prayer_book = Item.objects.create(club=club, name="Prayer Book", value_cp=500)
    bg_entry = make_bg_entry(active_template, background_option=bg_option_acolyte, coins_cp=500)
    make_bg_line(bg_entry, holy_symbol, is_choice=True, choice_group="holy_item")
    make_bg_line(bg_entry, prayer_book, is_choice=True, choice_group="holy_item")
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Test Fighter",
        char_class="Fighter",
        class_option=class_option_fighter,
        background="Acolyte",
        background_option=bg_option_acolyte,
        level=1,
    )


# ---------------------------------------------------------------------------
# get_choice_groups
# ---------------------------------------------------------------------------


class TestGetChoiceGroups:
    def test_returns_groups_for_class_and_background(
        self,
        club,
        active_template,
        class_option_fighter,
        bg_option_acolyte,
    ):
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
        class_entry = make_class_entry(active_template, class_option=class_option_fighter)
        make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
        make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
        holy_symbol = Item.objects.create(club=club, name="Holy Symbol", value_cp=500)
        prayer_book = Item.objects.create(club=club, name="Prayer Book", value_cp=500)
        bg_entry = make_bg_entry(active_template, background_option=bg_option_acolyte)
        make_bg_line(bg_entry, holy_symbol, is_choice=True, choice_group="holy_item")
        make_bg_line(bg_entry, prayer_book, is_choice=True, choice_group="holy_item")

        user = User.objects.create_user("owner@example.com", password="pw", display_name="Owner")
        owner = Membership.objects.create(user=user, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="Test Fighter",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Acolyte",
            background_option=bg_option_acolyte,
            level=1,
        )

        groups = get_choice_groups(character, active_template)
        assert len(groups) == 2
        keys = [g.key for g in groups]
        assert "class:weapon" in keys
        assert "background:holy_item" in keys
        weapon = next(g for g in groups if g.slug == "weapon")
        assert {o.line_id for o in weapon.options} == {
            StartingEquipmentClassLine.objects.get(item=longsword).id,
            StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        holy = next(g for g in groups if g.slug == "holy_item")
        assert [o.line_id for o in holy.options] == [
            StartingEquipmentBackgroundLine.objects.get(item=holy_symbol).id,
            StartingEquipmentBackgroundLine.objects.get(item=prayer_book).id,
        ]

    def test_skips_lines_without_a_choice_group(
        self, club, active_template, class_option_fighter, bg_option_acolyte
    ):
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        class_entry = make_class_entry(active_template, class_option=class_option_fighter)
        make_class_line(class_entry, longsword, is_choice=False)
        make_class_line(class_entry, longsword, is_choice=True, choice_group="")

        user = User.objects.create_user("owner@example.com", password="pw", display_name="Owner")
        owner = Membership.objects.create(user=user, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="Test Fighter",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Acolyte",
            background_option=bg_option_acolyte,
            level=1,
        )
        assert get_choice_groups(character, active_template) == []

    def test_returns_empty_for_none_template(self, club, class_option_fighter, bg_option_acolyte):
        user = User.objects.create_user("owner@example.com", password="pw", display_name="Owner")
        owner = Membership.objects.create(user=user, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="Test Fighter",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Acolyte",
            background_option=bg_option_acolyte,
            level=1,
        )
        assert get_choice_groups(character, None) == []


# ---------------------------------------------------------------------------
# apply_starting_equipment(picks=...)
# ---------------------------------------------------------------------------


class TestApplyWithPicks:
    def test_grants_picked_lines_plus_fixed(
        self, club, active_template, class_option_fighter, bg_option_acolyte
    ):
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
        class_entry = make_class_entry(
            active_template, class_option=class_option_fighter, coins_cp=1000
        )
        make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
        make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
        holy_symbol = Item.objects.create(club=club, name="Holy Symbol", value_cp=500)
        prayer_book = Item.objects.create(club=club, name="Prayer Book", value_cp=500)
        bg_entry = make_bg_entry(active_template, background_option=bg_option_acolyte, coins_cp=500)
        make_bg_line(bg_entry, holy_symbol, is_choice=True, choice_group="holy_item")
        make_bg_line(bg_entry, prayer_book, is_choice=True, choice_group="holy_item")

        user = User.objects.create_user("owner@example.com", password="pw", display_name="Owner")
        owner = Membership.objects.create(user=user, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="Test Fighter",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Acolyte",
            background_option=bg_option_acolyte,
            level=1,
        )

        picks = {
            "class:weapon": StartingEquipmentClassLine.objects.get(item=battleaxe).id,
            "background:holy_item": StartingEquipmentBackgroundLine.objects.get(
                item=prayer_book
            ).id,
        }
        result = apply_starting_equipment(character, active_template, None, picks=picks)
        entry = result.entry
        assert entry is not None
        assert entry.note == "Starting equipment"
        item_lines = entry.lines.select_related("item").filter(item__isnull=False)
        names = {(line.item.name, line.quantity) for line in item_lines}
        assert ("Battleaxe", 1) in names
        assert ("Prayer Book", 1) in names
        assert ("Longsword", 1) not in names
        assert ("Holy Symbol", 1) not in names

    def test_invalid_pick_raises(
        self, club, active_template, class_option_fighter, bg_option_acolyte
    ):
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
        class_entry = make_class_entry(active_template, class_option=class_option_fighter)
        make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
        make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
        other_item = Item.objects.create(club=club, name="Other", value_cp=10)
        make_class_line(class_entry, other_item, is_choice=True, choice_group="armor")

        user = User.objects.create_user("owner@example.com", password="pw", display_name="Owner")
        owner = Membership.objects.create(user=user, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="Test Fighter",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Acolyte",
            background_option=bg_option_acolyte,
            level=1,
        )

        with pytest.raises(InvalidChoices):
            apply_starting_equipment(
                character, active_template, None, picks={"class:weapon": other_item.id}
            )


# ---------------------------------------------------------------------------
# Choices view permissions
# ---------------------------------------------------------------------------


class TestChoicesViewPermissions:
    def test_owner_sees_choices(self, club, login, player, character_with_choices):
        client = login(player)
        response = client.get(choices_url(club, character_with_choices))
        assert response.status_code == 200

    def test_club_admin_sees_choices(self, club, login, club_admin, character_with_choices):
        client = login(club_admin)
        response = client.get(choices_url(club, character_with_choices))
        assert response.status_code == 200

    def test_game_master_sees_choices(self, club, login, game_master, character_with_choices):
        client = login(game_master)
        response = client.get(choices_url(club, character_with_choices))
        assert response.status_code == 200

    def test_other_member_gets_404(self, club, login, other_player, character_with_choices):
        client = login(other_player)
        response = client.get(choices_url(club, character_with_choices))
        assert response.status_code == 404

    def test_anonymous_redirected_to_login(self, club, client, character_with_choices):
        response = client.get(choices_url(club, character_with_choices))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))


# ---------------------------------------------------------------------------
# Choices view flow
# ---------------------------------------------------------------------------


class TestChoicesViewFlow:
    def test_post_picks_grants_one_entry_redirects_to_reveal(
        self, club, login, player, character_with_choices
    ):
        longsword = Item.objects.get(club=club, name="Longsword")
        battleaxe = Item.objects.get(club=club, name="Battleaxe")
        holy_symbol = Item.objects.get(club=club, name="Holy Symbol")
        prayer_book = Item.objects.get(club=club, name="Prayer Book")
        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        bg_line_ids = {
            holy_symbol: StartingEquipmentBackgroundLine.objects.get(item=holy_symbol).id,
            prayer_book: StartingEquipmentBackgroundLine.objects.get(item=prayer_book).id,
        }
        picks = {
            "g_0": class_line_ids[battleaxe],
            "g_1": bg_line_ids[prayer_book],
        }

        client = login(player)
        response = client.post(
            choices_url(club, character_with_choices),
            picks,
        )
        assert response.status_code == 302
        assert response.url == reveal_url(club, character_with_choices)

        character_with_choices.refresh_from_db()
        assert character_with_choices.starting_equipment_claimed is True

        entries = LedgerEntry.objects.filter(character=character_with_choices)
        assert entries.count() == 1
        entry = entries.first()
        assert entry.note == "Starting equipment"
        item_lines = entry.lines.select_related("item").filter(item__isnull=False)
        names = {(line.item.name, line.quantity) for line in item_lines}
        assert ("Battleaxe", 1) in names
        assert ("Prayer Book", 1) in names
        assert ("Longsword", 1) not in names
        assert ("Holy Symbol", 1) not in names

    def test_missing_pick_returns_200_with_error_no_entry(
        self, club, login, player, character_with_choices
    ):
        longsword = Item.objects.get(club=club, name="Longsword")
        battleaxe = Item.objects.get(club=club, name="Battleaxe")
        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }

        client = login(player)
        response = client.post(
            choices_url(club, character_with_choices),
            {"g_0": class_line_ids[battleaxe]},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Pick one option" in content

        character_with_choices.refresh_from_db()
        assert character_with_choices.starting_equipment_claimed is False
        assert LedgerEntry.objects.filter(character=character_with_choices).count() == 0

    def test_invalid_pick_line_from_another_group(
        self, club, login, player, character_with_choices
    ):
        prayer_book = Item.objects.get(club=club, name="Prayer Book")
        bg_line_ids = {
            prayer_book: StartingEquipmentBackgroundLine.objects.get(item=prayer_book).id,
        }

        client = login(player)
        # g_0 (weapon class group) gets a line id that is not one of its options.
        response = client.post(
            choices_url(club, character_with_choices),
            {"g_0": 999999, "g_1": bg_line_ids[prayer_book]},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Select a valid choice" in content or "Pick one option" in content
        assert LedgerEntry.objects.filter(character=character_with_choices).count() == 0
        character_with_choices.refresh_from_db()
        assert character_with_choices.starting_equipment_claimed is False

    def test_double_submit_grants_once(self, club, login, player, character_with_choices):
        longsword = Item.objects.get(club=club, name="Longsword")
        battleaxe = Item.objects.get(club=club, name="Battleaxe")
        holy_symbol = Item.objects.get(club=club, name="Holy Symbol")
        prayer_book = Item.objects.get(club=club, name="Prayer Book")
        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        bg_line_ids = {
            holy_symbol: StartingEquipmentBackgroundLine.objects.get(item=holy_symbol).id,
            prayer_book: StartingEquipmentBackgroundLine.objects.get(item=prayer_book).id,
        }
        picks = {
            "g_0": class_line_ids[battleaxe],
            "g_1": bg_line_ids[prayer_book],
        }

        client = login(player)
        response1 = client.post(choices_url(club, character_with_choices), picks)
        assert response1.status_code == 302

        response2 = client.post(choices_url(club, character_with_choices), picks)
        assert response2.status_code == 302
        character_with_choices.refresh_from_db()
        assert character_with_choices.starting_equipment_claimed is True
        assert LedgerEntry.objects.filter(character=character_with_choices).count() == 1

    def test_get_after_claim_redirects(self, club, login, player, character_with_choices):
        longsword = Item.objects.get(club=club, name="Longsword")
        battleaxe = Item.objects.get(club=club, name="Battleaxe")
        holy_symbol = Item.objects.get(club=club, name="Holy Symbol")
        prayer_book = Item.objects.get(club=club, name="Prayer Book")
        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        bg_line_ids = {
            holy_symbol: StartingEquipmentBackgroundLine.objects.get(item=holy_symbol).id,
            prayer_book: StartingEquipmentBackgroundLine.objects.get(item=prayer_book).id,
        }
        picks = {
            "g_0": class_line_ids[battleaxe],
            "g_1": bg_line_ids[prayer_book],
        }

        client = login(player)
        client.post(choices_url(club, character_with_choices), picks)

        response = client.get(choices_url(club, character_with_choices))
        assert response.status_code == 302
        assert response.url == detail_url(club, character_with_choices)

    def test_service_double_call_raises_already_claimed(self, club, player, character_with_choices):
        longsword = Item.objects.get(club=club, name="Longsword")
        battleaxe = Item.objects.get(club=club, name="Battleaxe")
        holy_symbol = Item.objects.get(club=club, name="Holy Symbol")
        prayer_book = Item.objects.get(club=club, name="Prayer Book")
        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        bg_line_ids = {
            holy_symbol: StartingEquipmentBackgroundLine.objects.get(item=holy_symbol).id,
            prayer_book: StartingEquipmentBackgroundLine.objects.get(item=prayer_book).id,
        }
        template = StartingEquipmentTemplate.objects.get(club=club, name="Test Template")
        picks = {
            "class:weapon": class_line_ids[battleaxe],
            "background:holy_item": bg_line_ids[prayer_book],
        }

        claim_starting_equipment(character_with_choices, template, None, picks=picks)
        with pytest.raises(AlreadyClaimed):
            claim_starting_equipment(character_with_choices, template, None, picks=picks)


# ---------------------------------------------------------------------------
# Skipped step
# ---------------------------------------------------------------------------


class TestChoicesSkipped:
    def test_get_redirects_to_detail_when_no_groups(
        self, club, login, player, active_template, class_option_fighter, bg_option_acolyte
    ):
        owner = Membership.objects.get(user=player, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="No Choices",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Acolyte",
            background_option=bg_option_acolyte,
            level=1,
        )
        client = login(player)
        response = client.get(choices_url(club, character))
        assert response.status_code == 302
        assert response.url == detail_url(club, character)


# ---------------------------------------------------------------------------
# Leave and finish later
# ---------------------------------------------------------------------------


@pytest.fixture
def unclaimed_character(club, player, active_template, class_option_fighter, bg_option_acolyte):
    longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
    battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
    class_entry = make_class_entry(active_template, class_option=class_option_fighter)
    make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
    make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club,
        owner=owner,
        name="Unclaimed",
        char_class="Fighter",
        class_option=class_option_fighter,
        background="Acolyte",
        background_option=bg_option_acolyte,
        level=1,
    )


class TestLeaveAndFinishLater:
    def test_not_claimed_no_entry_after_create(self, club, login, player, unclaimed_character):
        client = login(player)
        response = client.get(detail_url(club, unclaimed_character))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Choose starting equipment" in content
        assert choices_url(club, unclaimed_character) in content
        assert LedgerEntry.objects.filter(character=unclaimed_character).count() == 0
        unclaimed_character.refresh_from_db()
        assert unclaimed_character.starting_equipment_claimed is False

    def test_claim_post_redirects_to_choices(self, club, login, player, unclaimed_character):
        client = login(player)
        response = client.post(claim_url(club, unclaimed_character), HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response["HX-Redirect"] == choices_url(club, unclaimed_character)

    def test_finishing_from_choices_grants(self, club, login, player, unclaimed_character):
        longsword = Item.objects.get(club=club, name="Longsword")
        battleaxe = Item.objects.get(club=club, name="Battleaxe")
        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        client = login(player)
        response = client.post(
            choices_url(club, unclaimed_character),
            {"g_0": class_line_ids[battleaxe]},
        )
        assert response.status_code == 302
        unclaimed_character.refresh_from_db()
        assert unclaimed_character.starting_equipment_claimed is True
        assert (
            LedgerEntry.objects.filter(
                character=unclaimed_character, note="Starting equipment"
            ).count()
            == 1
        )


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------


class TestChoicesReasons:
    def test_custom_background_shows_reason_on_page_and_after_finish(
        self, club, login, player, active_template, class_option_fighter
    ):
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
        class_entry = make_class_entry(active_template, class_option=class_option_fighter)
        make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
        make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
        owner = Membership.objects.get(user=player, club=club)
        character = Character.objects.create(
            club=club,
            owner=owner,
            name="Custom BG",
            char_class="Fighter",
            class_option=class_option_fighter,
            background="Homebrew Background",
            background_option=None,
            level=1,
        )

        client = login(player)
        response = client.get(choices_url(club, character))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Homebrew Background" in content or "custom value" in content

        class_line_ids = {
            longsword: StartingEquipmentClassLine.objects.get(item=longsword).id,
            battleaxe: StartingEquipmentClassLine.objects.get(item=battleaxe).id,
        }
        response = client.post(
            choices_url(club, character),
            {"g_0": class_line_ids[battleaxe]},
        )
        assert response.status_code == 302
        flashed = " ".join(flash_messages(response))
        assert "custom value" in flashed


# ---------------------------------------------------------------------------
# Create with choices
# ---------------------------------------------------------------------------


class TestCreateWithChoices:
    def test_create_with_choice_groups_redirects_to_choices(
        self, club, login, player, active_template, class_option_fighter, bg_option_acolyte
    ):
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        battleaxe = Item.objects.create(club=club, name="Battleaxe", value_cp=1000)
        class_entry = make_class_entry(active_template, class_option=class_option_fighter)
        make_class_line(class_entry, longsword, is_choice=True, choice_group="weapon")
        make_class_line(class_entry, battleaxe, is_choice=True, choice_group="weapon")
        make_bg_entry(active_template, background_option=bg_option_acolyte)

        client = login(player)
        response = client.post(
            create_url(club),
            {"name": "Aria", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302
        character = Character.objects.get(name="Aria")
        assert response.url == choices_url(club, character)
        assert character.starting_equipment_claimed is False
        assert LedgerEntry.objects.filter(character=character).count() == 0
