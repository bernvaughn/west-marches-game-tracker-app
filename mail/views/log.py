"""Email log views for club admins."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from accounts.permissions import club_admin_required
from mail.models import EmailMessage, JobRun
from mail.suppression import clear


@club_admin_required
def email_log(request, club_slug):
    """Show email log for the club (club admin only)."""
    club = request.club
    messages_qs = EmailMessage.objects.filter(club=club).select_related("user")

    paginator = Paginator(messages_qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Background jobs panel only for site admin
    job_runs = JobRun.objects.all() if request.user.is_superuser else None

    context = {
        "club": club,
        "page_obj": page_obj,
        "job_runs": job_runs,
    }
    return render(request, "mail/log.html", context)


@club_admin_required
def clear_flag(request, club_slug):
    """Clear a do-not-email flag for an address in this club's log (club admin only)."""
    if request.method != "POST":
        return redirect("mail:log", club_slug=club_slug)

    address = request.POST.get("address", "").strip()
    if not address:
        messages.error(request, "No address provided.")
        return redirect("mail:log", club_slug=club_slug)

    # Check if address appears in this club's log
    exists = EmailMessage.objects.filter(club=request.club, to_address__iexact=address).exists()

    if not exists:
        messages.error(request, "Address not found in this club's email log.")
        return redirect("mail:log", club_slug=club_slug)

    # Clear the flag
    cleared = clear(address)
    if cleared:
        messages.success(request, f"Do-not-email flag cleared for {address}.")
    else:
        messages.info(request, f"No do-not-email flag found for {address}.")

    return redirect("mail:log", club_slug=club_slug)
