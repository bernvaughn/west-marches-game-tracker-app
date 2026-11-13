import pytest
from django.core.management import call_command

from downtime.models import DowntimeAction, DowntimeEntry, DowntimeEntryItem

pytestmark = [pytest.mark.django_db, pytest.mark.story("D2")]


def test_seed_demo_twice_makes_one_bakery():
    call_command("seed_demo", verbosity=0)
    call_command("seed_demo", verbosity=0)
    action = DowntimeAction.objects.get(name="Work at a bakery")
    assert action.entries.count() == 10
    assert DowntimeEntry.objects.count() == 10
    pins = DowntimeEntryItem.objects.filter(item__name="Golden rolling pin")
    assert pins.count() == 1 and pins.get().item.rarity == "rare"
