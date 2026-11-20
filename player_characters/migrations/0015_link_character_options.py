# Generated migration to link existing characters to option records.

from django.db import migrations
from django.db.models.functions import Lower


def link_characters(apps, schema_editor):
    """Link existing characters to option records by case-insensitive exact name match.

    For each club, build a lowercase-name map of each option kind (including archived).
    For each character with FK null and non-blank text, link on a trimmed iexact match.
    Never rewrite text. Print counts per field: linked, left custom, blank.
    """
    Character = apps.get_model("player_characters", "Character")
    Species = apps.get_model("character_options", "Species")
    CharacterClass = apps.get_model("character_options", "CharacterClass")
    Background = apps.get_model("character_options", "Background")

    fields = [
        ("char_class", "class_option", CharacterClass),
        ("species", "species_option", Species),
        ("background", "background_option", Background),
    ]

    # Process per club
    for club in Character.objects.values_list("club_id", flat=True).distinct():
        club_characters = Character.objects.filter(club_id=club)

        # Build lowercase name maps for each option kind, including archived.
        option_maps = {}
        for _text_field, _fk_field, model in fields:
            qs = model.objects.filter(club_id=club)
            option_maps[model] = {obj.name.lower(): obj for obj in qs}

        for text_field, fk_field, model in fields:
            option_map = option_maps[model]
            linked = 0
            left_custom = 0
            blank = 0

            # Characters with FK null and non-blank text
            chars_to_check = club_characters.filter(**{f"{fk_field}__isnull": True}).exclude(
                **{f"{text_field}__exact": ""}
            )

            for char in chars_to_check:
                text_val = getattr(char, text_field, "").strip()
                if not text_val:
                    blank += 1
                    continue

                match = option_map.get(text_val.lower())
                if match:
                    setattr(char, fk_field, match)
                    char.save(update_fields=[fk_field])
                    linked += 1
                else:
                    left_custom += 1

            # Also count characters with blank text (FK is already null)
            blank += club_characters.filter(**{f"{fk_field}__isnull": True, f"{text_field}__exact": ""}).count()

            print(
                f"Club {club} - {text_field}: linked={linked}, left_custom={left_custom}, blank={blank}"
            )


def reverse_noop(apps, schema_editor):
    """Reverse is a no-op: we never rewrite text, and FKs can stay linked."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("character_options", "0002_seed_default_options"),
        ("player_characters", "0014_character_background_option_character_class_option_and_more"),
    ]

    operations = [
        migrations.RunPython(link_characters, reverse_noop),
    ]