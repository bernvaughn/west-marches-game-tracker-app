from django.contrib import messages
from django.shortcuts import redirect, render

from ..forms.site_settings import SiteSettingsForm
from ..models import SiteSettings
from ..permissions import site_admin_required


@site_admin_required
def site_settings(request):
    obj = SiteSettings.load()
    if request.method == "POST":
        form = SiteSettingsForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Site settings saved.")
            return redirect("site_settings")
    else:
        form = SiteSettingsForm(instance=obj)
    return render(request, "accounts/site_settings/form.html", {"form": form})
