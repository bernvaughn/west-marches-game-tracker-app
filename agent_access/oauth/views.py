import json
import logging
from functools import wraps

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_application_model
from oauth2_provider.views import AuthorizationView, DynamicClientRegistrationView
from oauth2_provider.www_authenticate import build_bearer_challenge
from rest_framework.decorators import throttle_classes

from agent_access.mcp.server import mcp_view
from agent_access.throttles import DCRAnonThrottle, MCPAnonThrottle, OAuthAnonThrottle

from .forms import ConsentForm
from .tokens import create_connection, prepare_approval

oauth_logger = logging.getLogger("security.oauth")

RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"

CORS_ALLOW_HEADERS = (
    "Authorization, Content-Type, Mcp-Protocol-Version, Mcp-Session-Id, Accept"
)
CORS_ALLOW_METHODS = "GET, POST, DELETE, OPTIONS"
CORS_EXPOSE_HEADERS = "WWW-Authenticate, Mcp-Session-Id"


def _get_cors_origin(request):
    """Determine the Access-Control-Allow-Origin value for the request.
    
    In DEBUG mode, allow any origin (*).
    In production, only allow origins in ALLOWED_MCP_ORIGINS.
    Returns the origin to allow, or None if the origin is not allowed.
    """
    origin = request.headers.get("Origin")
    if not origin:
        return None
    
    if settings.DEBUG:
        return "*"
    
    allowed_origins = getattr(settings, "ALLOWED_MCP_ORIGINS", [])
    if origin in allowed_origins:
        return origin
    
    return None


def cors(view):
    """Let browser-based MCP clients (Inspector direct mode) reach the OAuth and MCP routes.
    
    Validates Origin header against ALLOWED_MCP_ORIGINS in production.
    In DEBUG mode, allows any origin (*).
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        allowed_origin = _get_cors_origin(request)
        
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = view(request, *args, **kwargs)
        
        if allowed_origin:
            response["Access-Control-Allow-Origin"] = allowed_origin
            response["Access-Control-Allow-Headers"] = CORS_ALLOW_HEADERS
            response["Access-Control-Allow-Methods"] = CORS_ALLOW_METHODS
            response["Access-Control-Expose-Headers"] = CORS_EXPOSE_HEADERS
            response["Vary"] = "Origin"
        
        return response

    return wrapped


@csrf_exempt
@cors
@throttle_classes([MCPAnonThrottle])
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
    throttle_classes = [DCRAnonThrottle]

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or b"{}")
        except ValueError:
            oauth_logger.warning("DCR registration failed: invalid JSON")
            return _bad_metadata("Body must be JSON.")
        if not isinstance(data, dict):
            oauth_logger.warning("DCR registration failed: body not a JSON object")
            return _bad_metadata("Body must be a JSON object.")
        if data.get("token_endpoint_auth_method") != "none":
            oauth_logger.warning(
                "DCR registration failed: invalid token_endpoint_auth_method",
                extra={"token_endpoint_auth_method": data.get("token_endpoint_auth_method")},
            )
            return _bad_metadata(
                "Only public clients are allowed: token_endpoint_auth_method must be none."
            )
        grants = data.get("grant_types", ["authorization_code"])
        if not isinstance(grants, list) or not set(grants) <= {
            "authorization_code",
            "refresh_token",
        }:
            oauth_logger.warning(
                "DCR registration failed: invalid grant_types",
                extra={"grant_types": grants},
            )
            return _bad_metadata("grant_types must be authorization_code and refresh_token only.")
        
        oauth_logger.info(
            "DCR registration attempted",
            extra={
                "client_name": data.get("client_name"),
                "redirect_uris": data.get("redirect_uris"),
            },
        )
        return super().post(request, *args, **kwargs)


class ConsentView(AuthorizationView):
    template_name = "agent_access/oauth/authorize.html"
    form_class = ConsentForm
    throttle_classes = [OAuthAnonThrottle]

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
        client_id = form.cleaned_data.get("client_id")
        allow = form.cleaned_data.get("allow")
        user = self.request.user
        
        if not allow:
            oauth_logger.info(
                "OAuth authorization denied by user",
                extra={"user_id": user.id, "client_id": client_id},
            )
            return super().form_valid(form)
        
        application = (
            get_application_model().objects.filter(client_id=client_id).first()
        )
        if application is None:
            oauth_logger.warning(
                "OAuth authorization failed: unknown client",
                extra={"user_id": user.id, "client_id": client_id},
            )
            return HttpResponse("Unknown client.", status=400, content_type="text/plain")
        
        with transaction.atomic():
            prepare_approval(user, application)
            response = super().form_valid(form)
            if response.status_code != 302 or "code=" not in response.get("Location", ""):
                transaction.set_rollback(True)
                return response
            create_connection(user, form.cleaned_data["club"], application)
        
        oauth_logger.info(
            "OAuth authorization granted",
            extra={
                "user_id": user.id,
                "client_id": client_id,
                "club_id": form.cleaned_data["club"],
            },
        )
        return response
