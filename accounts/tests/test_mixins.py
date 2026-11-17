"""Tests for accounts.mixins."""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.http import HttpRequest

from accounts.mixins import (
    ClubScopedMixin,
    CharacterContextMixin,
    PermissionMixin,
    ClubContextMixin,
    ViewMixin,
)
from accounts.models import Club, Membership, User
from player_characters.models import Character
from items.models import Item


class ClubScopedMixinTests(TestCase):
    def setUp(self):
        self.mixin = ClubScopedMixin()
        self.request = MagicMock()
        self.mixin.request = self.request

    def test_get_club_queryset(self):
        model = MagicMock()
        self.request.club = "test_club"

        with patch("accounts.mixins._club_queryset") as mock_queryset:
            mock_queryset.return_value = "filtered_queryset"
            result = self.mixin.get_club_queryset(model)

            mock_queryset.assert_called_once_with(self.request, model)
            self.assertEqual(result, "filtered_queryset")

    def test_get_club_object_or_404(self):
        model = MagicMock()
        self.request.club = "test_club"

        with patch("accounts.mixins._club_get_object_or_404") as mock_get:
            mock_get.return_value = "found_object"
            result = self.mixin.get_club_object_or_404(model, pk=1)

            mock_get.assert_called_once_with(self.request, model, pk=1)
            self.assertEqual(result, "found_object")


class CharacterContextMixinTests(TestCase):
    def setUp(self):
        self.mixin = CharacterContextMixin()
        self.request = MagicMock()
        self.mixin.request = self.request

    @patch("accounts.mixins.inventory_rows")
    @patch("accounts.mixins.coin_summary")
    @patch("accounts.mixins.junk_rows")
    @patch("accounts.mixins.junk_value")
    @patch("accounts.mixins.downtime_services.balance")
    def test_get_character_context_with_character(
        self, mock_balance, mock_junk_value, mock_junk_rows, mock_coin_summary, mock_inventory_rows
    ):
        character = MagicMock(spec=Character)
        mock_inventory_rows.return_value = ["row1", "row2"]
        mock_coin_summary.return_value = "coin_summary"
        mock_junk_rows.return_value = ["junk1"]
        mock_junk_value.return_value = 100
        mock_balance.return_value = 50

        result = self.mixin.get_character_context(character)

        self.assertEqual(result["inventory_rows"], ["row1", "row2"])
        self.assertEqual(result["coin_summary"], "coin_summary")
        self.assertEqual(result["junk_rows"], ["junk1"])
        self.assertEqual(result["junk_value"], 100)
        self.assertEqual(result["downtime_balance"], 50)

        mock_inventory_rows.assert_called_once_with(character)
        mock_coin_summary.assert_called_once_with(character)
        mock_junk_rows.assert_called_once_with(character)
        mock_junk_value.assert_called_once_with(character, ["junk1"])
        mock_balance.assert_called_once_with(character)

    @patch("accounts.mixins.inventory_rows")
    @patch("accounts.mixins.coin_summary")
    @patch("accounts.mixins.junk_rows")
    @patch("accounts.mixins.junk_value")
    @patch("accounts.mixins.downtime_services.balance")
    def test_get_character_context_without_character(
        self, mock_balance, mock_junk_value, mock_junk_rows, mock_coin_summary, mock_inventory_rows
    ):
        result = self.mixin.get_character_context(None)

        self.assertEqual(result["inventory_rows"], [])
        self.assertEqual(result["coin_summary"], None)
        self.assertEqual(result["junk_rows"], [])
        self.assertEqual(result["junk_value"], 0)
        self.assertEqual(result["downtime_balance"], 0)

        mock_inventory_rows.assert_not_called()
        mock_coin_summary.assert_not_called()
        mock_junk_rows.assert_not_called()
        mock_junk_value.assert_not_called()
        mock_balance.assert_not_called()

    @patch("accounts.mixins.selected_character")
    def test_get_selected_character(self, mock_selected):
        mock_selected.return_value = "selected_char"
        result = self.mixin.get_selected_character()
        self.assertEqual(result, "selected_char")
        mock_selected.assert_called_once_with(self.request)


class PermissionMixinTests(TestCase):
    def setUp(self):
        self.mixin = PermissionMixin()

    @patch("accounts.mixins._is_club_admin")
    def test_is_club_admin(self, mock_is_admin):
        mock_is_admin.return_value = True
        user = MagicMock()
        club = MagicMock()

        result = self.mixin.is_club_admin(user, club)

        self.assertTrue(result)
        mock_is_admin.assert_called_once_with(user, club)

    @patch("accounts.mixins._is_game_master")
    def test_is_game_master(self, mock_is_gm):
        mock_is_gm.return_value = True
        user = MagicMock()
        club = MagicMock()

        result = self.mixin.is_game_master(user, club)

        self.assertTrue(result)
        mock_is_gm.assert_called_once_with(user, club)

    @patch("accounts.mixins._can_view_inventory")
    def test_can_view_inventory(self, mock_can_view):
        mock_can_view.return_value = True
        user = MagicMock()
        character = MagicMock()

        result = self.mixin.can_view_inventory(user, character)

        self.assertTrue(result)
        mock_can_view.assert_called_once_with(user, character)


class ClubContextMixinTests(TestCase):
    def setUp(self):
        self.mixin = ClubContextMixin()
        self.request = MagicMock()
        self.mixin.request = self.request

    def test_club_property(self):
        self.request.club = "test_club"
        self.assertEqual(self.mixin.club, "test_club")

    def test_membership_property(self):
        self.request.membership = "test_membership"
        self.assertEqual(self.mixin.membership, "test_membership")

    def test_user_property(self):
        self.request.user = "test_user"
        self.assertEqual(self.mixin.user, "test_user")


class ViewMixinTests(TestCase):
    """Test that ViewMixin combines all mixins correctly."""

    def setUp(self):
        self.mixin = ViewMixin()
        self.request = MagicMock()
        self.mixin.request = self.request

    def test_inherits_all_mixins(self):
        self.assertIsInstance(self.mixin, ClubScopedMixin)
        self.assertIsInstance(self.mixin, CharacterContextMixin)
        self.assertIsInstance(self.mixin, PermissionMixin)
        self.assertIsInstance(self.mixin, ClubContextMixin)