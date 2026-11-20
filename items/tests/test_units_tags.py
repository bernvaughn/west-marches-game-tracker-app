"""Template filter tests for the ``units`` tag library (U125, U127)."""

from types import SimpleNamespace

import pytest
from django.template import Context, Template

from items.tests.factories import make_arrows, make_parchment


def _item(value_cp, value_units, name="Thing", unit_name="unit", stacked=True):
    return SimpleNamespace(
        name=name,
        unit_name=unit_name,
        value_cp=value_cp,
        value_units=value_units,
        is_stacked=stacked,
    )


def _render(text, **ctx):
    return Template("{% load units %}" + text).render(Context(ctx))


@pytest.mark.story("U127")
def test_with_units_stacked():
    rope = _item(100, 50, "Rope", "ft")
    assert _render("{{ item|with_units:40 }}", item=rope).strip() == "40 ft Rope"


@pytest.mark.story("U127")
def test_with_units_normal():
    rope = _item(100, 1, "Rope", "ft", stacked=False)
    assert _render("{{ item|with_units:3 }}", item=rope).strip() == "3 × Rope"


@pytest.mark.story("U125")
def test_bundle_label_stacked():
    arrows = _item(100, 20, "Arrows", "arrow")
    assert _render("{{ item|bundle_label:100 }}", item=arrows).strip() == "bundle of 100 arrow"


@pytest.mark.story("U125")
def test_bundle_label_normal_item_returns_name():
    rope = _item(100, 1, "Rope", "ft", stacked=False)
    assert _render("{{ item|bundle_label:1 }}", item=rope).strip() == "Rope"


@pytest.mark.story("U125")
def test_filters_work_with_factory_items(db, club):
    # DB-backed factory items render the same as pure stand-ins.
    parchment = make_parchment(club)
    assert _render("{{ item|with_units:1 }}", item=parchment).strip() == "1 sheet Parchment"
    arrows = make_arrows(club)
    assert _render("{{ item|bundle_label:5 }}", item=arrows).strip() == "bundle of 5 arrow"
