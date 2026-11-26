"""Forms and shared logic for RSVP (P13: per player)."""

from django import forms
from django.utils import timezone

from accounts.models import Membership

from . import core
from .models import PlayerRSVP


class RsvpForm(forms.Form):
    """Form for submitting an RSVP answer."""

    answer = forms.ChoiceField(choices=PlayerRSVP.Answer.choices)
    member = forms.ModelChoiceField(
        queryset=Membership.objects.none(), required=False
    )  # target membership (managers only)
    next = forms.CharField(required=False)  # redirect URL

    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        if club:
            self.fields["member"].queryset = Membership.objects.for_club(club)


def rsvp_refusal(request, session, member) -> str | None:
    """Return a refusal reason string if the RSVP is not allowed, else None.

    One shared rule set for the view and the hooks.
    """
    is_manager = core.can_manage_sessions(request.user, session.club)

    # Manager (GM, club admin, superuser): allowed for any club member,
    # before or after start, even if cancelled
    if is_manager:
        return None

    # Player: must be their own membership
    membership = getattr(request, "membership", None)
    if membership is None or membership.id != member.id:
        return "You can only RSVP for yourself."

    # Session must not have started
    if session.starts_at <= timezone.now():
        return "Answers are closed. The session has already started."

    # Session must not be cancelled
    if session.cancelled:
        return "This session is cancelled."

    return None


def rsvp_answers(session, members) -> dict:
    """Return a dict mapping member_id -> answer for the given session and members."""
    rsvps = PlayerRSVP.objects.filter(session=session, member__in=members).select_related("member")
    return {r.member_id: r.answer for r in rsvps}
