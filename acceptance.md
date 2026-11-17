## plan
- [x] Implementation plan written and set via ch task edit
- [x] Acceptance criteria defined and set via ch task acceptance set

## code
- [ ] starting_equipment app directory created with __init__.py, apps.py, models.py, admin.py
- [ ] App added to INSTALLED_APPS in config/settings.py
- [ ] StartingEquipmentTemplate model exists with club, name, is_active, description, created, updated fields
- [ ] StartingEquipmentTemplate has unique_together constraint on (club, name)
- [ ] StartingEquipmentClassEntry model exists with template, char_class, min_level, max_level, coins_cp fields
- [ ] StartingEquipmentClassEntry has proper related_name "class_entries" to template
- [ ] StartingEquipmentClassLine model exists with class_entry, item, quantity, is_choice, choice_group fields
- [ ] StartingEquipmentClassLine has proper related_name "lines" to class_entry
- [ ] StartingEquipmentBackgroundEntry model exists with template, background, coins_cp fields
- [ ] StartingEquipmentBackgroundEntry has proper related_name "background_entries" to template
- [ ] StartingEquipmentBackgroundLine model exists with background_entry, item, quantity, is_choice, choice_group fields
- [ ] StartingEquipmentBackgroundLine has proper related_name "lines" to background_entry
- [ ] StartingEquipmentLevelCoins model exists with template, level, coins_cp fields
- [ ] StartingEquipmentLevelCoins has proper related_name "level_coins" to template
- [ ] StartingEquipmentLevelCoins has level validators (MinValueValidator(2), MaxValueValidator(20))
- [ ] MagicItemStartingOption model exists with template, item, max_per_character, notes fields
- [ ] MagicItemStartingOption has proper related_name "magic_options" to template
- [ ] StartingEquipmentRequest model exists with all specified fields (club, character, item, quantity, note, status, decided_by, decided_at, decision_note, created)
- [ ] StartingEquipmentRequest has Status TextChoices (PENDING, APPROVED, DECLINED)
- [ ] StartingEquipmentRequest has proper related_names: "starting_requests" to club and character
- [ ] All models use ClubScopedManager and have club_path set
- [ ] All Item foreign keys use on_delete=models.PROTECT
- [ ] Models have indexes for common queries (template+club, character+status, etc.)
- [ ] Admin registration complete with TabularInline for line models
- [ ] Admin registration complete with StackedInline for entry models
- [ ] Template admin shows inlines for all related entries

## verify
- [ ] Migrations generated and applied successfully
- [ ] All models import without errors
- [ ] Admin pages load without errors
- [ ] Basic model operations work (create, read, update where allowed)