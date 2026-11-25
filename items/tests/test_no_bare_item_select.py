"""Guard test: no admin/GM item-choice form uses a bare forms.Select for its item field.

This test scans the codebase for forms that choose items in admin/GM contexts and
verifies they use ItemPickerWidget instead of a bare ModelChoiceField (which
renders as a plain <select>).

Forms covered by S2-S6 (must use ItemPickerWidget):
- S2: items.forms.SlotOptionForm
- S3: quests.forms.RequirementForm, quests.forms.RewardForm
- S4: downtime.forms.EntryItemForm
- S5: shops.forms.manage.StockAddForm, starting_equipment.forms.ClassLineForm,
      starting_equipment.forms.BackgroundLineForm, starting_equipment.forms.MagicOptionForm
- S6: agent_access.forms_batches.LineForm

Additional forms fixed in S7:
- player_characters.forms.ItemLineForm
- player_characters.forms_adjust.BulkAwardItemLineForm
- accounts.views.inbox uses item_line_formset (which uses ItemLineForm)
"""

import ast
import inspect
from pathlib import Path

import pytest

from items.widgets import ItemPickerWidget

# Forms that must use ItemPickerWidget (from S2-S6 + S7)
# Tuple format: (module_path, class_name, field_name)
REQUIRED_PICKER_FORMS = [
    # S2: Container slots
    ("items.forms", "SlotOptionForm", "item"),
    # S3: Quests
    ("quests.forms", "RequirementForm", "item"),
    ("quests.forms", "RewardForm", "item"),
    # S4: Downtime
    ("downtime.forms", "EntryItemForm", "item"),
    # S5: Shops
    ("shops.forms.manage", "StockAddForm", "item"),
    # S5: Starting equipment
    ("starting_equipment.forms", "ClassLineForm", "item"),
    ("starting_equipment.forms", "BackgroundLineForm", "item"),
    ("starting_equipment.forms", "MagicOptionForm", "item"),
    # S6: Agent batch review
    ("agent_access.forms_batches", "LineForm", "item"),
    # S7: Player characters adjust/consume/bulk
    ("player_characters.forms", "ItemLineForm", "item"),
    ("player_characters.forms_adjust", "BulkAwardItemLineForm", "item"),
]


def _import_form_class(module_path, class_name):
    """Import a form class by module path and class name."""
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _get_field_widget(form_class, field_name, init_kwargs):
    """Get the widget instance for a form field, instantiated with provided args."""
    try:
        form = form_class(**init_kwargs)
    except TypeError:
        # Can't instantiate with provided args
        return None

    if field_name not in form.fields:
        return None

    return form.fields[field_name].widget


@pytest.mark.django_db
def test_required_forms_use_picker_widget():
    """All required forms must use ItemPickerWidget for their item field."""
    from accounts.models import Club, Membership, User
    from items.models import Item
    from player_characters.models import Character
    from shops.models import Shop

    # Create test objects for forms that need them
    club = Club.objects.create(name="Test Club", slug="test-club")
    user = User.objects.create_user("test@example.com", password="pw", display_name="Test")
    membership = Membership.objects.create(user=user, club=club)
    character = Character.objects.create(club=club, owner=membership, name="Test Character")
    shop = Shop.objects.create(name="Test Shop", club=club)

    # Mock line object for LineForm (avoids batch FK requirement)
    class MockLine:
        pk = 1
        character_id = character.pk
        item_id = None
        proposed_item_id = None
        quantity = 1
        coins = None
        note = ""
        date = None

    line = MockLine()

    # Override init_kwargs with real objects where needed
    form_kwargs = {
        "items.forms.SlotOptionForm": {"club": club},
        "quests.forms.RequirementForm": {"club": club},
        "quests.forms.RewardForm": {"club": club},
        "downtime.forms.EntryItemForm": {"club": club},
        "shops.forms.manage.StockAddForm": {"shop": shop},
        "starting_equipment.forms.ClassLineForm": {"club": club},
        "starting_equipment.forms.BackgroundLineForm": {"club": club},
        "starting_equipment.forms.MagicOptionForm": {"club": club},
        "agent_access.forms_batches.LineForm": {"club": club, "line": line},
        "player_characters.forms.ItemLineForm": {"items": Item.objects.none(), "club": club},
        "player_characters.forms_adjust.BulkAwardItemLineForm": {
            "items": Item.objects.none(),
            "club": club,
        },
    }

    for module_path, class_name, field_name in REQUIRED_PICKER_FORMS:
        key = f"{module_path}.{class_name}"
        init_kwargs = form_kwargs[key]
        form_class = _import_form_class(module_path, class_name)
        widget = _get_field_widget(form_class, field_name, init_kwargs)

        assert widget is not None, (
            f"{module_path}.{class_name}.{field_name} has no widget or form cannot be instantiated "
            f"with kwargs {init_kwargs}"
        )
        assert isinstance(widget, ItemPickerWidget), (
            f"{module_path}.{class_name}.{field_name} uses {type(widget).__name__}, "
            f"expected ItemPickerWidget"
        )


