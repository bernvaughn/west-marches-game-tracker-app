from django.contrib import admin

from .models import Rotation, Shop, ShopStock

admin.site.register([Shop, ShopStock, Rotation])
