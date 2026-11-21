"""Helper to append a stacked-item unit summary to a ledger note.

Pure function: no Django imports, no database access.
"""

from ledger.services import Line

from . import stacked


def with_unit_summary(note: str, lines: list[Line]) -> str:
    """Append a summary of stacked-item units to ``note``.

    For each stacked item in ``lines``, adds a fragment like
    `` (+10 sheet Parchment, -3 ft Rope)`` using ``stacked.unit_label``.
    Non-stacked items add nothing. The original ``note`` is kept first
    (the user's text is kept first). Returns the note unchanged when
    no stacked lines are present.
    """
    if not note:
        note = ""
    parts = []
    for line in lines:
        if line.item and line.item.is_stacked:
            label = stacked.unit_label(line.item, abs(line.quantity))
            sign = "+" if line.quantity > 0 else "-"
            parts.append(f"{sign}{label}")
    if not parts:
        return note
    summary = ", ".join(parts)
    if note:
        return f"{note} ({summary})"
    return f"({summary})"
