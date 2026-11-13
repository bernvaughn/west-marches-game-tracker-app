"""One sentence that says where a trade stands and who it waits on (U78)."""

from django.utils import timezone
from django.utils.formats import date_format

from .models import Trade


def _player(character):
    return character.owner.user.display_name


def trade_status_line(trade, viewer_side):
    """`viewer_side` is "sender", "receiver" or None (a GM or admin watching)."""
    status = trade.status
    if status in (Trade.Status.COMPLETED, Trade.Status.DECLINED, Trade.Status.CANCELLED):
        when = date_format(timezone.localdate(trade.updated), "j M Y")
        return f"This trade was {status} on {when}."

    sender, receiver = _player(trade.sender), _player(trade.receiver)
    if status == Trade.Status.REQUESTED:
        if viewer_side == "receiver":
            return (
                f"{sender} wants to trade with {trade.receiver.name}. "
                "Accept to choose what you give, or decline."
            )
        if viewer_side == "sender":
            return f"Waiting for {receiver} to accept."
        return f"Waiting for {receiver} to accept {sender}'s trade request."

    # Accepted.
    approved = {"sender": trade.sender_approved, "receiver": trade.receiver_approved}
    names = {"sender": sender, "receiver": receiver}
    if not any(approved.values()):
        changed = trade.sides_changed_by
        if changed in names:
            who = "You" if changed == viewer_side else names[changed]
            their = "your" if changed == viewer_side else "their"
            return f"{who} changed {their} side. Both of you need to approve again."
        return "Both sides can change what they give. Approve when the trade looks right."
    if viewer_side is None:
        done = [names[s] for s in ("sender", "receiver") if approved[s]]
        waiting = [names[s] for s in ("sender", "receiver") if not approved[s]]
        if not waiting:
            return f"{sender} and {receiver} have approved."
        return f"{done[0]} has approved. Waiting for {waiting[0]}."
    other = "receiver" if viewer_side == "sender" else "sender"
    if approved[viewer_side] and not approved[other]:
        return f"You have approved. Waiting for {names[other]} to approve as well."
    if approved[other] and not approved[viewer_side]:
        return f"{names[other]} has approved. Approve to complete the trade."
    return "Both of you have approved."
