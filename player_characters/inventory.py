"""Deprecated: re-export inventory rendering helpers from :mod:`player_characters.sheet`.

``inventory_rows``, ``coin_summary``, ``InventoryRow`` and ``CoinSummary`` now live in
``player_characters/sheet.py`` as the single source of truth for character sheet inventory
rendering. This module remains only for backward compatibility; new code should import from
``player_characters.sheet`` instead.

``USE_CIRCLE_CAP`` stays here because ``player_characters.item_cards`` and some tests import
it directly; it is unrelated to inventory rendering.
"""

from .sheet import CoinSummary, InventoryRow, coin_summary, inventory_rows  # noqa: F401

USE_CIRCLE_CAP = 30
