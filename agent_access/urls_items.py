from django.urls import path

from .views import items

urlpatterns = [
    path("", items.proposed_item_list, name="proposed_items"),
    path("<int:pk>/", items.proposed_item_detail, name="proposed_item_detail"),
    path("<int:pk>/approve/", items.proposed_item_approve, name="proposed_item_approve"),
    path("<int:pk>/reject/", items.proposed_item_reject, name="proposed_item_reject"),
]
