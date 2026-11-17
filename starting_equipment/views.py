from django.http import HttpResponse
from django.views import View


class StartingEquipmentPlaceholderView(View):
    """Placeholder view for starting equipment URLs (to be implemented in SE3)."""

    def get(self, request, *args, **kwargs):
        return HttpResponse("Starting Equipment - Coming Soon")