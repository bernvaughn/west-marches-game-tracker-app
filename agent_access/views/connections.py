from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_queryset

from ..models import AgentConnection
from ..tokens import create_token


class ConnectionForm(forms.Form):
    label = forms.CharField(max_length=200, required=True, strip=True)


def _own_connections(request):
    return club_queryset(request, AgentConnection).filter(user=request.user).order_by("-created")


@game_master_required
@never_cache
def connection_list(request, club_slug):
    context = {"mcp_url": request.build_absolute_uri(reverse("mcp"))}
    if request.method == "POST":
        form = ConnectionForm(request.POST)
        if form.is_valid():
            connection, secret = create_token(
                request.user, request.club, form.cleaned_data["label"]
            )
            context.update(new_secret=secret, new_connection=connection)
            form = ConnectionForm()
    else:
        form = ConnectionForm()
    context.update(form=form, connections=_own_connections(request))
    return render(request, "agent_access/connections/list.html", context)


@game_master_required
@require_POST
def connection_revoke(request, club_slug, pk):
    connection = get_object_or_404(_own_connections(request), pk=pk)
    if connection.revoked_at is None:
        connection.revoked_at = timezone.now()
        connection.save(update_fields=["revoked_at"])
    messages.success(request, f"Revoked connection “{connection.label}”.")
    return redirect("agent_access:connections", club_slug=club_slug)
