"""htmx helpers (U33). The project has no django-htmx; detect the header directly."""

import json

from django.http import HttpResponse
from django.shortcuts import redirect as django_redirect
from django.shortcuts import render
from django.utils.cache import patch_vary_headers


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _trigger_value(trigger):
    """Return a trigger header value: a string as-is, a dict json-encoded."""
    if isinstance(trigger, str):
        return trigger
    return json.dumps(trigger)


def set_hx_headers(response, *, trigger=None, redirect=None, refresh=False):
    """Set HX-* headers on `response` and return it."""
    if redirect is not None:
        response["HX-Redirect"] = redirect
    if trigger is not None:
        response["HX-Trigger"] = _trigger_value(trigger)
    if refresh:
        response["HX-Refresh"] = "true"
    return response


def hx_response(*, trigger=None, redirect=None, refresh=False, status=204):
    """Build an HTMX response (default 204) with HX-* headers."""
    response = HttpResponse(status=status)
    return set_hx_headers(response, trigger=trigger, redirect=redirect, refresh=refresh)


def htmx_or_redirect(request, url, *, trigger=None):
    """hx_response(redirect=url, trigger=trigger) for HTMX, else a normal redirect."""
    if is_htmx(request):
        return hx_response(redirect=url, trigger=trigger)
    return django_redirect(url)


def render_modal_or_page(request, fragment, page, context=None, **kwargs):
    """Render `fragment` for an htmx request and the full `page` otherwise."""
    response = render(request, fragment if is_htmx(request) else page, context, **kwargs)
    patch_vary_headers(response, ["HX-Request"])
    return response
