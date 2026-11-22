"""Club-scoped mail URLs."""

from django.urls import path

from .views.contact import contact_email
from .views.test_email import test_email

club_urlpatterns = [
    path("contact-email/", contact_email, name="contact_email"),
    path("test-email/", test_email, name="test_email"),
]