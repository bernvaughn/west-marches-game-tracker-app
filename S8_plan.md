# Implementation Plan: S8 Bulk Award for GMs

## Overview
Create "Award Loot to Party" page for GMs to award coins/items to multiple characters in one flow, similar to the existing D5 Downtime Points award.

## Files to Create/Modify

### 1. `player_characters/views/character_adjust.py` (modify)
Add new `bulk_award` view function:
- Use `@admin_or_gm_required` decorator
- Handle GET (render form) and POST (process form)
- Form handles:
  - Character checklist (select all/none)
  - Per-character coins input
  - Per-character item rows with autocomplete from catalogue
  - Shared note + date
- Use `ledger.services.record_many` for atomic ledger entry creation
- On success: toast + redirect to club ledger filtered to new entries

### 2. `player_characters/forms_adjust.py` (modify)
Add new form classes:
- `BulkAwardCharacterForm`: Character selection (ModelMultipleChoiceField with CheckboxSelectMultiple)
- `BulkAwardItemLineForm`: Item + quantity + optional override value
- `BulkAwardItemLineFormSet`: Formset for item lines
- `BulkAwardForm`: Main form combining characters, note, date

### 3. `player_characters/templates/player_characters/characters/bulk_award.html` (new)
Template for the bulk award page:
- Page header "Award Loot to Party"
- Character checklist table (like D5 points_award.html)
- Per-character coins input
- Per-character item rows (autocomplete item select, quantity, optional value override)
- Shared note + date fields
- Select All / Clear buttons
- Save button

### 4. `player_characters/urls_characters.py` (modify)
Add URL pattern: `path("<int:pk>/bulk-award/", character_adjust.bulk_award, name="bulk_award")`

### 5. `accounts/navigation.py` (modify via `downtime/apps.py` or `player_characters/apps.py`)
Register GM navigation entry:
- Group: "gm"
- Label: "Award Loot to Party"
- URL name: "characters:bulk_award" (but needs club_slug)
- Check: `is_gm_or_admin`
- Order: appropriate (e.g., 20)

Actually, the navigation needs a URL that doesn't require a specific character PK. Looking at the spec: "URL: `/characters/<slug>/bulk-award/`" - this uses club slug, not character PK. So we need a different URL pattern.

Wait, re-reading the spec: "URL: `/characters/<slug>/bulk-award/`" - the `<slug>` here is the club slug, not a character PK. This is a club-level page, not character-specific.

So the URL should be in `player_characters/urls.py` (not urls_characters.py) at the club level:
`path("bulk-award/", character_adjust.bulk_award, name="bulk_award")`

And the navigation entry would be:
`reg("gm", "Award Loot to Party", "characters:bulk_award", is_gm_or_admin, 20)`

But wait, the characters app uses `app_name = "characters"` in urls_characters.py. Let me check the main urls.py.

Actually, looking at the existing structure, the characters URLs are included under the club slug in the main URL config. Let me check.

### 6. `player_characters/urls.py` (modify)
Add the bulk-award URL at the club level (not per-character).

## Technical Details

### Form Structure
The form needs to handle:
1. Character selection (checkbox list)
2. For each selected character:
   - Coins amount (can be different per character)
   - Item rows (each with: item autocomplete, quantity, optional value override)
3. Shared note (single textarea)
4. Shared date (single date field)

This is complex because each character can have different items/coins. The simplest approach:
- Character checklist
- For each character, a "section" with coins + item rows
- But that's a lot of form fields

Alternative: Use a formset for characters, where each character form has coins + item formset.

Let me look at how the existing adjust form works - it uses a single form with a formset for items. For bulk award, we need per-character data.

The D5 points award just has a single points value for all selected characters. For bulk award, we need per-character coins and items.

Best approach:
- Character checkbox list (ModelMultipleChoiceField)
- When submitted, for each selected character, create a ledger entry spec
- The form can have:
  - Character checkboxes
  - A "global" coins field (applies to all) OR per-character coins
  - Item rows that can be "shared" (same items for all) with per-character quantity overrides
  - Shared note + date

