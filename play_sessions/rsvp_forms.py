"""Forms and shared logic for RSVP (P4)."""

from django import forms
from django.utils import timezone

from player_characters.selection import own_characters, selected_character

from . import core
from .models import SessionRSVP


class RsvpForm(forms.Form):
    """Form for submitting an RSVP answer."""

    answer = forms.ChoiceField(choices=SessionRSVP.Answer.choices)
    character = forms.IntegerField(required=False)  # character pk
    next = forms.CharField(required=False)  # redirect URL


def rsvp_refusal(request, session, character) -> str | None:
    """Return a refusal reason string if the RSVP is not allowed, else None.

    One shared rule set for the view and the hooks.
    """
    # Inactive character -> refused for everyone, GM and admin included
    if not core.character_is_active(character):
        return "This character is no longer active and cannot RSVP."

    is_manager = core.can_manage_sessions(request.user, session.club)

    # Manager (GM, club admin, superuser) -> allowed for any club character, before or after start
    if is_manager:
        return None

    # Player: character must be owned by request.membership
    membership = getattr(request, "membership", None)
    if membership is None or character.owner_id != membership.id:
        return "You can only RSVP for your own characters."

    # Session must not have started
    if session.starts_at <= timezone.now():
        return "Answers are closed. The session has already started."

    # Session must not be cancelled
    if session.cancelled:
        return "This session is cancelled."

    return None


def answerable_characters(request) -> list:
    """Return own active characters, ordered with the selected character first."""
    chars = [c for c in own_characters(request) if core.character_is_active(c)]
    selected = selected_character(request)
    if selected and selected in chars:
        chars.remove(selected)
        chars.insert(0, selected)
    return chars


def default_character(request):
    """Return the default character for RSVP: selected if active and owned,
    else first active own character."""
    selected = selected_character(request)
    if selected and core.character_is_active(selected):
        # Verify ownership
        membership = getattr(request, "membership", None)
        if membership and selected.owner_id == membership.id:
            return selected
    # Fall back to first active own character
    for c in own_characters(request):
        if core.character_is_active(c):
            return c
    return None


def rsvp_answers(session, characters) -> dict:
    """Return a dict mapping character_id -> answer for the given session and characters."""
    rsvps = SessionRSVP.objects.filter(session=session, character__in=characters).select_related(
        "character"
    )
    return {r.character_id: r.answer for r in rsvps}
