from django.urls import path

from .views import batches

urlpatterns = [
    path("", batches.batch_list, name="batches"),
    path("<int:pk>/", batches.batch_detail, name="batch_detail"),
    path("<int:pk>/confirm/", batches.batch_confirm, name="batch_confirm"),
    path("<int:pk>/discard/", batches.batch_discard, name="batch_discard"),
    path("<int:pk>/lines/<int:line_pk>/edit/", batches.batch_line_edit, name="batch_line_edit"),
    path(
        "<int:pk>/lines/<int:line_pk>/remove/", batches.batch_line_remove, name="batch_line_remove"
    ),
]
