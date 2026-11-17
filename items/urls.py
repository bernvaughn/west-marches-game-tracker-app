from django.urls import path

from . import views

app_name = "items"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("new/", views.CreateView.as_view(), name="create"),
    path("references/", views.ReferencesView.as_view(), name="references"),
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    path("<int:pk>/details-modal/", views.DetailsModalView.as_view(), name="details_modal"),
    path("<int:pk>/where-to-buy/", views.WhereToBuyView.as_view(), name="where_to_buy"),
    path("<int:pk>/edit/", views.EditView.as_view(), name="edit"),
    path("<int:pk>/retire/", views.RetireView.as_view(), name="retire"),
    path("<int:pk>/restore/", views.RestoreView.as_view(), name="restore"),
    path("<int:pk>/delete/", views.DeleteView.as_view(), name="delete"),
    path("loot-cards/", views.LootCardsPickerView.as_view(), name="loot_cards_picker"),
    path("loot-cards/print/", views.LootCardsPrintView.as_view(), name="loot_cards_print"),
]