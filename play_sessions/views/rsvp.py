"""Views for RSVP (P13: per player)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..models import PlayerRSVP, PlaySession
from ..rsvp_forms import RsvpForm, rsvp_refusal


@club_member_required
@require_POST
def rsvp_set(request, club_slug, pk):
    """Set or update an RSVP for a session.

    POST parameters:
        answer: "yes", "maybe", or "no"
        member: (optional) membership pk; managers can answer for any member
        next: (optional) redirect URL after success

    Returns:
        - HTMX: re-renders the RSVP section fragment (swap #rsvp-section outerHTML)
        - Regular: redirects to next (if safe) or session detail
    """
    session = club_get_object_or_404(request, PlaySession, pk=pk)

    membership = getattr(request, "membership", None)
    # Superusers may not have a membership in the club but can still manage RSVPs
    if membership is None and not request.user.is_superuser:
        return HttpResponseBadRequest("No membership found for this club.")

    # Validate form
    form = RsvpForm(request.POST, club=session.club)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid RSVP answer.")

    answer = form.cleaned_data["answer"]
    target_member = form.cleaned_data.get("member") or membership

    # Check refusal rules
    refusal = rsvp_refusal(request, session, target_member)
    if refusal:
        raise PermissionDenied(refusal)

    # Save RSVP
    PlayerRSVP.objects.update_or_create(
        session=session,
        member=target_member,
        defaults={"answer": answer, "answered_by": request.user, "answered_at": timezone.now()},
    )

    # Success handling
    next_url = form.cleaned_data.get("next")
    if next_url and not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        next_url = None

    if is_htmx(request) and not next_url:
        # Re-render the RSVP section fragment
        from django.http import HttpResponse
        from django.template.loader import render_to_string

        from ..hooks_rsvp import _rsvp_section_context

        context = _rsvp_section_context(request, session)
        html = render_to_string("play_sessions/_rsvp_section.html", context, request=request)
        return HttpResponse(html)

    messages.success(request, "Your RSVP has been saved.")
    if next_url:
        return redirect(next_url)
    return redirect("play_sessions:session_detail", club_slug=club_slug, pk=session.pk)
