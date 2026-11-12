"""One shared form renderer: every Django form gets compact Bootstrap markup."""

from django.forms.renderers import DjangoTemplates
from django.template.loader import get_template as project_get_template

FORM_TEMPLATES = {
    "django/forms/p.html": "forms/div.html",
    "django/forms/div.html": "forms/div.html",
    "django/forms/table.html": "forms/div.html",
    "django/forms/ul.html": "forms/div.html",
    "django/forms/errors/list/ul.html": "forms/errors.html",
    "django/forms/errors/list/default.html": "forms/errors.html",
}

SELECT_TEMPLATES = {
    "django/forms/widgets/select.html",
    "django/forms/widgets/select_multiple.html",
}

TEXT_TYPES = {"text", "number", "email", "password", "date", "url", "file", "search", "tel"}


def _add_class(attrs, classes):
    existing = attrs.get("class") or ""
    have = set(existing.split())
    extra = " ".join(c for c in classes.split() if c not in have)
    if extra:
        attrs["class"] = f"{existing} {extra}".strip()


def _classes_for(widget):
    kind = widget.get("type")
    name = widget.get("template_name", "")
    if kind == "hidden" or widget.get("is_hidden"):
        return ""
    if kind in ("checkbox", "radio"):
        return "form-check-input"
    if name in SELECT_TEMPLATES:
        return "form-select form-select-sm"
    if "textarea" in name or kind in TEXT_TYPES:
        return "form-control form-control-sm"
    return ""


def apply_bootstrap(widget):
    """Add Bootstrap classes to a widget context, its subwidgets and its options."""
    attrs = widget.setdefault("attrs", {})
    classes = _classes_for(widget)
    if classes and widget.get("subwidgets") is None:
        _add_class(attrs, classes)
    if attrs.get("aria-invalid") == "true" and classes:
        _add_class(attrs, "is-invalid")
    for sub in widget.get("subwidgets") or []:
        apply_bootstrap(sub)
        if attrs.get("aria-invalid") == "true":
            _add_class(sub["attrs"], "is-invalid")
    for _group, options, _index in widget.get("optgroups") or []:
        for option in options:
            apply_bootstrap(option)
    return widget


class BootstrapFormRenderer(DjangoTemplates):
    form_template_name = "forms/div.html"
    field_template_name = "forms/field.html"

    def get_template(self, template_name):
        template_name = FORM_TEMPLATES.get(template_name, template_name)
        if template_name.startswith("forms/"):
            return project_get_template(template_name)
        return super().get_template(template_name)

    def render(self, template_name, context, request=None):
        widget = context.get("widget")
        if isinstance(widget, dict):
            apply_bootstrap(widget)
        template = self.get_template(template_name)
        return template.render(context, request=request).strip()