Looking at the acceptance criteria: "per-character coins + item rows, shared note + date"

This suggests:
- Per-character coins input
- Per-character item rows (can add different items per character)
- Single shared note
- Single shared date

The UI could be:
1. Character checklist table (like D5)
2. Below each checked character, show coins input + item rows
3. Shared note + date at bottom

For the form handling, we can use a dynamic form that builds fields based on selected characters.

But for simplicity and HTMX compatibility, let's use a different approach:
- First step: Select characters (checkboxes)
- Second step: After selecting characters and clicking "Next", show per-character forms
- But this requires multi-step form

Simpler: Render all character sections at once, use JavaScript to show/hide per-character sections based on checkboxes.

Actually, looking at the D5 points award - it shows all characters in a table with checkboxes, and a single points field. For bulk award with per-character coins/items, we need a different UI.

Let me design the form:
- Table of characters with checkboxes
- For each character row, show coins input and "Add item" button
- When checkbox is checked, show the coins/item fields for that character
- Item rows: autocomplete item select, quantity, optional value override (per row)
- Shared note + date at bottom

For the form backend:
- Character checkboxes: `characters` (ModelMultipleChoiceField)
- For coins: use a JSON field or dynamic fields like `coins_<pk>`
- For items: dynamic formset per character

Actually, the simplest approach for the backend:
- Use a form with:
  - `characters` = ModelMultipleChoiceField (checkboxes)
  - `note` = CharField
  - `date` = DateField
- In the view, for each selected character, read:
  - `coins_<pk>` from POST
  - `items_<pk>-TOTAL_FORMS`, `items_<pk>-INITIAL_FORMS`, etc. (separate formset per character)

This is complex but doable.

Alternative: Use a single formset where each form represents a character's award:
- Character (ModelChoiceField, hidden after selection)
- Coins
- Item formset (nested)

But Django doesn't support nested formsets easily.

Let me look at how the existing code handles this kind of thing... 

Actually, looking at the ledger.services.record_many, it takes a list of specs, each with character, kind, lines, note, date. This is perfect for bulk award - we just need to build the list of specs from the form data.

For the form, I'll create:
1. `BulkAwardForm` - main form with characters (checkboxes), note, date
2. In the view, dynamically create per-character coins fields and item formsets based on selected characters

But for initial GET, we don't know which characters are selected. So:
- GET: Show all characters with checkboxes, no per-character fields yet
- POST: If characters selected, validate and process; if not, show error

Actually, better UX: Show all characters with their coins/item sections always visible but disabled/hidden until checked. Use JavaScript to enable them.

For the form submission, we can use a single form with:
- `characters`: ModelMultipleChoiceField (checkboxes)
- `note`: CharField
- `date`: DateField
- For each character in the club: optional `coins_<pk>` field and optional item formset

But this means the form class needs to know all characters, which it does via `club` in __init__.

Let me design the forms:

```python
class BulkAwardItemLineForm(forms.Form):
    item = forms.ModelChoiceField(queryset=None, required=False)
    quantity = forms.IntegerField(min_value=1, required=False)
    value_override = forms.IntegerField(required=False, min_value=0, label="Value (cp)", help_text="Override item value in cp")

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = items

    def clean(self):
        data = super().clean()
        item, qty = data.get("item"), data.get("quantity")
        if (item is None) != (qty is None):
            raise forms.ValidationError("Pick an item and a quantity, or leave the row blank.")
        return data


class BaseBulkAwardItemLineFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            item = getattr(form, "cleaned_data", {}).get("item")
            if item is None:
                continue
            if item.pk in seen:
                raise forms.ValidationError("Pick each item once.")
            seen.add(item.pk)
```

Then in the view, for each selected character, create a formset.

For the template, I'll use HTMX to dynamically load per-character sections when checkboxes are checked, or just render all sections and use CSS/JS to show/hide.

Given the complexity, I'll start with a simpler approach:
- Render all characters with their sections
- Use JavaScript to toggle visibility
- On POST, process only checked characters

Let me now write the plan and acceptance criteria.