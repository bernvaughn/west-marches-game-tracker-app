"""All OAuth routes live in one `oauth2_provider` namespace: DOT's metadata views reverse it."""

from django.urls import path
from oauth2_provider import views as dot

from . import views

app_name = "oauth2_provider"

urlpatterns = [
    path(
        ".well-known/oauth-authorization-server",
        views.cors(dot.OAuthServerMetadataView.as_view()),
        name="oauth-server-metadata",
    ),
    path(
        ".well-known/oauth-protected-resource",
        views.cors(dot.OAuthProtectedResourceMetadataView.as_view()),
        name="oauth-resource-metadata",
    ),
    path(
        ".well-known/oauth-protected-resource/<path:resource_path>",
        views.cors(dot.OAuthProtectedResourceMetadataView.as_view()),
        name="oauth-resource-metadata-path",
    ),
    path("oauth/authorize/", views.ConsentView.as_view(), name="authorize"),
    path("oauth/token/", views.cors(dot.TokenView.as_view()), name="token"),
    path("oauth/revoke_token/", views.cors(dot.RevokeTokenView.as_view()), name="revoke-token"),
    path(
        "oauth/register/",
        views.cors(views.PublicClientRegistrationView.as_view()),
        name="dcr-register",
    ),
    path(
        "oauth/register/<str:client_id>/",
        views.cors(dot.DynamicClientRegistrationManagementView.as_view()),
        name="dcr-register-management",
    ),
]
