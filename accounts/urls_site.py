from django.urls import path

from .views import clubs, core, design, feedback, passwords, public, site_settings

urlpatterns = [
    path("about/", public.about, name="about"),
    path("plans/", public.plans, name="plans"),
    path("accounts/login/", core.rate_limited_login, name="login"),
    path("accounts/password_change/", passwords.password_change, name="password_change"),
    path("feedback/", feedback.feedback_new, name="feedback_new"),
    path("site/clubs/", clubs.club_list, name="site_clubs"),
    path("site/clubs/new/", clubs.club_new, name="site_club_new"),
    path("site/feedback/", feedback.feedback_list, name="site_feedback"),
    path(
        "site/feedback/<int:pk>/status/",
        feedback.feedback_status,
        name="site_feedback_status",
    ),
    path("site/settings/", site_settings.site_settings, name="site_settings"),
    path("site/design/", design.design_reference, name="site_design"),
]
