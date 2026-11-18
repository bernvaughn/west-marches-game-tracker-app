"""Stub views for starting equipment template CRUD."""

from django.shortcuts import render

from .base import StartingEquipmentBaseView


class TemplateListView(StartingEquipmentBaseView):
    """List starting equipment templates for the club."""

    def get(self, request, club_slug):
        templates = self.get_club_template_queryset()
        return render(request, "starting_equipment/template_list.html", {"templates": templates})


class TemplateCreateView(StartingEquipmentBaseView):
    """Create a starting equipment template (stub)."""

    def get(self, request, club_slug):
        return render(request, "starting_equipment/template_list.html", {"templates": []})


class TemplateDetailView(StartingEquipmentBaseView):
    """Detail view for a starting equipment template (stub)."""

    def get(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        return render(request, "starting_equipment/template_list.html", {"templates": [template]})


class TemplateEditView(StartingEquipmentBaseView):
    """Edit a starting equipment template (stub)."""

    def get(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        return render(request, "starting_equipment/template_list.html", {"templates": [template]})


class TemplateDeleteView(StartingEquipmentBaseView):
    """Delete a starting equipment template (stub)."""

    def get(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        return render(request, "starting_equipment/template_list.html", {"templates": [template]})


class TemplateSetActiveView(StartingEquipmentBaseView):
    """Set a template as the active template for the club (stub)."""

    def post(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        return render(request, "starting_equipment/template_list.html", {"templates": [template]})
