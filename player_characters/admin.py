from django.contrib import admin

from .models import Character, Trade, TradeLine

admin.site.register([Character, Trade, TradeLine])
