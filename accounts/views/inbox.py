from django.contrib import messages as flash
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from player_characters.selection import selected_character

from ..forms.inbox import MessageForm, StatusForm
from ..models import Message
from ..permissions import club_admin_required, club_member_required
from ..scoping import club_get_object_or_404, club_queryset

FILTERS = ("open", "handled", "closed", "all")


@club_member_required
def message_new(request, club_slug):
    membership = request.membership
    if membership is None:
        if request.method == "POST":
            raise PermissionDenied
        return render(request, "accounts/inbox/message_new.html", {"form": None, "sent": []})
    form = MessageForm(
        request.POST or None,
        membership=membership,
        initial={"character": selected_character(request)},
    )
    if request.method == "POST" and form.is_valid():
        msg = form.save(commit=False)
        msg.club = request.club
        msg.sender = membership
        msg.save()
        flash.success(request, "Message sent to the club admins.")
        return redirect("accounts:message_new", club_slug=club_slug)
    sent = club_queryset(request, Message).filter(sender=membership).select_related("character")
    return render(request, "accounts/inbox/message_new.html", {"form": form, "sent": sent})


@club_admin_required
def message_inbox(request, club_slug):
    status = request.GET.get("status", "open")
    if status not in FILTERS:
        status = "open"
    qs = club_queryset(request, Message).select_related("sender__user", "character")
    if status != "all":
        qs = qs.filter(status=status)
    return render(
        request,
        "accounts/inbox/inbox.html",
        {
            "messages_list": qs,
            "status": status,
            "filters": FILTERS,
            "statuses": Message.Status.choices,
        },
    )


@club_admin_required
@require_POST
def message_status(request, club_slug, pk):
    msg = club_get_object_or_404(request, Message, pk=pk)
    form = StatusForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid status")
    msg.status = form.cleaned_data["status"]
    msg.save(update_fields=["status"])
    back = request.POST.get("filter", "open")
    if back not in FILTERS:
        back = "open"
    return redirect(f"{reverse('accounts:message_inbox', args=[club_slug])}?status={back}")
