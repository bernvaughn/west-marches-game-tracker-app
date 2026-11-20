"""Views for starting equipment entry management.

All views subclass :class:`starting_equipment.views.base.StartingEquipmentBaseView`,
so every entry page is protected by ``club_admin_required`` and scoped to the
current club. Views receive ``(club_slug, template_pk[, pk])`` as defined by
``urls_entries.py``.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.htmx import hx_response, is_htmx, render_modal_or_page
from starting_equipment.forms import (
    BackgroundEntryForm,
    BackgroundLineFormSet,
    ClassEntryForm,
    ClassLineFormSet,
    LevelCoinsForm,
    MagicOptionForm,
)
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
    StartingEquipmentLevelCoins,
)

from .base import StartingEquipmentBaseView


def _entry_url(name, club_slug, template_pk, pk=None):
    args = [club_slug, template_pk]
    if pk is not None:
        args.append(pk)
    return reverse(f"starting_equipment:{name}", args=args)


class _EntryListView(StartingEquipmentBaseView):
    """Shared list view for one entry type within a template."""

    template_name = "starting_equipment/entry_list.html"
    related_name = None  # attribute on the template holding the entries
    select_related = ()  # FKs the list template reads per row
    page_title = None
    entry_type = None  # "class" | "background" | "level-coins" | "magic-options"
    create_url_name = None
    edit_url_name = None
    delete_url_name = None

    def get(self, request, club_slug, template_pk):
        template = self.get_club_template_or_404(pk=template_pk)
        entries = getattr(template, self.related_name).select_related(*self.select_related)
        ctx = self.get_template_context(template=template)
        ctx.update(
            {
                "entries": entries,
                "page_title": self.page_title,
                "entry_type": self.entry_type,
                "create_url": _entry_url(self.create_url_name, club_slug, template_pk),
                "edit_url_name": self.edit_url_name,
                "delete_url_name": self.delete_url_name,
            }
        )
        return render(request, self.template_name, ctx)


class _EntryFormView(StartingEquipmentBaseView):
    """Shared create/edit view for an entry with an optional inline line formset."""

    form_class = None
    formset_class = None
    model = None
    page_title = None
    list_url_name = None
    template_name = "starting_equipment/entry_form.html"
    modal_template_name = "starting_equipment/_entry_form_modal.html"

    def get_entry(self, template, pk):
        return get_object_or_404(self.get_club_queryset(self.model), pk=pk, template=template)

    def _forms(self, request, entry=None, template=None):
        form_kwargs = {"club": self.club, "template": template}
        if entry is None:
            form = self.form_class(**form_kwargs)
            formset = self.formset_class(form_kwargs=form_kwargs) if self.formset_class else None
        else:
            form = self.form_class(instance=entry, **form_kwargs)
            formset = (
                self.formset_class(instance=entry, form_kwargs=form_kwargs)
                if self.formset_class
                else None
            )
        return form, formset

    def _context(self, template, entry, form, formset):
        ctx = self.get_template_context(template=template)
        ctx.update(
            {
                "page_title": self.page_title,
                "entry": entry,
                "form": form,
                "formset": formset,
                "is_create": entry is None,
                "list_url": _entry_url(self.list_url_name, self.club.slug, template.pk),
            }
        )
        return ctx

    def get(self, request, club_slug, template_pk, pk=None):
        template = self.get_club_template_or_404(pk=template_pk)
        entry = self.get_entry(template, pk) if pk is not None else None
        form, formset = self._forms(request, entry, template)
        return render_modal_or_page(
            request,
            self.modal_template_name,
            self.template_name,
            self._context(template, entry, form, formset),
        )

    def _save_success(self, request, club_slug, template_pk):
        messages.success(request, f"{self.page_title} saved.")
        if is_htmx(request):
            return hx_response(trigger={"entrySaved": True, "appModalClose": True})
        return redirect(_entry_url(self.list_url_name, club_slug, template_pk))

    def post(self, request, club_slug, template_pk, pk=None):
        template = self.get_club_template_or_404(pk=template_pk)
        entry = self.get_entry(template, pk) if pk is not None else None
        form_kwargs = {"club": self.club, "template": template}

        if entry is None:
            # Create: the inline line formset needs a persisted parent (its
            # hidden FK field), so persist the entry first and roll back if the
            # lines are invalid.
            form = self.form_class(request.POST, **form_kwargs)
            if not form.is_valid():
                formset = (
                    self.formset_class(form_kwargs=form_kwargs) if self.formset_class else None
                )
                return render_modal_or_page(
                    request,
                    self.modal_template_name,
                    self.template_name,
                    self._context(template, None, form, formset),
                )
            entry = form.save(commit=False)
            entry.template = template
            entry.save()
            formset = (
                self.formset_class(request.POST, instance=entry, form_kwargs=form_kwargs)
                if self.formset_class
                else None
            )
            if formset is None or formset.is_valid():
                if formset is not None:
                    formset.instance = entry
                    formset.save()
                return self._save_success(request, club_slug, template_pk)
            entry.delete()
            return render_modal_or_page(
                request,
                self.modal_template_name,
                self.template_name,
                self._context(template, None, form, formset),
            )

        # Edit.
        form = self.form_class(request.POST, instance=entry, **form_kwargs)
        formset = (
            self.formset_class(request.POST, instance=entry, form_kwargs=form_kwargs)
            if self.formset_class
            else None
        )
        if form.is_valid() and (formset is None or formset.is_valid()):
            form.save()
            if self.formset_class is not None:
                formset.instance = entry
                formset.save()
            return self._save_success(request, club_slug, template_pk)
        return render_modal_or_page(
            request,
            self.modal_template_name,
            self.template_name,
            self._context(template, entry, form, formset),
        )


class _EntryDeleteView(StartingEquipmentBaseView):
    """Shared delete view: GET shows a confirm, POST deletes the entry."""

    model = None
    page_title = None
    list_url_name = None
    delete_url_name = None

    def get_entry(self, template, pk):
        return get_object_or_404(self.get_club_queryset(self.model), pk=pk, template=template)

    def get(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        entry = self.get_entry(template, pk)
        ctx = self.get_template_context(template=template)
        ctx.update(
            {
                "page_title": self.page_title,
                "entry": entry,
                "confirm_url": _entry_url(self.delete_url_name, club_slug, template_pk, pk),
                "list_url": _entry_url(self.list_url_name, club_slug, template_pk),
            }
        )
        return render(request, "starting_equipment/_entry_delete_confirm.html", ctx)

    def post(self, request, club_slug, template_pk, pk):
        template = self.get_club_template_or_404(pk=template_pk)
        entry = self.get_entry(template, pk)
        entry.delete()
        messages.success(request, f"{self.page_title} deleted.")
        if is_htmx(request):
            return hx_response(trigger={"entryDeleted": True, "appModalClose": True})
        return redirect(_entry_url(self.list_url_name, club_slug, template_pk))


# ---------------------------------------------------------------------------
# Class entries
# ---------------------------------------------------------------------------


class ClassEntryListView(_EntryListView):
    related_name = "class_entries"
    select_related = ("class_option",)
    page_title = "Class entries"
    entry_type = "class"
    create_url_name = "class_entry_create"
    edit_url_name = "class_entry_edit"
    delete_url_name = "class_entry_delete"


class ClassEntryCreateView(_EntryFormView):
    form_class = ClassEntryForm
    formset_class = ClassLineFormSet
    model = StartingEquipmentClassEntry
    page_title = "Class entry"
    list_url_name = "class_entry_list"


class ClassEntryEditView(ClassEntryCreateView):
    pass


class ClassEntryDeleteView(_EntryDeleteView):
    model = StartingEquipmentClassEntry
    page_title = "Class entry"
    list_url_name = "class_entry_list"
    delete_url_name = "class_entry_delete"


# ---------------------------------------------------------------------------
# Background entries
# ---------------------------------------------------------------------------


class BackgroundEntryListView(_EntryListView):
    related_name = "background_entries"
    select_related = ("background_option",)
    page_title = "Background entries"
    entry_type = "background"
    create_url_name = "background_entry_create"
    edit_url_name = "background_entry_edit"
    delete_url_name = "background_entry_delete"


class BackgroundEntryCreateView(_EntryFormView):
    form_class = BackgroundEntryForm
    formset_class = BackgroundLineFormSet
    model = StartingEquipmentBackgroundEntry
    page_title = "Background entry"
    list_url_name = "background_entry_list"


class BackgroundEntryEditView(BackgroundEntryCreateView):
    pass


class BackgroundEntryDeleteView(_EntryDeleteView):
    model = StartingEquipmentBackgroundEntry
    page_title = "Background entry"
    list_url_name = "background_entry_list"
    delete_url_name = "background_entry_delete"


# ---------------------------------------------------------------------------
# Level coins
# ---------------------------------------------------------------------------


class LevelCoinsListView(_EntryListView):
    related_name = "level_coins"
    page_title = "Level coins"
    entry_type = "level-coins"
    create_url_name = "level_coins_create"
    edit_url_name = "level_coins_edit"
    delete_url_name = "level_coins_delete"


class LevelCoinsCreateView(_EntryFormView):
    form_class = LevelCoinsForm
    formset_class = None
    model = StartingEquipmentLevelCoins
    page_title = "Level coins"
    list_url_name = "level_coins_list"


class LevelCoinsEditView(LevelCoinsCreateView):
    pass


class LevelCoinsDeleteView(_EntryDeleteView):
    model = StartingEquipmentLevelCoins
    page_title = "Level coins"
    list_url_name = "level_coins_list"
    delete_url_name = "level_coins_delete"


# ---------------------------------------------------------------------------
# Magic item options
# ---------------------------------------------------------------------------


class MagicOptionListView(_EntryListView):
    related_name = "magic_options"
    page_title = "Magic item options"
    entry_type = "magic-options"
    create_url_name = "magic_option_create"
    edit_url_name = "magic_option_edit"
    delete_url_name = "magic_option_delete"


class MagicOptionCreateView(_EntryFormView):
    form_class = MagicOptionForm
    formset_class = None
    model = MagicItemStartingOption
    page_title = "Magic item option"
    list_url_name = "magic_option_list"
    template_name = "starting_equipment/magic_option_form.html"
    modal_template_name = "starting_equipment/_magic_option_form_modal.html"


class MagicOptionEditView(MagicOptionCreateView):
    pass


class MagicOptionDeleteView(_EntryDeleteView):
    model = MagicItemStartingOption
    page_title = "Magic item option"
    list_url_name = "magic_option_list"
    delete_url_name = "magic_option_delete"
