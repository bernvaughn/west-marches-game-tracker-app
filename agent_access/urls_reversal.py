from django.urls import path

from .views import reversal

urlpatterns = [
    path("<int:pk>/reverse/", reversal.batch_reverse, name="batch_reverse"),
]
