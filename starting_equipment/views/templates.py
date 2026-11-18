"""Views for starting equipment template CRUD."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from starting_equipment.forms import TemplateForm
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.views.base import StartingEquipmentBaseView


class TemplateListView(StartingEquipmentBaseView):
    """List starting equipment templates for the club."""

    def get(self, request, club_slug):
        templates = self.get_club_template_queryset().order_by("-is_active", "name")
        context = self.get_template_context()
        context["templates"] = templates
        return render(request, "starting_equipment/template_list.html", context)


class TemplateCreateView(StartingEquipmentBaseView):
    """Create a starting equipment template."""

    def get(self, request, club_slug):
        form = TemplateForm(club=request.club)
        context = self.get_template_context()
        context["form"] = form
        context["action"] = "create"
        return render(request, "starting_equipment/template_form.html", context)

    def post(self, request, club_slug):
        form = TemplateForm(request.POST, club=request.club)
        if form.is_valid():
            template = form.save()
            messages.success(request, f"Template '{template.name}' created.")
            return redirect("starting_equipment:templates", club_slug=club_slug)
        context = self.get_template_context()
        context["form"] = form
        context["action"] = "create"
        return render(request, "starting_equipment/template_form.html", context)


class TemplateDetailView(StartingEquipmentBaseView):
    """Detail view for a starting equipment template."""

    def get(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        context = self.get_template_context(template=template)
        context["class_entries"] = template.class_entries.select_related(
            "template"
        ).prefetch_related("lines__item")
        context["background_entries"] = template.background_entries.select_related(
            "template"
        ).prefetch_related("lines__item")
        context["level_coins"] = template.level_coins.all()
        context["magic_options"] = template.magic_options.select_related("item")
        return render(request, "starting_equipment/template_detail.html", context)


class TemplateEditView(StartingEquipmentBaseView):
    """Edit a starting equipment template."""

    def get(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        form = TemplateForm(instance=template, club=request.club)
        context = self.get_template_context(template=template)
        context["form"] = form
        context["action"] = "edit"
        return render(request, "starting_equipment/template_form.html", context)

    def post(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        form = TemplateForm(request.POST, instance=template, club=request.club)
        if form.is_valid():
            template = form.save()
            messages.success(request, f"Template '{template.name}' updated.")
            return redirect("starting_equipment:templates", club_slug=club_slug)
        context = self.get_template_context(template=template)
        context["form"] = form
        context["action"] = "edit"
        return render(request, "starting_equipment/template_form.html", context)


class TemplateDeleteView(StartingEquipmentBaseView):
    """Delete a starting equipment template."""

    def get(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        context = self.get_template_context(template=template)
        return render(request, "starting_equipment/template_delete_confirm.html", context)

    def post(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        name = template.name
        template.delete()
        messages.success(request, f"Template '{name}' deleted.")
        return redirect("starting_equipment:templates", club_slug=club_slug)


@method_decorator(require_POST, name="dispatch")
class TemplateSetActiveView(StartingEquipmentBaseView):
    """Set a template as the active template for the club."""

    def post(self, request, club_slug, pk):
        template = self.get_club_template_or_404(pk=pk)
        if template.is_active:
            messages.info(request, f"Template '{template.name}' is already active.")
            return redirect("starting_equipment:templates", club_slug=club_slug)

        with transaction.atomic():
            # Deactivate all templates for this club
            StartingEquipmentTemplate.objects.for_club(request.club).update(is_active=False)
            # Activate the selected template
            template.is_active = True
            template.save(update_fields=["is_active", "updated"])

        messages.success(request, f"Template '{template.name}' set as active.")
        return redirect("starting_equipment:templates", club_slug=club_slug)
