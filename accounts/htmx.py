"""htmx helpers (U33). The project has no django-htmx; detect the header directly."""

from django.shortcuts import render
from django.utils.cache import patch_vary_headers


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def render_modal_or_page(request, fragment, page, context=None, **kwargs):
    """Render `fragment` for an htmx request and the full `page` otherwise."""
    response = render(request, fragment if is_htmx(request) else page, context, **kwargs)
    patch_vary_headers(response, ["HX-Request"])
    return response
