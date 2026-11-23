"""Club-scoped mail log URLs."""

from django.urls import path

from .views.log import clear_flag, email_log
from .views.webhook import resend_webhook

club_urlpatterns = [
    path("log/", email_log, name="log"),
    path("log/clear-flag/", clear_flag, name="clear_flag"),
]

public_urlpatterns = [
    path("webhook/resend/", resend_webhook, name="webhook_resend"),
]
