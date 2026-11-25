"""Registry for character sheet sections.

Other apps can register sections to be rendered on the character sheet
without editing the sheet template. Sections render in order after the
ledger box, and only on screen (they carry ``no-print``).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SheetSection:
    """A registered sheet section."""

    key: str
    order: int
    template: str
    context_fn: Callable[..., dict | None]  # (request, character) -> dict | None
    visible_fn: Callable[..., bool] | None = None  # (request, character) -> bool


_sections: dict[str, SheetSection] = {}
_app_defaults: dict[str, SheetSection] = {}
_cleared: bool = False


def register_sheet_section(
    key: str,
    order: int,
    template: str,
    context_fn: Callable[..., dict | None],
    visible_fn: Callable[..., bool] | None = None,
) -> None:
    """Register a sheet section.

    A repeated ``key`` replaces the old entry (safe for ``ready()`` called
    twice during tests or hot reload).

    Sections registered before the first test-only clear are treated as
    app-defaults: they are restored by :func:`restore_app_defaults` after a
    test fixture wipes the live registry, so later test files still see the
    sheet sections apps provide at app load.

    Args:
        key: Unique identifier for the section.
        order: Sort order (lower renders first). Ties broken by key.
        template: Template path to render for this section.
        context_fn: Callable ``(request, character) -> dict | None``.
            Returning ``None`` skips the section.
        visible_fn: Optional callable ``(request, character) -> bool``.
            A falsy result skips the section.
    """
    section = SheetSection(
        key=key,
        order=order,
        template=template,
        context_fn=context_fn,
        visible_fn=visible_fn,
    )
    _sections[key] = section
    if not _cleared:
        _app_defaults[key] = section


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


def restore_app_defaults() -> None:
    """Re-register every app-default section into the live registry.

    Test fixtures that clear the live registry wipe the app-default sections
    registered at app load. Call this after clearing so later test files
    still see the character sheet sections that apps provide.
    """
    for section in _app_defaults.values():
        register_sheet_section(
            section.key,
            section.order,
            section.template,
            section.context_fn,
            section.visible_fn,
        )


def _clear_sections() -> None:
    """Clear all registered sections (for tests only).

    App-defaults registered before the first clear are preserved in
    :data:`_app_defaults` and can be restored with
    :func:`restore_app_defaults`.
    """
    global _cleared
    _cleared = True
    _sections.clear()
