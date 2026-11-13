from django.urls import path

from . import views

app_name = "items"
urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.create, name="create"),
    path("references/", views.references, name="references"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/where-to-buy/", views.where_to_buy, name="where_to_buy"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/retire/", views.retire, name="retire"),
    path("<int:pk>/restore/", views.restore, name="restore"),
    path("<int:pk>/delete/", views.delete, name="delete"),
]
