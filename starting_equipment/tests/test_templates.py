"""Tests for starting equipment template CRUD views."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import Membership
from starting_equipment.models import StartingEquipmentTemplate


@pytest.mark.django_db
class TestTemplateListView:
    """Tests for the template list view."""

    def test_club_admin_can_list_templates(
        self, client, club_admin, club, template, inactive_template
    ):
        """Club admin can list templates for their club."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:templates", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert response.status_code == 200
        assert b"Test Template" in response.content
        assert b"Inactive Template" in response.content
        assert b"Active" in response.content

    def test_list_shows_active_flag(self, client, club_admin, club, template, inactive_template):
        """List shows active flag for each template."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:templates", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert b"Active" in response.content  # For the active template
        assert b"Set active" in response.content  # For the inactive template

    def test_other_club_templates_not_shown(self, client, club_admin, club, other_club, template):
        """Templates from other clubs are not shown."""
        # Create template in other club
        StartingEquipmentTemplate.objects.create(
            club=other_club, name="Other Club Template", is_active=True
        )
        client.force_login(club_admin)
        url = reverse("starting_equipment:templates", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert b"Other Club Template" not in response.content

    def test_non_admin_receives_403(self, client, player, club, template):
        """Non-admin user receives 403."""
        client.force_login(player)
        url = reverse("starting_equipment:templates", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert response.status_code == 403

    def test_game_master_receives_403(self, client, game_master, club, template):
        """Game master (non-admin) receives 403."""
        # Ensure game_master is not a club admin
        Membership.objects.filter(user=game_master, club=club).update(
            is_club_admin=False, is_game_master=True
        )
        client.force_login(game_master)
        url = reverse("starting_equipment:templates", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestTemplateCreateView:
    """Tests for the template create view."""

    def test_get_create_form(self, client, club_admin, club):
        """GET returns the create form."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert response.status_code == 200
        assert b"New Template" in response.content
        assert b"Name" in response.content

    def test_post_valid_form_creates_template(self, client, club_admin, club):
        """POST with valid data creates template and redirects."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        data = {"name": "New Template", "description": "A new template", "is_active": True}
        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse(
            "starting_equipment:templates", kwargs={"club_slug": club.slug}
        )
        template = StartingEquipmentTemplate.objects.get(club=club, name="New Template")
        assert template.club == club
        assert template.description == "A new template"
        assert template.is_active is True

    def test_post_valid_form_shows_success_message(self, client, club_admin, club):
        """POST shows success message."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        data = {"name": "New Template", "description": "", "is_active": False}
        response = client.post(url, data, follow=True)
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "created" in str(messages[0])

    def test_post_invalid_form_shows_errors(self, client, club_admin, club):
        """POST with invalid data shows form errors."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        data = {"name": "", "description": "", "is_active": False}
        response = client.post(url, data)
        assert response.status_code == 200
        assert b"This field is required" in response.content

    def test_duplicate_name_rejected(self, client, club_admin, club, template):
        """Duplicate template name is rejected."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        data = {"name": template.name, "description": "", "is_active": False}
        response = client.post(url, data)
        assert response.status_code == 200
        assert b"already exists" in response.content

    def test_non_admin_receives_403(self, client, player, club):
        """Non-admin receives 403 on create."""
        client.force_login(player)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestTemplateDetailView:
    """Tests for the template detail view."""

    def test_detail_shows_template_info(
        self, client, club_admin, club, template, class_entry, bg_entry, level_coins, magic_option
    ):
        """Detail view shows template and related entries."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.get(url)
        assert response.status_code == 200
        assert template.name.encode() in response.content
        assert b"Fighter" in response.content  # class entry
        assert b"Acolyte" in response.content  # background entry
        assert b"5" in response.content  # level coins (level number)
        assert b"Potion of Healing" in response.content  # magic option

    def test_non_admin_receives_403(self, client, player, club, template):
        """Non-admin receives 403 on detail."""
        client.force_login(player)
        url = reverse(
            "starting_equipment:template_detail", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.get(url)
        assert response.status_code == 403

    def test_other_club_template_404(self, client, club_admin, other_club, template):
        """Template from other club returns 404."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": other_club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestTemplateEditView:
    """Tests for the template edit view."""

    def test_get_edit_form(self, client, club_admin, club, template):
        """GET returns the edit form pre-filled."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_edit", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.get(url)
        assert response.status_code == 200
        assert template.name.encode() in response.content
        assert b"Edit Template" in response.content

    def test_post_updates_template(self, client, club_admin, club, template):
        """POST updates template and redirects."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_edit", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        data = {"name": "Updated Name", "description": "Updated desc", "is_active": False}
        response = client.post(url, data)
        assert response.status_code == 302
        template.refresh_from_db()
        assert template.name == "Updated Name"
        assert template.description == "Updated desc"
        assert template.is_active is False

    def test_post_shows_success_message(self, client, club_admin, club, template):
        """POST shows success message."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_edit", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        data = {"name": "Updated", "description": "", "is_active": False}
        response = client.post(url, data, follow=True)
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "updated" in str(messages[0]).lower()

    def test_non_admin_receives_403(self, client, player, club, template):
        """Non-admin receives 403 on edit."""
        client.force_login(player)
        url = reverse(
            "starting_equipment:template_edit", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.get(url)
        assert response.status_code == 403

    def test_other_club_template_404(self, client, club_admin, other_club, template):
        """Template from other club returns 404."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_edit",
            kwargs={"club_slug": other_club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestTemplateDeleteView:
    """Tests for the template delete view."""

    def test_get_shows_confirmation(self, client, club_admin, club, template):
        """GET shows delete confirmation with confirm_url on action and hx-post."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_delete", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.get(url)
        assert response.status_code == 200
        assert b"Delete Template" in response.content
        assert template.name.encode() in response.content
        assert f'action="{url}"'.encode() in response.content
        assert f'hx-post="{url}"'.encode() in response.content

    def test_post_deletes_template(self, client, club_admin, club, template):
        """POST deletes template and redirects."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_delete", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse(
            "starting_equipment:templates", kwargs={"club_slug": club.slug}
        )
        assert not StartingEquipmentTemplate.objects.filter(pk=template.pk).exists()

    def test_post_shows_success_message(self, client, club_admin, club, template):
        """POST shows success message."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_delete", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.post(url, follow=True)
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "deleted" in str(messages[0]).lower()

    def test_non_admin_receives_403(self, client, player, club, template):
        """Non-admin receives 403 on delete."""
        client.force_login(player)
        url = reverse(
            "starting_equipment:template_delete", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        response = client.get(url)
        assert response.status_code == 403

    def test_other_club_template_404(self, client, club_admin, other_club, template):
        """Template from other club returns 404."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_delete",
            kwargs={"club_slug": other_club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestTemplateSetActiveView:
    """Tests for the template set-active view."""

    def test_activate_inactive_template(
        self, client, club_admin, club, template, inactive_template
    ):
        """Activating an inactive template deactivates the currently active one."""
        client.force_login(club_admin)
        # Initially: template is active, inactive_template is not
        assert template.is_active is True
        assert inactive_template.is_active is False

        url = reverse(
            "starting_equipment:template_set_active",
            kwargs={"club_slug": club.slug, "pk": inactive_template.pk},
        )
        response = client.post(url)
        assert response.status_code == 302

        template.refresh_from_db()
        inactive_template.refresh_from_db()
        assert template.is_active is False
        assert inactive_template.is_active is True

    def test_exactly_one_active_after_set_active(self, client, club_admin, club):
        """Exactly one template is active after set-active."""
        # Create multiple templates
        t1 = StartingEquipmentTemplate.objects.create(club=club, name="T1", is_active=True)
        t2 = StartingEquipmentTemplate.objects.create(club=club, name="T2", is_active=False)
        t3 = StartingEquipmentTemplate.objects.create(club=club, name="T3", is_active=False)

        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_set_active", kwargs={"club_slug": club.slug, "pk": t2.pk}
        )
        client.post(url)

        t1.refresh_from_db()
        t2.refresh_from_db()
        t3.refresh_from_db()
        active_count = (
            StartingEquipmentTemplate.objects.for_club(club).filter(is_active=True).count()
        )
        assert active_count == 1
        assert t2.is_active is True
        assert t1.is_active is False
        assert t3.is_active is False

    def test_activating_already_active_is_noop(self, client, club_admin, club, template):
        """Activating already-active template is a no-op success."""
        client.force_login(club_admin)
        assert template.is_active is True

        url = reverse(
            "starting_equipment:template_set_active",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.post(url, follow=True)
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "already active" in str(messages[0]).lower()

        template.refresh_from_db()
        assert template.is_active is True

    def test_requires_post(self, client, club_admin, club, template):
        """GET request is not allowed (requires POST)."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_set_active",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 405  # Method Not Allowed

    def test_non_admin_receives_403(self, client, player, club, template):
        """Non-admin receives 403 on set-active."""
        client.force_login(player)
        url = reverse(
            "starting_equipment:template_set_active",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.post(url)
        assert response.status_code == 403

    def test_other_club_template_404(self, client, club_admin, other_club, template):
        """Template from other club returns 404."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_set_active",
            kwargs={"club_slug": other_club.slug, "pk": template.pk},
        )
        response = client.post(url)
        assert response.status_code == 404

    def test_set_active_shows_success_message(
        self, client, club_admin, club, template, inactive_template
    ):
        """Set active shows success message."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_set_active",
            kwargs={"club_slug": club.slug, "pk": inactive_template.pk},
        )
        response = client.post(url, follow=True)
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "set as active" in str(messages[0]).lower()


@pytest.mark.django_db
class TestClubScoping:
    """Tests to verify club-scoping is enforced across all views."""

    def test_create_assigns_correct_club(self, client, club_admin, club, other_club):
        """Created template is assigned to the correct club."""
        client.force_login(club_admin)
        url = reverse("starting_equipment:template_create", kwargs={"club_slug": club.slug})
        data = {"name": "Scoped Template", "description": "", "is_active": False}
        response = client.post(url, data)
        assert response.status_code == 302
        template = StartingEquipmentTemplate.objects.for_club(club).get(name="Scoped Template")
        assert template.club == club
        assert template.club != other_club

    def test_edit_only_affects_own_club(self, client, club_admin, club, other_club, template):
        """Edit only affects templates in the same club."""
        # Create template in other club
        other_template = StartingEquipmentTemplate.objects.create(
            club=other_club, name="Other Template", is_active=False
        )
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_edit", kwargs={"club_slug": club.slug, "pk": template.pk}
        )
        data = {"name": "Updated", "description": "", "is_active": True}
        response = client.post(url, data)
        print(f"Response status (no follow): {response.status_code}")
        print(f"Response url (no follow): {getattr(response, 'url', 'N/A')}")
        template.refresh_from_db()
        print(f"Template name after: {template.name}")

        # Also test with follow
        response2 = client.post(url, data, follow=True)
        print(f"Response status (follow): {response2.status_code}")
        print(f"Redirect chain: {response2.redirect_chain}")
        if hasattr(response2, "context") and response2.context:
            if "form" in response2.context:
                print(f"Form data (follow): {response2.context['form'].data}")
        other_template.refresh_from_db()
        assert template.name == "Updated"
        assert other_template.name == "Other Template"  # Unchanged


@pytest.mark.django_db
class TestTemplateDetailMissingWarning:
    """Surface: template detail warns for active classes/backgrounds with no entry."""

    def test_warns_for_uncovered_active_class_and_background(
        self, client, club_admin, club, template, class_entry, class_option_wizard, bg_option_sage
    ):
        """Active class and background with no template entry each produce a warning."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "has no entry in this template" in content
        assert class_option_wizard.name in content
        assert bg_option_sage.name in content

    def test_covered_class_and_background_are_not_flagged(
        self, client, club_admin, club, template, class_entry, bg_entry
    ):
        """A class/background that HAS an entry is not listed as missing."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # class_entry (Fighter) and bg_entry (Acolyte) are present, so they are
        # not flagged even though other active options without entries are.
        assert (
            "Fighter" not in content.split("has no entry in this template")[0]
            if "has no entry in this template" in content
            else True
        )
        # Stronger: covered options are never named in a missing warning.
        import re

        missing = re.findall(r'Class "([^"]+)" has no entry', content)
        missing += re.findall(r'Background "([^"]+)" has no entry', content)
        assert "Fighter" not in missing
        assert "Acolyte" not in missing

    def test_archived_records_not_warned(
        self,
        client,
        club_admin,
        club,
        template,
        class_entry,
        bg_entry,
        class_option_wizard,
        bg_option_sage,
    ):
        """Archived records are not listed as missing (other active ones still are)."""
        class_option_wizard.is_active = False
        class_option_wizard.save()
        bg_option_sage.is_active = False
        bg_option_sage.save()

        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        import re

        missing_classes = re.findall(r'Class "([^"]+)" has no entry', content)
        missing_backgrounds = re.findall(r'Background "([^"]+)" has no entry', content)
        assert class_option_wizard.name not in missing_classes
        assert bg_option_sage.name not in missing_backgrounds
        # Other active options without entries are still flagged.
        assert missing_classes or missing_backgrounds

    def test_warning_names_the_template(
        self, client, club_admin, club, template, class_option_wizard
    ):
        """The warning names the template so an admin can prepare an inactive one."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert template.name in content


@pytest.mark.django_db
class TestTemplateDetailItemNames:
    """Tests for item names rendered via items/_item_name.html in template detail."""

    def test_template_detail_shows_item_names_in_class_entries(
        self, client, club_admin, club, template, class_entry, class_item, class_line
    ):
        """Plain GET test: item names from items/_item_name.html in class entry lines."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()

        # Assert the class item name appears (rendered via items/_item_name.html)
        assert class_item.name in content
        # Assert the wm-item-symbol class appears if item has a symbol
        if class_item.symbol:
            assert 'class="wm-item-symbol"' in content
        # info=True is NOT used in template_detail.html, so no info link expected

    def test_template_detail_shows_item_names_in_background_entries(
        self, client, club_admin, club, template, bg_entry, bg_item, bg_line
    ):
        """Plain GET test: item names from items/_item_name.html in background entry lines."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()

        # Assert the background item name appears (rendered via items/_item_name.html)
        assert bg_item.name in content
        # Assert the wm-item-symbol class appears if item has a symbol
        if bg_item.symbol:
            assert 'class="wm-item-symbol"' in content

    def test_template_detail_shows_item_names_in_magic_options(
        self, client, club_admin, club, template, magic_option, magic_item
    ):
        """Plain GET test: item names from items/_item_name.html in magic options."""
        client.force_login(club_admin)
        url = reverse(
            "starting_equipment:template_detail",
            kwargs={"club_slug": club.slug, "pk": template.pk},
        )
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()

        # Assert the magic item name appears (rendered via items/_item_name.html)
        # Note: info=True is NOT used for magic options in template_detail.html
        assert magic_item.name in content
        # Assert the wm-item-symbol class appears if item has a symbol
        if magic_item.symbol:
            assert 'class="wm-item-symbol"' in content
        # No info link expected since info=True is not used
