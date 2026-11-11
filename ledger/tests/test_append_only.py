import pytest

from ledger.models import AppendOnlyError, LedgerEntry, LedgerLine

pytestmark = pytest.mark.story("FOUNDATION")


@pytest.fixture
def entry(club, character, item):
    e = LedgerEntry.objects.create(club=club, character=character, kind="award")
    LedgerLine.objects.create(entry=e, item=item, quantity=1)
    return e


def test_save_existing_entry_refused(entry):
    entry.note = "changed"
    with pytest.raises(AppendOnlyError):
        entry.save()


def test_save_existing_line_refused(entry):
    line = entry.lines.get()
    line.quantity = 5
    with pytest.raises(AppendOnlyError):
        line.save()


def test_delete_instance_refused(entry):
    with pytest.raises(AppendOnlyError):
        entry.delete()
    with pytest.raises(AppendOnlyError):
        entry.lines.get().delete()


def test_queryset_update_delete_refused(entry):
    with pytest.raises(AppendOnlyError):
        LedgerEntry.objects.update(note="x")
    with pytest.raises(AppendOnlyError):
        LedgerEntry.objects.all().delete()
    with pytest.raises(AppendOnlyError):
        entry.lines.all().delete()
    with pytest.raises(AppendOnlyError):
        LedgerLine.objects.update(quantity=2)


def test_new_rows_still_insert(entry):
    assert LedgerEntry.objects.for_club(entry.club).count() == 1
