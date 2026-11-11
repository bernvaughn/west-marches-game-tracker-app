from django import template

from map import xp

register = template.Library()


@register.simple_tag
def xp_for(club, band):
    return xp.xp_for(club, band)


@register.filter
def band_label(band):
    return xp.band_label(band)
