from django.urls import path

from .views import templates as template_views

urlpatterns = [
    path("", template_views.TemplateListView.as_view(), name="templates"),
    path("new/", template_views.TemplateCreateView.as_view(), name="template_create"),
    path("<int:pk>/", template_views.TemplateDetailView.as_view(), name="template_detail"),
    path("<int:pk>/edit/", template_views.TemplateEditView.as_view(), name="template_edit"),
    path("<int:pk>/delete/", template_views.TemplateDeleteView.as_view(), name="template_delete"),
    path(
        "<int:pk>/set-active/",
        template_views.TemplateSetActiveView.as_view(),
        name="template_set_active",
    ),
]
