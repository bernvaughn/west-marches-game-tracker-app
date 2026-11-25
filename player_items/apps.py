from django.apps import AppConfig

from player_characters.sheet_sections import register_sheet_section


class PlayerItemsConfig(AppConfig):
    name = "player_items"
    label = "player_items"
    verbose_name = "Player items"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin
        from accounts.permissions import can_view_inventory
        from player_items.models import PlayerItem

        def entries_context(request, character):
            """Return the player-written entries for a character's sheet."""
            return {
                "entries": character.player_items.for_club(request.club).all(),
                "can_add": can_view_inventory(request.user, character),
            }

        def entries_visible(request, character):
            return can_view_inventory(request.user, character)

        register_sheet_section(
            key="player_entries",
            order=50,
            template="player_items/_entries.html",
            context_fn=entries_context,
            visible_fn=entries_visible,
        )

        def open_review_group_label(request):
            """Label for the review nav entry, including open-group count."""
            count = (
                PlayerItem.objects.for_club(request.club)
                .filter(review=PlayerItem.Review.OPEN)
                .values("name_key")
                .distinct()
                .count()
            )
            if count:
                return f"Review player items ({count})"
            return "Review player items"

        reg = navigation.register
        reg(
            "admin",
            open_review_group_label,
            "player_items:review",
            is_admin,
            45,
        )
