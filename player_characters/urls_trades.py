from django.urls import path

from .views import trade_detail, trade_sides, trade_status, trades

app_name = "trades"
urlpatterns = [
    path("", trades.index, name="index"),
    path("new/", trades.propose, name="propose"),
    path("<int:pk>/", trade_detail.detail, name="detail"),
    path("<int:pk>/accept/", trade_status.accept, name="accept"),
    path("<int:pk>/decline/", trade_status.decline, name="decline"),
    path("<int:pk>/cancel/", trade_status.cancel, name="cancel"),
    path("<int:pk>/side/", trade_sides.edit_side, name="edit_side"),
    path("<int:pk>/approve/", trade_sides.approve, name="approve"),
]
