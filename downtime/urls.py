from downtime.views.actions import actions_urls
from downtime.views.agenda import agenda_urls
from downtime.views.play import play_urls
from downtime.views.points import points_urls
from downtime.views.requests import requests_urls

app_name = "downtime"

urlpatterns = [
    *points_urls,
    *actions_urls,
    *play_urls,
    *requests_urls,
    *agenda_urls,
]
