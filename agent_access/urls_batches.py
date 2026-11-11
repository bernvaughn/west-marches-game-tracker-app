from django.urls import path

from .views import batches

urlpatterns = [
    path("", batches.batch_list, name="batches"),
    path("<int:pk>/", batches.batch_detail, name="batch_detail"),
    path("<int:pk>/confirm/", batches.batch_confirm, name="batch_confirm"),
    path("<int:pk>/discard/", batches.batch_discard, name="batch_discard"),
]
