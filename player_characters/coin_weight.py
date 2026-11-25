"""Coin weight calculation helper.

Calculates the weight of a character's coins in hundredths of a pound.
Uses the minimum physical coin count for the balance (platinum, gold, silver, copper).
50 coins = 1 lb = 100 hundredths.

Coins are stored as a copper total in the ledger. This module converts that total
to the minimum number of physical coins using standard D&D denominations:
1 pp = 10 gp = 100 sp = 1000 cp
1 gp = 10 sp = 100 cp
1 sp = 10 cp
"""

from ledger.services import coin_balance


def coin_weight_hundredths(character, club_weight_settings):
    """Return coin weight in hundredths of a pound, or 0 if disabled.

    Args:
        character: A Character instance.
        club_weight_settings: A ClubWeightSettings instance, or None.

    Returns:
        Integer weight in hundredths of a pound. 0 if coin weight is disabled
        or the character has no coins.
    """
    if not club_weight_settings or not club_weight_settings.count_coin_weight:
        return 0

    # Get total copper balance from ledger
    total_cp = coin_balance(character)
    if total_cp <= 0:
        return 0

    # Minimum physical coins for the balance (greedy algorithm):
    # Convert to the fewest coins using standard denominations
    min_pp = total_cp // 1000
    remainder = total_cp % 1000
    min_gp = remainder // 100
    remainder = remainder % 100
    min_sp = remainder // 10
    min_cp = remainder % 10

    total_coins = min_pp + min_gp + min_sp + min_cp

    if total_coins == 0:
        return 0

    # 50 coins = 1 lb = 100 hundredths
    # So 1 coin = 2 hundredths
    return total_coins * 2
