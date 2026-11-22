"""Views for RSVP (P4)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from player_characters.models import Character

from .. import core
from ..models import PlaySession
from ..rsvp_forms import RsvpForm, default_character, rsvp_refusal


@club_member_required
@require_POST
def rsvp_set(request, club_slug, pk):
    """Set or update an RSVP for a session.

    POST parameters:
        answer: "yes", "maybe", or "no"
        character: (optional) character pk; defaults to selected character
        next: (optional) redirect URL after success

    Returns:
        - HTMX: re-renders the RSVP section fragment (swap #rsvp-section outerHTML)
        - Regular: redirects to next (if safe) or session detail
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)

    # Determine character from POST or default
    character = None
    char_pk = request.POST.get("character")
    if char_pk:
        character = club_get_object_or_404(request, Character, pk=char_pk)
    else:
        character = default_character(request)

    if character is None:
        return HttpResponseBadRequest("No active character available for RSVP.")

    # Validate form
    form = RsvpForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid RSVP answer.")

    answer = form.cleaned_data["answer"]

    # Check refusal rules
    refusal = rsvp_refusal(request, session, character)
    if refusal:
        raise PermissionDenied(refusal)

    # Save RSVP
    core.set_rsvp(session, character, answer, request.user)

    # Success handling
    next_url = form.cleaned_data.get("next")
    if next_url and not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        next_url = None

    if is_htmx(request) and not next_url:
        # Re-render the RSVP section fragment
        from ..hooks_rsvp import _rsvp_section_context

        context = _rsvp_section_context(request, session)
        from django.template.loader import render_to_string

        html = render_to_string("play_sessions/_rsvp_section.html", context, request=request)
        from django.http import HttpResponse

        return HttpResponse(html)

    messages.success(request, "Your RSVP has been saved.")
    if next_url:
        return redirect(next_url)
    return redirect("play_sessions:session_detail", club_slug=club_slug, pk=session.pk)
