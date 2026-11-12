import re
from pathlib import Path

import pytest
from django import forms
from django.template import Context, Template

from ledger.coins import CoinsField, display_parts, format_coins

STATIC = Path(__file__).resolve().parents[2] / "static/css"
CSS = (STATIC / "coins.css").read_text()
TOKENS = (STATIC / "tokens.css").read_text()  # coin colours live in tokens (U35)


def render(src, v):
    return Template("{% load coins %}" + src).render(Context({"v": v}))


def lum(h):
    c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.story("U32")
@pytest.mark.parametrize(
    "cp, parts",
    [
        (0, (0, 0, 0, 0)),
        (999_999, (0, 9999, 9, 9)),
        (1_000_000, (1000, 0, 0, 0)),
        (1_234_560, (1234, 5, 6, 0)),
        (-999_999, (0, -9999, -9, -9)),
        (-1_234_560, (-1234, -5, -6, 0)),
    ],
)
def test_display_parts(cp, parts):
    assert display_parts(cp) == parts


@pytest.mark.story("U32")
def test_format_gold_first():
    assert format_coins(1_234_500) == "1,234 pp 5 gp"
    assert format_coins(999_950) == "9,999 gp 5 sp"


@pytest.mark.story("U31")
def test_coins_filter_spans():
    out = render("{{ v|coins }}", 1_234_560)
    assert re.findall(r'class="(coin coin-\w+)"', out) == [
        "coin coin-pp",
        "coin coin-gp",
        "coin coin-sp",
    ]
    assert "1,234 pp" in out
    assert render("{{ v|coins }}", 0).count("coin-cp") == 1
    assert render("{{ v|coins }}", -150).startswith("-<span")
    assert render("{{ v|coins }}", None) == ""


@pytest.mark.story("U31")
def test_coins_text_plain():
    out = render("{{ v|coins_text }}", 1_234_560)
    assert "<span" not in out and out == "1,234 pp 5 gp 6 sp"


@pytest.mark.story("U31")
def test_widget_labels():
    class F(forms.Form):
        price = CoinsField()

    html = str(F()["price"])
    for i, u in enumerate(("pp", "gp", "sp", "cp")):
        assert f'<label class="coin coin-{u}" for="id_price_{i}">{u}</label>' in html
        assert f'id="id_price_{i}"' in html
        assert "form-control-sm" in html


@pytest.mark.story("U31")
def test_css_contrast_and_print():
    for u in ("cp", "sp", "gp"):
        assert f".coin-{u} {{ color: var(--wm-coin-{u}); }}" in CSS
        colour = re.search(rf"--wm-coin-{u}: (#\w+)", TOKENS).group(1)
        assert ratio(colour, "#ffffff") >= 4.5
    assert "color: var(--wm-coin-pp); background: var(--wm-coin-pp-bg)" in CSS
    fg = re.search(r"--wm-coin-pp: (#\w+)", TOKENS).group(1)
    bg = re.search(r"--wm-coin-pp-bg: (#\w+)", TOKENS).group(1)
    assert ratio(fg, bg) >= 4.5
    assert re.search(r"@media print\s*\{[^}]*#000", CSS)
