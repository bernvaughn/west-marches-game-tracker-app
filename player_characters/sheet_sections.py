"""Registry for character sheet sections.

Other apps can register sections to be rendered on the character sheet
without editing the sheet template. Sections render in order after the
ledger box, and only on screen (they carry ``no-print``).
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SheetSection:
    """A registered sheet section."""

    key: str
    order: int
    template: str
    context_fn: object  # Callable[[HttpRequest, Character], dict | None]
    visible_fn: object | None = None  # Callable[[HttpRequest, Character], bool] | None


_sections: dict[str, SheetSection] = {}


def register_sheet_section(
    key: str,
    order: int,
    template: str,
    context_fn: object,
    visible_fn: object | None = None,
) -> None:
    """Register a sheet section.

    A repeated ``key`` replaces the old entry (safe for ``ready()`` called
    twice during tests or hot reload).

    Args:
        key: Unique identifier for the section.
        order: Sort order (lower renders first). Ties broken by key.
        template: Template path to render for this section.
        context_fn: Callable ``(request, character) -> dict | None``.
            Returning ``None`` skips the section.
        visible_fn: Optional callable ``(request, character) -> bool``.
            A falsy result skips the section.
    """
    _sections[key] = SheetSection(
        key=key,
        order=order,
        template=template,
        context_fn=context_fn,
        visible_fn=visible_fn,
    )


def get_sheet_sections(request, character) -> list[dict]:
    """Return visible sections with their rendered context.

    Sections are sorted by ``(order, key)``. Sections whose ``visible_fn``
    returns falsy, whose ``context_fn`` returns ``None``, or whose
    callbacks raise an exception are skipped (the exception is logged).
    A broken plugin must not break the sheet.

    Returns:
        List of dicts with keys ``key``, ``template``, ``context``.
    """
    result = []
    for section in sorted(_sections.values(), key=lambda s: (s.order, s.key)):
        # Check visibility
        if section.visible_fn is not None:
            try:
                if not section.visible_fn(request, character):
                    continue
            except Exception:
                logger.exception("visible_fn raised for sheet section %r", section.key)
                continue

        # Build context
        try:
            ctx = section.context_fn(request, character)
        except Exception:
            logger.exception("context_fn raised for sheet section %r", section.key)
            continue

        if ctx is None:
            continue

        result.append(
            {
                "key": section.key,
                "order": section.order,
                "template": section.template,
                "context": ctx,
            }
        )

    return result


def _clear_sections() -> None:
    """Clear all registered sections (for tests only)."""
    _sections.clear()
