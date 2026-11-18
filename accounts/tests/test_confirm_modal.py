"""Render tests for the shared confirm modal and its consume conversion."""

import pytest
from django.template.loader import render_to_string

from player_characters.forms_adjust import PlayerConsumeForm

pytestmark = [pytest.mark.django_db, pytest.mark.story("FOUNDATION")]


def _render_consume(item, club, available=1):
    form = PlayerConsumeForm(available=available)
    return render_to_string(
        "accounts/modals/_consume_confirm.html",
        {
            "item": item,
            "club": club,
            "available": available,
            "form": form,
            "confirm_url": "/c/club/characters/consume/1/1/",
        },
    )


def test_consume_confirm_renders_cancel_and_confirm(item, club):
    html = _render_consume(item, club)
    assert "Consume 1" in html and item.name in html
    assert 'data-bs-dismiss="modal">Cancel</button>' in html
    assert '<button class="btn btn-primary" type="submit">Consume</button>' in html
    assert 'hx-post="/c/club/characters/consume/1/1/"' in html
    assert 'name="quantity"' in html and 'name="note"' in html


def test_confirm_modal_blocks_honored(club):
    from django.template import Context, Template

    html = Template(
        '{% extends "components/_confirm_modal.html" %}'
        "{% block title %}Delete item?{% endblock %}"
        "{% block summary %}This cannot be undone.{% endblock %}"
        "{% block confirm_label %}Delete{% endblock %}"
    ).render(Context({"confirm_url": "/delete/"}))
    assert "Delete item?" in html
    assert "This cannot be undone." in html
    assert '<button class="btn btn-primary" type="submit">Delete</button>' in html
    assert 'data-bs-dismiss="modal">Cancel</button>' in html
