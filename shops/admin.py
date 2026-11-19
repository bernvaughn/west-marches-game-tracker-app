from django.contrib import admin

from .models import FavoriteShop, Rotation, Shop, ShopStock

admin.site.register([Shop, ShopStock, Rotation, FavoriteShop])
