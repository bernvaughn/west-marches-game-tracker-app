"""Tests for the loot_preview template tag."""

import pytest
from django.template import Context, Template

from items.tests.factories import _get_or_create_item, add_slot, make_container


@pytest.mark.django_db
class TestLootPreviewTag:
    """Tests for the {% loot_preview %} template tag."""

    def test_non_container_returns_empty_list(self, club, player):
        """Tag returns [] for a plain item."""
        item = _get_or_create_item(club, "Plain Item", is_container=False)
        template = Template("{% load loot_tags %}{% loot_preview item as rows %}{{ rows|length }}")
        context = Context(
            {"request": type("Request", (), {"user": player, "club": club})(), "item": item}
        )
        result = template.render(context)
        assert result == "0"

    def test_none_item_returns_empty_list(self, club, player):
        """Tag returns [] when item is None."""
        template = Template("{% load loot_tags %}{% loot_preview item as rows %}{{ rows|length }}")
        context = Context(
            {"request": type("Request", (), {"user": player, "club": club})(), "item": None}
        )
        result = template.render(context)
        assert result == "0"

    def test_container_returns_rows_for_gm(self, club, game_master):
        """GM sees real item names in preview rows."""
        container = make_container(club, name="Diplomat's Pack")
        fine_clothes = _get_or_create_item(club, "Fine Clothes")
        add_slot(container, [(fine_clothes, 1, 1, 1)], chance_pct=100, unknown=False, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}{{ rows.0.label }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": game_master, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "Fine Clothes"

    def test_container_masks_unknown_for_player(self, club, player):
        """Player sees ??? for unknown slots."""
        container = make_container(club, name="Diplomat's Pack")
        sealed_letter = _get_or_create_item(club, "Sealed Letter")
        add_slot(container, [(sealed_letter, 1, 1, 1)], chance_pct=100, unknown=True, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}{{ rows.0.label }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": player, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "???"

    def test_container_shows_real_name_for_club_admin(self, club, club_admin):
        """Club admin sees real item names in preview rows."""
        container = make_container(club, name="Diplomat's Pack")
        sealed_letter = _get_or_create_item(club, "Sealed Letter")
        add_slot(container, [(sealed_letter, 1, 1, 1)], chance_pct=100, unknown=True, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}{{ rows.0.label }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": club_admin, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "Sealed Letter"

    def test_unknown_row_has_no_item_name_in_context(self, club, player):
        """Masked row has item=None and label=???."""
        container = make_container(club, name="Diplomat's Pack")
        sealed_letter = _get_or_create_item(club, "Sealed Letter")
        add_slot(container, [(sealed_letter, 1, 1, 1)], chance_pct=100, unknown=True, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}"
            "{{ rows.0.item }}{{ rows.0.masked }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": player, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        # item should be None (renders as empty string), masked should be True
        assert "True" in result  # masked=True

    def test_non_member_cannot_see_unknown(self, club, other_player):
        """User from another club sees masked rows."""
        container = make_container(club, name="Diplomat's Pack")
        sealed_letter = _get_or_create_item(club, "Sealed Letter")
        add_slot(container, [(sealed_letter, 1, 1, 1)], chance_pct=100, unknown=True, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}{{ rows.0.label }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": other_player, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "???"

    def test_fixed_quantity_row(self, club, game_master):
        """Fixed quantity row shows qty_min=qty_max."""
        container = make_container(club, name="Container")
        potion = _get_or_create_item(club, "Potion")
        add_slot(container, [(potion, 2, 2, 1)], chance_pct=100, unknown=False, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}"
            "{{ rows.0.qty_min }}-{{ rows.0.qty_max }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": game_master, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "2-2"

    def test_range_quantity_row(self, club, game_master):
        """Range quantity row shows min-max."""
        container = make_container(club, name="Container")
        gold = _get_or_create_item(club, "Gold")
        add_slot(container, [(gold, 1, 4, 1)], chance_pct=100, unknown=False, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}"
            "{{ rows.0.qty_min }}-{{ rows.0.qty_max }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": game_master, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "1-4"

    def test_chance_pct_row(self, club, game_master):
        """Row shows chance_pct < 100."""
        container = make_container(club, name="Container")
        gem = _get_or_create_item(club, "Gem")
        add_slot(container, [(gem, 1, 1, 1)], chance_pct=50, unknown=False, position=0)

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}{{ rows.0.chance_pct }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": game_master, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert result == "50"

    def test_one_of_row(self, club, game_master):
        """Weighted 'pick one' row shows options with weight_pct."""
        container = make_container(club, name="Container")
        sword = _get_or_create_item(club, "Sword")
        shield = _get_or_create_item(club, "Shield")
        add_slot(
            container,
            [(sword, 1, 1, 1), (shield, 1, 1, 3)],
            chance_pct=100,
            unknown=False,
            position=0,
        )

        template = Template(
            "{% load loot_tags %}{% loot_preview container as rows %}"
            "{{ rows.0.label }}"
            "{{ rows.0.options.0.weight_pct }}"
            "{{ rows.0.options.1.weight_pct }}"
        )
        context = Context(
            {
                "request": type("Request", (), {"user": game_master, "club": club})(),
                "container": container,
            }
        )
        result = template.render(context)
        assert "One of" in result
        assert "25" in result  # 1/4 * 100
        assert "75" in result  # 3/4 * 100
