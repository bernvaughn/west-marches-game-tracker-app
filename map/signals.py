from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Club

from .xp import copy_default_xp_table


@receiver(post_save, sender=Club)
def club_created(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        copy_default_xp_table(instance)
