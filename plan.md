# Implementation Plan: T3 - List pages for items extra models

## Overview
Enhance Django admin list pages for ContainerSlot, ContainerSlotOption, and ClubWeightSettings with proper date_hierarchy, ordering, and verify all list_display, list_filter, search_fields, autocomplete_fields/raw_id_fields work correctly.

## Files to Modify
1. `items/admin.py` - Add date_hierarchy and update ordering for three admin classes
2. `items/tests/test_admin.py` - Add comprehensive tests for list page features

## Changes to items/admin.py

### ContainerSlotAdmin
- Add: `date_hierarchy = "container__club__created"` (Item has no created field, use club's)
- Change: `ordering = ["container", "position"]` (was `["position"]`)

### ContainerSlotOptionAdmin
- Add: `date_hierarchy = "slot__container__club__created"` (ContainerSlot/Item have no created field)
- Change: `ordering = ["slot", "id"]` (was default Meta ordering)

### ClubWeightSettingsAdmin
- Add: `date_hierarchy = "club__created"`
- Add: `ordering = ["club__name"]`

## New Tests to Add (items/tests/test_admin.py)

For each model, add tests verifying:
1. **list_display fields appear in changelist** - GET changelist, assert field values in response content
2. **list_filter shows club via related paths** - Check filter sidebar presence in changelist
3. **search works on specified fields** - POST search query, assert filtered results
4. **autocomplete_fields work for FKs** - Verify autocomplete URL patterns resolve
5. **raw_id_fields for ClubWeightSettings.club** - Verify raw_id widget renders

### Specific test functions:
- `test_containerslot_admin_list_display_content`
- `test_containerslot_admin_list_filter_club`
- `test_containerslot_admin_search`
- `test_containerslot_admin_autocomplete_container`
- `test_containerslot_admin_date_hierarchy`
- `test_containerslot_admin_ordering`

- `test_containerslotoption_admin_list_display_content`
- `test_containerslotoption_admin_list_filter_club`
- `test_containerslotoption_admin_search`
- `test_containerslotoption_admin_autocomplete_slot`
- `test_containerslotoption_admin_autocomplete_item`
- `test_containerslotoption_admin_date_hierarchy`
- `test_containerslotoption_admin_ordering`

- `test_clubweightsettings_admin_list_display_content`
- `test_clubweightsettings_admin_search`
- `test_clubweightsettings_admin_raw_id_club`
- `test_clubweightsettings_admin_date_hierarchy`
- `test_clubweightsettings_admin_ordering`

## Acceptance Criteria Mapping

| Spec Requirement | Proof Stage |
|------------------|-------------|
| ContainerSlotAdmin: date_hierarchy, ordering | code (admin.py changes) |
| ContainerSlotOptionAdmin: date_hierarchy, ordering | code (admin.py changes) |
| ClubWeightSettingsAdmin: date_hierarchy, ordering | code (admin.py changes) |
| list_display fields appear in changelist | verify (tests) |
| list_filter shows club via related paths | verify (tests) |
| search works on specified fields | verify (tests) |
| autocomplete_fields work for FKs | verify (tests) |
| raw_id_fields for ClubWeightSettings.club | verify (tests) |

## Dependencies
- C4 (Register missing items models) - COMPLETED
- No other dependencies