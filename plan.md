# Implementation Plan: Starting Equipment App Models

## Overview
Create the `starting_equipment` Django app with all models specified in the design:
- StartingEquipmentTemplate
- StartingEquipmentClassEntry
- StartingEquipmentClassLine
- StartingEquipmentBackgroundEntry
- StartingEquipmentBackgroundLine
- StartingEquipmentLevelCoins
- MagicItemStartingOption
- StartingEquipmentRequest

## Steps

### 1. Create App Structure
- Create `starting_equipment/` directory
- Create `__init__.py`, `apps.py`, `models.py`, `admin.py`
- Add app to `INSTALLED_APPS` in `config/settings.py`

### 2. Implement Models (models.py)
Follow the project's conventions:
- Use `ClubScopedManager` for club-scoped models
- Set `club_path` on each model
- Add proper `related_name` attributes
- Add indexes for common queries (template+club, character+status, etc.)
- Add constraints (unique_together, check constraints)
- Use `on_delete=models.PROTECT` for Item FKs
- Use `models.TextChoices` for status fields

### 3. Register Models in Admin (admin.py)
- Register all models
- Use `TabularInline` for line models (ClassLine, BackgroundLine)
- Use `StackedInline` for entry models (ClassEntry, BackgroundEntry, LevelCoins, MagicItemOption, Request)
- Template admin shows inlines for all related entries

### 4. Run Migrations
- Generate and apply migrations

## File Changes

### New Files
- `starting_equipment/__init__.py`
- `starting_equipment/apps.py`
- `starting_equipment/models.py`
- `starting_equipment/admin.py`
- `starting_equipment/migrations/` (created by Django)

### Modified Files
- `config/settings.py` - Add `starting_equipment` to INSTALLED_APPS

## Acceptance Criteria Mapping
Each acceptance item maps to the plan stage where it can be verified:
- App exists with all models → plan (structure) / code (migrations applied)
- Proper related_names, indexes, constraints → code (model inspection)
- Admin registration with inlines → code (admin.py inspection)

## Proof Stages
- `plan`: Structure exists, files created
- `code`: Migrations applied, models work, admin registered
- `verify`: All tests pass
