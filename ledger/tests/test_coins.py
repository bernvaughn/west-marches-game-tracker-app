import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.template import Context, Template

from ledger.coins import CoinsField, CoinsWidget, format_coins, split_copper

pytestmark = pytest.mark.story("FOUNDATION")


@pytest.mark.parametrize(
    "cp, text",
    [
        (0, "0 cp"),
        (5, "5 cp"),
        (1234, "1 pp 2 gp 3 sp 4 cp"),
        (1000, "1 pp"),
        (230, "2 gp 3 sp"),
        (-1234, "-1 pp 2 gp 3 sp 4 cp"),
    ],
)
def test_format_coins(cp, text):
    assert format_coins(cp) == text


def test_format_none():
    assert format_coins(None) == ""


def test_split_copper():
    assert split_copper(1234) == (1, 2, 3, 4)
    assert split_copper(0) == (0, 0, 0, 0)
    assert split_copper(-1234) == (-1, -2, -3, -4)


def test_field_clean():
    assert CoinsField().clean([1, 2, 3, 4]) == 1234
    assert CoinsField().clean(["", 2, "", ""]) == 200


def test_field_empty_not_required():
    assert CoinsField(required=False).clean(["", "", "", ""]) == 0


def test_field_empty_required():
    with pytest.raises(ValidationError):
        CoinsField().clean(["", "", "", ""])


def test_field_negative_and_non_integer():
    with pytest.raises(ValidationError):
        CoinsField().clean([-1, 0, 0, 0])
    with pytest.raises(ValidationError):
        CoinsField().clean(["x", 0, 0, 0])


def test_form_round_trip():
    class F(forms.Form):
        price = CoinsField()

    form = F({"price_pp": "1", "price_gp": "2", "price_sp": "", "price_cp": "4"})
    assert form.is_valid()
    assert form.cleaned_data["price"] == 1204
    assert not F({"price_pp": "-1"}).is_valid()


def test_widget_decompress():
    w = CoinsWidget()
    assert w.decompress(1234) == [1, 2, 3, 4]
    assert w.decompress(None) == [None] * 4


@pytest.mark.parametrize("n", [0, 1234, -5])
def test_filter(n):
    out = Template("{% load coins %}{{ v|coins }}").render(Context({"v": n}))
    assert out == format_coins(n)
