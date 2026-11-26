import logging

from django.conf import settings
from django.db import connections
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.templatetags.static import static
from django.views.decorators.csrf import csrf_exempt

from accounts.ratelimit import get_client_ip, rate_limit

logger = logging.getLogger(__name__)


def favicon(request):
    return HttpResponseRedirect(static("favicon.ico"))


@csrf_exempt
@rate_limit(
    prefix="healthz",
    limit=lambda: settings.RATELIMIT_HEALTHZ_ATTEMPTS,
    window=lambda: settings.RATELIMIT_HEALTHZ_WINDOW,
    key_func=get_client_ip,
)
def healthz(request):
    """Health check: reports whether the default database is reachable.

    No login, no club, no session, no cookies. Only GET and HEAD are allowed.
    """
    if request.method not in ("GET", "HEAD"):
        response = HttpResponseNotAllowed(["GET", "HEAD"])
        response["Cache-Control"] = "no-store"
        return response

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("healthz database check failed")
        response = HttpResponse("database unavailable", status=503, content_type="text/plain")
        response["Cache-Control"] = "no-store"
        return response

    response = HttpResponse("ok", content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response
