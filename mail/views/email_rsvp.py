"""View for email RSVP confirmation page (E6)."""

from django.shortcuts import render
from django.views import View

from mail.tokens import consume, peek
from play_sessions import core
from play_sessions.models import PlaySession, SessionRSVP
from player_characters.models import Character


class EmailRSVPView(View):
    """Public RSVP confirmation page.

    GET: Shows the confirmation page with the selected answer and current RSVP.
    POST: Confirms the RSVP by calling play_sessions.core.set_rsvp after validation.
    """

    template_name = "mail/email_rsvp_confirm.html"

    def get(self, request, token):
        """Show confirmation page. Does not consume the token or change anything."""
        ot_token = peek(token, "rsvp")
        if not ot_token:
            return render(request, self.template_name, {"error": "invalid_or_expired"})

        # Extract data from token extra
        extra = ot_token.extra or {}
        session_id = extra.get("session_id")
        character_id = extra.get("character_id")
        answer = extra.get("answer")

        if not all([session_id, character_id, answer]):
            return render(request, self.template_name, {"error": "invalid_token_data"})

        # Check if signed-in user differs from token user
        if request.user.is_authenticated and request.user != ot_token.user:
            return render(request, self.template_name, {"error": "not_for_you"})

        try:
            session = PlaySession.objects.get(pk=session_id)
            character = Character.objects.get(pk=character_id)
        except (PlaySession.DoesNotExist, Character.DoesNotExist):
            return render(request, self.template_name, {"error": "invalid_token_data"})

        # Get current RSVP if exists
        current_rsvp = SessionRSVP.objects.filter(session=session, character=character).first()

        context = {
            "token": token,
            "session": session,
            "character": character,
            "selected_answer": answer,
            "current_rsvp": current_rsvp,
            "club": session.club,
            "show_form": True,
        }
        return render(request, self.template_name, context)

    def post(self, request, token):
        """Confirm RSVP. Consumes the token and calls set_rsvp after validation."""
        ot_token = consume(token, "rsvp")
        if not ot_token:
            return render(request, self.template_name, {"error": "invalid_or_expired"})

        # Check if signed-in user differs from token user
        if request.user.is_authenticated and request.user != ot_token.user:
            return render(request, self.template_name, {"error": "not_for_you"})

        # Extract data from token extra
        extra = ot_token.extra or {}
        session_id = extra.get("session_id")
        character_id = extra.get("character_id")
        answer = extra.get("answer")

        if not all([session_id, character_id, answer]):
            return render(request, self.template_name, {"error": "invalid_token_data"})

        try:
            session = PlaySession.objects.get(pk=session_id)
            character = Character.objects.get(pk=character_id)
        except (PlaySession.DoesNotExist, Character.DoesNotExist):
            return render(request, self.template_name, {"error": "invalid_token_data"})

        # Validation checks
        # 1. Character belongs to token's user
        if character.owner.user != ot_token.user:
            return render(request, self.template_name, {"error": "wrong_character"})

        # 2. Character is active (not dead, not archived)
        if not core.character_is_active(character):
            return render(request, self.template_name, {"error": "character_inactive"})

        # 3. Session is not cancelled
        if session.cancelled:
            return render(request, self.template_name, {"error": "session_cancelled"})

        # 4. Session has not started
        from django.utils import timezone

        if session.starts_at <= timezone.now():
            return render(request, self.template_name, {"error": "session_started"})

        # All checks passed - record the RSVP
        core.set_rsvp(session, character, answer, by=ot_token.user)

        # Get the updated RSVP
        updated_rsvp = SessionRSVP.objects.get(session=session, character=character)

        context = {
            "session": session,
            "character": character,
            "selected_answer": answer,
            "current_rsvp": updated_rsvp,
            "club": session.club,
            "show_form": False,
            "confirmed": True,
        }
        return render(request, self.template_name, context)
