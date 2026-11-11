from django.db import transaction


def item_is_referenced(item):
    """True if any model points at the item (any relation, including CASCADE/SET_NULL ones)."""
    for rel in item._meta.related_objects:
        if rel.related_model._default_manager.filter(**{rel.field.name: item}).exists():
            return True
    return False


def delete_or_retire(item):
    """Delete an unused item; retire a used one. Returns True when deleted."""
    with transaction.atomic():
        if item_is_referenced(item):
            item.retired = True
            item.save(update_fields=["retired"])
            return False
        item.delete()
        return True
