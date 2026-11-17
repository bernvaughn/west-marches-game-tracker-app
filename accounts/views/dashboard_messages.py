"""My Messages dashboard views."""

from django.http import Http404
from django.shortcuts import redirect, render

from accounts.forms import MessageForm
from accounts.models import Message
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_get_object_or_404, club_queryset
from player_characters.selection import selected_character


@club_member_required
def message_detail(request, club_slug, pk):
    """Message detail view - sender sees read-only, admin sees actions."""
    club = request.club
    membership = request.membership
    message = club_get_object_or_404(request, Message, pk=pk)

    # Sender can view their own message (read-only)
    if message.sender_id == membership.id:
        return render(request, "accounts/message_detail.html", {
            "club": club,
            "message": message,
            "read_only": True,
        })

    # Admin can view any message with action buttons
    if is_club_admin(request.user, club) or is_game_master(request.user, club):
        return render(request, "accounts/message_detail.html", {
            "club": club,
            "message": message,
            "read_only": False,
        })

    # Others cannot view
    raise Http404("Message not found.")


@club_member_required
def message_new(request, club_slug):
    """Create a new message to admins."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    if request.method == "POST":
        form = MessageForm(request.POST, club=club, sender=membership)
        if form.is_valid():
            msg = form.save()
            return redirect("accounts:message_detail", club_slug=club.slug, pk=msg.pk)
    else:
        form = MessageForm(club=club, sender=membership)

    return render(request, "accounts/message_new.html", {
        "club": club,
        "form": form,
        "character": character,
    })


@club_member_required
def message_inbox(request, club_slug):
    """Admin inbox showing all open messages."""
    club = request.club

    if not (is_club_admin(request.user, club) or is_game_master(request.user, club)):
        raise Http404("Not authorized.")

    messages = (
        club_queryset(request, Message)
        .filter(status=Message.Status.OPEN)
        .select_related("sender__user", "character")
        .order_by("-created")
    )

    return render(request, "accounts/message_inbox.html", {
        "club": club,
        "messages": messages,
    })