"""Stub views for starting equipment entry management."""

from django.shortcuts import render

from .base import StartingEquipmentBaseView


class ClassEntryListView(StartingEquipmentBaseView):
    """List class entries for a template (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class ClassEntryCreateView(StartingEquipmentBaseView):
    """Create a class entry (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class ClassEntryEditView(StartingEquipmentBaseView):
    """Edit a class entry (stub)."""

    def get(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class ClassEntryDeleteView(StartingEquipmentBaseView):
    """Delete a class entry (stub)."""

    def post(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class BackgroundEntryListView(StartingEquipmentBaseView):
    """List background entries for a template (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class BackgroundEntryCreateView(StartingEquipmentBaseView):
    """Create a background entry (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class BackgroundEntryEditView(StartingEquipmentBaseView):
    """Edit a background entry (stub)."""

    def get(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class BackgroundEntryDeleteView(StartingEquipmentBaseView):
    """Delete a background entry (stub)."""

    def post(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class LevelCoinsListView(StartingEquipmentBaseView):
    """List level coins for a template (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class LevelCoinsCreateView(StartingEquipmentBaseView):
    """Create level coins (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class LevelCoinsEditView(StartingEquipmentBaseView):
    """Edit level coins (stub)."""

    def get(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class LevelCoinsDeleteView(StartingEquipmentBaseView):
    """Delete level coins (stub)."""

    def post(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class MagicOptionListView(StartingEquipmentBaseView):
    """List magic item options for a template (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class MagicOptionCreateView(StartingEquipmentBaseView):
    """Create a magic item option (stub)."""

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class MagicOptionEditView(StartingEquipmentBaseView):
    """Edit a magic item option (stub)."""

    def get(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})


class MagicOptionDeleteView(StartingEquipmentBaseView):
    """Delete a magic item option (stub)."""

    def post(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        return render(request, "starting_equipment/template_list.html", {"template": template})
