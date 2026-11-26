"""View for email RSVP confirmation page (E6).

The RSVP token now carries the member (member_id), not a character.
Old character-carrying tokens (character_id) still resolve to that
character's owner membership so links already sent keep working until
the session starts.

GET: Shows the confirmation page. Does not consume the token or change
anything (a plain page load records no RSVP).
POST: Consumes the token and records a PlayerRSVP for the member.
"""

from django.shortcuts import render
from django.utils import timezone
from django.views import View

from mail.tokens import consume, peek
from play_sessions.models import PlayerRSVP, PlaySession
from player_characters.models import Character


class EmailRSVPView(View):
    """Public RSVP confirmation page."""

    template_name = "mail/email_rsvp_confirm.html"

    # --- Token resolution -------------------------------------------------

    def _resolve_token(self, ot_token):
        """Resolve a token to the session + membership it addresses.

        New tokens carry member_id. Legacy character-carrying tokens
        resolve to that character's owner membership.
        Returns None if the token data is invalid.
        """
        extra = ot_token.extra or {}
        session_id = extra.get("session_id")
        member_id = extra.get("member_id")
        character_id = extra.get("character_id")
        answer = extra.get("answer")

        if not session_id or not answer:
            return None

        try:
            session = PlaySession.objects.get(pk=session_id)
        except PlaySession.DoesNotExist:
            return None

        membership = None
        character = None
        legacy = False

        if member_id is not None:
            # New-style token: addressed to the member directly.
            from accounts.models import Membership

            try:
                membership = Membership.objects.get(pk=member_id)
            except Membership.DoesNotExist:
                return None
            if membership.club_id != session.club_id:
                return None
        elif character_id is not None:
            # Legacy token: addressed to a character; resolve to its owner.
            legacy = True
            try:
                character = Character.objects.select_related("owner").get(pk=character_id)
            except Character.DoesNotExist:
                return None
            membership = character.owner
            if membership is None or membership.club_id != session.club_id:
                return None
        else:
            return None

        return {
            "session": session,
            "membership": membership,
            "character": character,
            "legacy": legacy,
            "answer": answer,
        }

    # --- GET --------------------------------------------------------------

    def get(self, request, token):
        """Show confirmation page. Does not consume the token or change anything."""
        ot_token = peek(token, "rsvp")
        if not ot_token:
            return render(request, self.template_name, {"error": "invalid_or_expired"})

        resolved = self._resolve_token(ot_token)
        if not resolved:
            return render(request, self.template_name, {"error": "invalid_token_data"})

        # Check if signed-in user differs from token user
        if request.user.is_authenticated and request.user != ot_token.user:
            return render(request, self.template_name, {"error": "not_for_you"})

        session = resolved["session"]

        # The token expires at the session start; a started or cancelled
        # session cannot be RSVP'd to.
        if session.cancelled:
            return render(request, self.template_name, {"error": "session_cancelled"})
        if session.starts_at <= timezone.now():
            return render(request, self.template_name, {"error": "session_started"})

        membership = resolved["membership"]
        current_rsvp = PlayerRSVP.objects.filter(session=session, member=membership).first()

        context = {
            "token": token,
            "session": session,
            "membership": membership,
            "member": membership,
            "character": resolved["character"],
            "legacy": resolved["legacy"],
            "selected_answer": resolved["answer"],
            "current_rsvp": current_rsvp,
            "club": session.club,
            "show_form": True,
        }
        return render(request, self.template_name, context)

    # --- POST -------------------------------------------------------------

    def post(self, request, token):
        """Confirm RSVP. Consumes the token and records a PlayerRSVP."""
        ot_token = consume(token, "rsvp")
        if not ot_token:
            return render(request, self.template_name, {"error": "invalid_or_expired"})

        # Check if signed-in user differs from token user
        if request.user.is_authenticated and request.user != ot_token.user:
            return render(request, self.template_name, {"error": "not_for_you"})

        resolved = self._resolve_token(ot_token)
        if not resolved:
            return render(request, self.template_name, {"error": "invalid_token_data"})

        session = resolved["session"]
        membership = resolved["membership"]

        if session.cancelled:
            return render(request, self.template_name, {"error": "session_cancelled"})
        if session.starts_at <= timezone.now():
            return render(request, self.template_name, {"error": "session_started"})

        answer = resolved["answer"]

        # Record the RSVP for the member. Legacy character tokens also
        # resolve to the owner's membership and record a PlayerRSVP.
        PlayerRSVP.objects.update_or_create(
            session=session,
            member=membership,
            defaults={
                "answer": answer,
                "answered_by": ot_token.user,
                "answered_at": timezone.now(),
            },
        )

        updated_rsvp = PlayerRSVP.objects.get(session=session, member=membership)

        context = {
            "session": session,
            "membership": membership,
            "member": membership,
            "character": resolved["character"],
            "legacy": resolved["legacy"],
            "selected_answer": answer,
            "current_rsvp": updated_rsvp,
            "club": session.club,
            "show_form": False,
            "confirmed": True,
        }
        return render(request, self.template_name, context)
