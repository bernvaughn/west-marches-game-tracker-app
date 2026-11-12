from .selection import own_characters, selected_character


def selection(request):
    if getattr(request, "club", None) is None:
        return {}
    chosen = selected_character(request)
    request.selected_character = chosen
    return {"own_characters": list(own_characters(request)), "selected_character": chosen}
