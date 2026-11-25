from .entries import add_entry, edit_entry, remove_entry
from .merge import (
    merge_confirm,
    merge_form,
    suggest_matches_view,
)

__all__ = [
    "add_entry",
    "edit_entry",
    "remove_entry",
    "merge_form",
    "merge_confirm",
    "suggest_matches_view",
]
