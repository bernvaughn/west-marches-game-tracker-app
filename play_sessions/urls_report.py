"""URLs for the attendance report (mounted under c/<club_slug>/sessions/)."""

from django.urls import path

from .views import report

urlpatterns = [
    path("report/", report.report, name="report"),
    path("report/export.csv", report.report_csv, name="report_csv"),
]