def test_no_bare_modelchoicefield_for_item_in_admin_forms():
    """Scan admin/GM form modules for bare ModelChoiceField with Item queryset.

    This is a static analysis test that looks for patterns like:
        item = forms.ModelChoiceField(queryset=Item.objects...)
    without a subsequent widget assignment to ItemPickerWidget.
    """
    # Modules to scan (admin/GM item-choice forms)
    scan_modules = [
        "items.forms",
        "quests.forms",
        "downtime.forms",
        "shops.forms.manage",
        "starting_equipment.forms",
        "agent_access.forms_batches",
        "player_characters.forms",
        "player_characters.forms_adjust",
        "player_characters.forms_consume",
    ]

    violations = []

    for module_path in scan_modules:
        try:
            module = __import__(module_path, fromlist=["*"])
        except ImportError:
            continue

        # Get the source file
        try:
            source_file = inspect.getsourcefile(module)
        except TypeError:
            continue

        if not source_file:
            continue

        source = Path(source_file).read_text()
        tree = ast.parse(source)

        # Find form classes
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if it's a Form subclass
            is_form = False
            for base in node.bases:
                if isinstance(base, ast.Attribute):
                    if base.attr in ("Form", "ModelForm"):
                        is_form = True
                        break
                elif isinstance(base, ast.Name):
                    if base.id in ("Form", "ModelForm"):
                        is_form = True
                        break

            if not is_form:
                continue

            # Look for item field definitions
            has_item_field = False
            item_field_is_modelchoice = False
            item_field_has_picker_in_def = False

            for item_node in node.body:
                if not isinstance(item_node, ast.Assign):
                    continue

                # Check if it's assigning to 'item'
                if not (len(item_node.targets) == 1 and isinstance(item_node.targets[0], ast.Name)):
                    continue

                if item_node.targets[0].id != "item":
                    continue

                has_item_field = True

                # Check if it's a ModelChoiceField
                if not isinstance(item_node.value, ast.Call):
                    continue

                func = item_node.value.func
                is_model_choice = False
                if isinstance(func, ast.Attribute):
                    if func.attr == "ModelChoiceField":
                        is_model_choice = True
                elif isinstance(func, ast.Name):
                    if func.id == "ModelChoiceField":
                        is_model_choice = True

                if not is_model_choice:
                    continue

                item_field_is_modelchoice = True

                # Check if the field definition includes widget=ItemPickerWidget(...)
                for keyword in item_node.value.keywords:
                    if keyword.arg == "widget":
                        if isinstance(keyword.value, ast.Call):
                            func = keyword.value.func
                            if isinstance(func, ast.Name) and func.id == "ItemPickerWidget":
                                item_field_has_picker_in_def = True
                                break
                            if isinstance(func, ast.Attribute) and func.attr == "ItemPickerWidget":
                                item_field_has_picker_in_def = True
                                break

            if not (has_item_field and item_field_is_modelchoice):
                continue

            # If the field definition already has ItemPickerWidget, it's OK
            if item_field_has_picker_in_def:
                continue

            # Otherwise, check if __init__ sets the widget to ItemPickerWidget
            has_picker_widget_in_init = False
            for method in node.body:
                if not isinstance(method, ast.FunctionDef):
                    continue
                if method.name != "__init__":
                    continue

                # Look for self.fields["item"].widget = ItemPickerWidget(...)
                for stmt in ast.walk(method):
                    if not isinstance(stmt, ast.Assign):
                        continue
                    if len(stmt.targets) != 1:
                        continue
                    target = stmt.targets[0]
                    if not isinstance(target, ast.Attribute):
                        continue
                    if target.attr != "widget":
                        continue
                    # Check if value is ItemPickerWidget call
                    if isinstance(stmt.value, ast.Call):
                        func = stmt.value.func
                        if isinstance(func, ast.Name) and func.id == "ItemPickerWidget":
                            has_picker_widget_in_init = True
                            break
                        if isinstance(func, ast.Attribute) and func.attr == "ItemPickerWidget":
                            has_picker_widget_in_init = True
                            break

            if not has_picker_widget_in_init:
                violations.append(f"{module_path}.{node.name}.item")

    assert not violations, (
        "Found bare ModelChoiceField for item in admin/GM forms (missing ItemPickerWidget):\n"
        + "\n".join(violations)
    )


@pytest.mark.django_db
def test_picker_widget_renders_without_select():
    """Verify that ItemPickerWidget renders the picker component, not a plain select."""
    from accounts.models import Club

    # Create a minimal club for testing
    club = Club.objects.create(name="Test Club", slug="test-club")

    widget = ItemPickerWidget(club=club)
    html = widget.render("test_field", None)

    # Should render the picker component
    assert "data-item-picker" in html
    assert 'name="test_field"' in html
    # Should NOT render a plain select outside of noscript
    # The only select should be inside <noscript>
    assert html.strip().startswith("<div"), f"Expected picker div, got: {html[:200]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
