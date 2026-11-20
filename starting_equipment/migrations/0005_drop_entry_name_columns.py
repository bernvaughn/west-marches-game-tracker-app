"""Drop the old name columns from starting equipment entries.

Entries now link to character option records by FK only. This migration:

1. Fails loudly (RuntimeError) if any entry has a null FK, or if two
   background entries share a template and option record (which would break
   the new unique constraint). The error lists the offending ids and old
   names so the operator can fix them before re-running.
2. Removes the old text-based constraint and indexes.
3. Makes both FKs non-null.
4. Drops the text columns, updates model options, and adds the FK-based
   indexes and the background unique constraint.

Reverse is a no-op: links and created records are kept.
"""

import django.db.models.deletion
from django.db import migrations, models


def _fail_loudly(apps, schema_editor):
    """Raise if any entry lacks its FK or a background duplicate would break
    the new unique constraint. Lists ids and old names."""
    ClassEntry = apps.get_model("starting_equipment", "StartingEquipmentClassEntry")
    BackgroundEntry = apps.get_model("starting_equipment", "StartingEquipmentBackgroundEntry")

    problems = []

    for entry in ClassEntry.objects.filter(class_option_id__isnull=True):
        problems.append(
            f"  class entry id={entry.pk} template_id={entry.template_id} char_class={entry.char_class!r}"
        )

    for entry in BackgroundEntry.objects.filter(background_option_id__isnull=True):
        problems.append(
            f"  background entry id={entry.pk} template_id={entry.template_id} background={entry.background!r}"
        )

    # Two background entries on one template + record break the new constraint.
    from django.db.models import Count

    duplicates = (
        BackgroundEntry.objects.filter(background_option_id__isnull=False)
        .values("template_id", "background_option_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    for dup in duplicates:
        entries = BackgroundEntry.objects.filter(
            template_id=dup["template_id"], background_option_id=dup["background_option_id"]
        )
        ids = ", ".join(str(e.pk) for e in entries)
        problems.append(
            f"  duplicate background entries ids=[{ids}] "
            f"template_id={dup['template_id']} background_option_id={dup['background_option_id']}"
        )

    if problems:
        raise RuntimeError(
            "Starting equipment entries are not ready for the FK-only cleanup. "
            "Fix these before re-running migration 0005:\n" + "\n".join(problems)
        )


def _noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("character_options", "0002_seed_default_options"),
        ("starting_equipment", "0004_link_entries_to_character_options"),
    ]

    operations = [
        # 1. Fail loudly on null FKs or background duplicates.
        migrations.RunPython(_fail_loudly, _noop),
        # 2. Remove the old text-based constraint and indexes.
        migrations.RemoveConstraint(
            model_name="startingequipmentbackgroundentry",
            name="unique_background_per_template",
        ),
        migrations.RemoveIndex(
            model_name="startingequipmentclassentry",
            name="starting_eq_templat_0a8bd7_idx",
        ),
        migrations.RemoveIndex(
            model_name="startingequipmentbackgroundentry",
            name="starting_eq_templat_fc399d_idx",
        ),
        # 3. Make both FKs required.
        migrations.AlterField(
            model_name="startingequipmentclassentry",
            name="class_option",
            field=models.ForeignKey(
                blank=False,
                null=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="starting_entries",
                to="character_options.characterclass",
            ),
        ),
        migrations.AlterField(
            model_name="startingequipmentbackgroundentry",
            name="background_option",
            field=models.ForeignKey(
                blank=False,
                null=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="starting_entries",
                to="character_options.background",
            ),
        ),
        # 4. Drop the text columns.
        migrations.RemoveField(
            model_name="startingequipmentclassentry",
            name="char_class",
        ),
        migrations.RemoveField(
            model_name="startingequipmentbackgroundentry",
            name="background",
        ),
        # 5. Model options + FK-based indexes + background unique constraint.
        migrations.AlterModelOptions(
            name="startingequipmentclassentry",
            options={"ordering": ["class_option__name", "min_level"]},
        ),
        migrations.AlterModelOptions(
            name="startingequipmentbackgroundentry",
            options={"ordering": ["background_option__name"]},
        ),
        migrations.AddIndex(
            model_name="startingequipmentclassentry",
            index=models.Index(
                fields=["template", "class_option"],
                name="starting_equipment_class_entry_template_class_option_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="startingequipmentbackgroundentry",
            index=models.Index(
                fields=["template", "background_option"],
                name="starting_equipment_background_entry_template_background_option_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="startingequipmentbackgroundentry",
            constraint=models.UniqueConstraint(
                fields=["template", "background_option"],
                name="unique_background_per_template",
            ),
        ),
    ]
