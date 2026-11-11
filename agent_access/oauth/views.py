import json
from functools import wraps

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_application_model
from oauth2_provider.views import AuthorizationView, DynamicClientRegistrationView
from oauth2_provider.www_authenticate import build_bearer_challenge

from agent_access.mcp.server import mcp_view

from .forms import ConsentForm
from .tokens import create_connection, prepare_approval

RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": (
        "Authorization, Content-Type, Mcp-Protocol-Version, Mcp-Session-Id, Accept"
    ),
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Expose-Headers": "WWW-Authenticate, Mcp-Session-Id",
}


def cors(view):
    """Let browser-based MCP clients (Inspector direct mode) reach the OAuth and MCP routes."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = view(request, *args, **kwargs)
        for key, value in CORS_HEADERS.items():
            response[key] = value
        return response

    return wrapped


@csrf_exempt
@cors
def mcp_entry(request, *args, **kwargs):
    response = mcp_view(request, *args, **kwargs)
    if response.status_code == 401:
        url = request.build_absolute_uri(RESOURCE_METADATA_PATH)
        response["WWW-Authenticate"] = build_bearer_challenge(request, resource_metadata_url=url)
    return response


def _bad_metadata(description):
    return JsonResponse(
        {"error": "invalid_client_metadata", "error_description": description}, status=400
    )


class PublicClientRegistrationView(DynamicClientRegistrationView):
    """Dynamic client registration for public (no secret) clients only."""

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or b"{}")
        except ValueError:
            return _bad_metadata("Body must be JSON.")
        if not isinstance(data, dict):
            return _bad_metadata("Body must be a JSON object.")
        if data.get("token_endpoint_auth_method") != "none":
            return _bad_metadata(
                "Only public clients are allowed: token_endpoint_auth_method must be none."
            )
        grants = data.get("grant_types", ["authorization_code"])
        if not isinstance(grants, list) or not set(grants) <= {
            "authorization_code",
            "refresh_token",
        }:
            return _bad_metadata("grant_types must be authorization_code and refresh_token only.")
        return super().post(request, *args, **kwargs)


class ConsentView(AuthorizationView):
    template_name = "agent_access/oauth/authorize.html"
    form_class = ConsentForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        # A client must not skip the consent page: approving is what makes the connection.
        if "approval_prompt" in request.GET:
            request.GET = request.GET.copy()
            del request.GET["approval_prompt"]
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        if not form.cleaned_data.get("allow"):
            return super().form_valid(form)
        application = (
            get_application_model().objects.filter(client_id=form.cleaned_data["client_id"]).first()
        )
        if application is None:
            return HttpResponse("Unknown client.", status=400, content_type="text/plain")
        user = self.request.user
        with transaction.atomic():
            prepare_approval(user, application)
            response = super().form_valid(form)
            if response.status_code != 302 or "code=" not in response.get("Location", ""):
                transaction.set_rollback(True)
                return response
            create_connection(user, form.cleaned_data["club"], application)
        return response
