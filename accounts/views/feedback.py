from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms.feedback import FeedbackForm
from ..forms.inbox import StatusForm
from ..models import Club, SiteFeedback
from ..permissions import site_admin_required
from ..ratelimit import rate_limit

FEEDBACK_LIMIT = 10
FEEDBACK_WINDOW = 60 * 60  # 10 per hour per user


def _safe_page_url(request):
    """Return a validated same-site relative path from the request, or ''."""
    for raw in (request.GET.get("from"), request.GET.get("next"), request.META.get("HTTP_REFERER")):
        if not raw or not raw.strip():
            continue
        if url_has_allowed_host_and_scheme(raw.strip(), allowed_hosts=None):
            path = urlparse(raw.strip()).path
            if path.startswith("/"):
                return path
    return ""


def _club_for_path(path):
    """The club referenced by a /c/<slug>/... path, or None."""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "c":
        return Club.objects.filter(slug=parts[1]).first()
    return None


@login_required
@rate_limit(
    prefix="site_feedback",
    limit=FEEDBACK_LIMIT,
    window=FEEDBACK_WINDOW,
    key_func=lambda req: str(req.user.id),
)
def feedback_new(request):
    page_url = _safe_page_url(request)
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            # page_url is captured server-side; never trust the posted hidden field.
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.club = _club_for_path(page_url)
            feedback.page_url = page_url
            feedback.save()
            messages.success(request, "Thanks, we got it.")
            return redirect(page_url or reverse("feedback_new"))
    else:
        form = FeedbackForm(initial={"page_url": page_url})
        kind = request.GET.get("kind")
        if kind in dict(SiteFeedback.Kind.choices):
            form.fields["kind"].initial = kind
    earlier = (
        SiteFeedback.objects.filter(user=request.user).select_related("club").order_by("-created")
    )
    return render(
        request,
        "accounts/feedback/new.html",
        {"form": form, "page_url": page_url, "earlier_reports": earlier},
    )


@site_admin_required
def feedback_list(request):
    status = request.GET.get("status", "open")
    if status not in ("open", "handled", "closed", "all"):
        status = "open"
    kind = request.GET.get("kind", "all")
    if kind not in dict(SiteFeedback.Kind.choices):
        kind = "all"
    qs = SiteFeedback.objects.select_related("user", "club").all()
    if status != "all":
        qs = qs.filter(status=status)
    if kind != "all":
        qs = qs.filter(kind=kind)
    return render(
        request,
        "accounts/feedback/list.html",
        {
            "feedback_list": qs,
            "status": status,
            "kind": kind,
            "status_choices": SiteFeedback.Status.choices,
            "kind_choices": SiteFeedback.Kind.choices,
        },
    )


@site_admin_required
@require_POST
def feedback_status(request, pk):
    feedback = get_object_or_404(SiteFeedback, pk=pk)
    form = StatusForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid status")
    feedback.status = form.cleaned_data["status"]
    feedback.save(update_fields=["status"])
    return redirect("site_feedback")
