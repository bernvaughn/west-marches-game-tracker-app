"""Shared club-scoped base view/mixin for starting equipment admin."""

from django.utils.decorators import method_decorator
from django.views import View

from accounts.mixins import ClubContextMixin, ClubScopedMixin, PermissionMixin
from accounts.permissions import club_admin_required
from starting_equipment.models import StartingEquipmentTemplate


@method_decorator(club_admin_required, name="dispatch")
class StartingEquipmentBaseView(ClubScopedMixin, ClubContextMixin, PermissionMixin, View):
    """Base view for starting equipment admin pages.

    Combines ClubScopedMixin, ClubContextMixin and PermissionMixin, and
    requires the club_admin_required permission on every dispatch. All
    starting equipment admin views should subclass this.
    """

    def get_club_template_queryset(self):
        """Return StartingEquipmentTemplate queryset scoped to the current club."""
        return self.get_club_queryset(StartingEquipmentTemplate)

    def get_club_template_or_404(self, **kwargs):
        """Return a club-scoped StartingEquipmentTemplate or raise Http404."""
        return self.get_club_object_or_404(StartingEquipmentTemplate, **kwargs)

    def get_template_context(self, template=None):
        """Build common template context: club, template, is_admin."""
        return {
            "club": self.club,
            "template": template,
            "is_admin": self.is_club_admin(self.user, self.club),
        }
