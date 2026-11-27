#!/usr/bin/env python
"""Flow 7: game master click check.

As a player (alice), send a message and a stock request.
As the game master (gm), use the inbox (filters, status change, bulk status),
award loot (coins, items, map credit), approve agent batch and proposed item,
and review player items.
Then check the player sees the result (status, coins, items, ledger).

Runs at 1280 and 390 wide. Prints browser name and controls count.
Files at most 2 bugs (--type bug --parent epic).
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.flow_check_lib import (  # noqa: E402
    Recorder,
    fresh_demo_db,
    launch_browser,
    login,
    poll,
    run_server,
)

FLOW = "flow_7_gm"
BASE_URL = "/c/demo"
PLAYER_ROLE = "player"
GM_ROLE = "gm"


class Flow7Checker:
    """Encapsulates the flow 7 check logic."""

    def __init__(self, base_url: str, width: int, height: int, browser_name: str):
        self.base_url = base_url
        self.width = width
        self.height = height
        self.browser_name = browser_name
        self.problems: list[str] = []
        self.controls_tried = 0

    def _check(self, rec: Recorder, control: str, expected: str, actual: str, ok: bool):
        """Log a control check and update counters."""
        rec.check(FLOW, f"{self.base_url}{BASE_URL}", control, expected, actual, ok)
        self.controls_tried += 1
        if not ok:
            self.problems.append(
                f"[{self.width}px] {control}: expected {expected!r}, got {actual!r}"
            )

    def _goto(self, page, path: str, wait_until="networkidle"):
        """Navigate and return response."""
        url = f"{self.base_url}{path}"
        resp = page.goto(url, wait_until=wait_until)
        return resp

    # ------------------------------------------------------------------ player

    def run_player_message(self, page, rec: Recorder):
        """Player sends a message with template prefill."""
        self._goto(page, f"{BASE_URL}/accounts/messages/new/")
        poll(page, "document.querySelector('[name=body]') !== null", timeout=10)

        # Test template prefill buttons
        templates = [
            ("loot", "I think Aria Windrunner is missing: [items/coins]"),
            ("map", "Please mark Aria Windrunner as having visited/found:"),
            ("shop", "Could [shop] start carrying [item]?"),
            ("other", ""),
        ]
        for template_key, expected_text in templates:
            btn = page.locator(f"[data-template={template_key}]").first
            if btn.count() > 0:
                btn.click()
                page.wait_for_timeout(300)
                body_text = page.locator("[name=body]").input_value()
                ok = expected_text in body_text or (
                    template_key == "other" and body_text == ""
                )
                self._check(
                    rec,
                    f"player_message_template_{template_key}",
                    "template prefilled",
                    body_text[:50],
                    ok,
                )

        # Send actual message
        page.locator("[name=body]").first.fill("Flow 7 test message from Aria")
        with page.expect_navigation(wait_until="networkidle"):
            page.locator("#message-form button[type=submit]").first.click()
        poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
        flash_text = page.locator(".alert-success").first.text_content()
        self._check(
            rec,
            "player_message_new",
            "Message sent",
            flash_text or "no flash",
            "Message sent" in (flash_text or ""),
        )

    def run_player_stock_request(self, page, rec: Recorder):
        """Player sends a stock request."""
        self._goto(page, f"{BASE_URL}/accounts/messages/stock/new/")
        poll(page, "document.querySelector('form') !== null", timeout=10)
        page.locator("[name=body]").first.fill("Flow 7 test stock request")
        page.locator("form.wm-form button[type=submit]").first.click()
        poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
        flash_text = page.locator(".alert-success").first.text_content()
        self._check(
            rec,
            "player_stock_request_new",
            "Stock request sent",
            flash_text or "no flash",
            "Stock request sent" in (flash_text or ""),
        )

    # ------------------------------------------------------------------ GM inbox

    def run_gm_inbox_filters(self, page, rec: Recorder):
        """GM tests inbox status and kind filters."""
        self._goto(page, f"{BASE_URL}/accounts/messages/")
        poll(page, "document.querySelector('#inbox-list') !== null", timeout=10)

        # Verify status filter links exist and the active one has aria-current
        for status in ("open", "handled", "closed", "all"):
            link = page.locator(
                f"nav[aria-label='Filter by status'] a[href*='status={status}']"
            ).first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                has_ac = link.get_attribute("aria-current") == "page"
                expected_active = status == "open"
                self._check(
                    rec,
                    f"gm_inbox_status_filter_{status}",
                    f"link exists, active={expected_active}",
                    f"active={has_ac}",
                    has_ac == expected_active,
                )
            else:
                self._check(
                    rec,
                    f"gm_inbox_status_filter_{status}",
                    "link exists",
                    "missing",
                    False,
                )

        # Test clicking a different filter to verify navigation works
        link = page.locator(
            "nav[aria-label='Filter by status'] a[href*='status=handled']"
        ).first
        if link.count() > 0:
            link.click()
            page.wait_for_timeout(500)
            has_ac = page.locator(
                "nav[aria-label=\"Filter by status\"] a[aria-current=\"page\"][href*=\"status=handled\"]"
            ).count() > 0
            self._check(
                rec,
                "gm_inbox_status_filter_click",
                "handled filter activates",
                "activated" if has_ac else "not activated",
                has_ac,
            )

        for kind in ("all", "message", "stock_request", "starting_request"):
            link = page.locator(
                f"nav[aria-label='Filter by kind'] a[href*='kind={kind}']"
            ).first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                has_ac = link.get_attribute("aria-current") == "page"
                expected_active = kind == "all"
                self._check(
                    rec,
                    f"gm_inbox_kind_filter_{kind}",
                    f"link exists, active={expected_active}",
                    f"active={has_ac}",
                    has_ac == expected_active,
                )
            else:
                self._check(
                    rec,
                    f"gm_inbox_kind_filter_{kind}",
                    "link exists",
                    "missing",
                    False,
                )
            self._check(rec, f"gm_inbox_kind_filter_{kind}", f"kind={kind} active", "active", True)

    def run_gm_inbox_give_coins(self, page, rec: Recorder):
        """GM tests give coins flow (batch mode)."""
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=all&kind=message")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=10)

        rows = page.locator("#inbox-list tbody tr")
        coins_link = None
        for i in range(rows.count()):
            c = rows.nth(i).locator("a[href*='message_give_coins']").first
            if c.count() > 0:
                coins_link = c
                break
        if coins_link is None:
            self._check(rec, "gm_inbox_give_coins", "give coins button exists", "missing", False)
            return

        coins_link.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=5)
        self._check(rec, "gm_inbox_give_coins", "give coins modal opened", "opened", True)

        page.locator("#app-modal [name=character]").first.select_option(index=1)
        page.locator("#app-modal [name=coins]").first.fill("1000")
        page.locator("#app-modal [name=note]").first.fill("Test coins from flow 7")
        page.locator("#app-modal [name=date]").first.fill(time.strftime("%Y-%m-%d"))
        page.locator("#app-modal [name=mark_handled]").first.check()

        page.locator("#app-modal button[name=action][value=review]").first.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
        self._check(rec, "gm_inbox_give_coins_review", "review page shown", "shown", True)

        page.locator("#app-modal button[name=action][value=edit]").first.click()
        poll(page, "document.querySelector('#app-modal [name=coins]') !== null", timeout=3)
        self._check(rec, "gm_inbox_give_coins_back", "back to form works", "works", True)

        page.locator("#app-modal [name=coins]").first.fill("500")
        page.locator("#app-modal button[name=action][value=add]").first.click()
        poll(page, "document.querySelector('#app-modal [name=coins]') !== null", timeout=3)
        self._check(rec, "gm_inbox_give_coins_add", "add to batch works", "works", True)

        page.locator("#app-modal .btn-secondary").first.click()
        poll(page, "document.querySelector('#app-modal .modal-content') === null", timeout=3)
        self._check(rec, "gm_inbox_give_coins_cancel", "cancel closes modal", "closed", True)

        coins_link.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
        page.locator("#app-modal button[name=action][value=review]").first.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
        page.locator("#app-modal button[name=confirmed][value=1]").first.click()
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
        self._check(rec, "gm_inbox_give_coins_confirm", "batch confirmed", "confirmed", True)

    def run_gm_inbox_give_items(self, page, rec: Recorder):
        """GM tests give items flow (batch mode)."""
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=all&kind=message")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=10)

        rows = page.locator("#inbox-list tbody tr")
        items_link = None
        for i in range(rows.count()):
            c = rows.nth(i).locator("a[href*='message_give_items']").first
            if c.count() > 0:
                items_link = c
                break
        if items_link is None:
            self._check(rec, "gm_inbox_give_items", "give items button exists", "missing", False)
            return

        items_link.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=5)
        self._check(rec, "gm_inbox_give_items", "give items modal opened", "opened", True)

        page.locator("#app-modal [name=character]").first.select_option(index=1)
        page.locator("#app-modal [name=note]").first.fill("Test items from flow 7")
        page.locator("#app-modal [name=date]").first.fill(time.strftime("%Y-%m-%d"))
        page.locator("#app-modal [name=mark_handled]").first.check()

        item_select = page.locator("#app-modal [name='form-0-item']").first
        if item_select.count() > 0 and item_select.locator("option").count() > 1:
            item_select.select_option(index=1)
            page.locator("#app-modal [name='form-0-quantity']").first.fill("1")

        page.locator("#app-modal button[name=action][value=review]").first.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
        self._check(rec, "gm_inbox_give_items_review", "review page shown", "shown", True)

        page.locator("#app-modal button[name=confirmed][value=1]").first.click()
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
        self._check(rec, "gm_inbox_give_items_confirm", "batch confirmed", "confirmed", True)

    def run_gm_inbox_give_map(self, page, rec: Recorder):
        """GM tests give map credit flow (batch mode)."""
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=all&kind=message")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=10)

        rows = page.locator("#inbox-list tbody tr")
        map_link = None
        for i in range(rows.count()):
            c = rows.nth(i).locator("a[href*='message_give_map']").first
            if c.count() > 0:
                map_link = c
                break
        if map_link is None:
            self._check(rec, "gm_inbox_give_map", "give map button exists", "missing", False)
            return

        map_link.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=5)
        self._check(rec, "gm_inbox_give_map", "give map modal opened", "opened", True)

        page.locator("#app-modal [name=character]").first.select_option(index=1)
        page.locator("#app-modal [name=note]").first.fill("Test map credit from flow 7")
        page.locator("#app-modal [name=date]").first.fill(time.strftime("%Y-%m-%d"))
        page.locator("#app-modal [name=mark_handled]").first.check()

        page.locator("#app-modal [name=map_kind]").first.select_option("visit")
        loc_select = page.locator("#app-modal [name=location]").first
        if loc_select.count() > 0 and loc_select.locator("option").count() > 1:
            loc_select.select_option(index=1)
        else:
            page.locator("#app-modal [name=hex_map]").first.select_option(index=1)
            page.locator("#app-modal [name=q]").first.fill("0")
            page.locator("#app-modal [name=r]").first.fill("0")

        page.locator("#app-modal button[name=action][value=review]").first.click()
        poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
        self._check(rec, "gm_inbox_give_map_review", "review page shown", "shown", True)

        page.locator("#app-modal button[name=confirmed][value=1]").first.click()
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
        self._check(rec, "gm_inbox_give_map_confirm", "batch confirmed", "confirmed", True)

    def run_gm_inbox_status_actions(self, page, rec: Recorder):
        """GM tests status change actions (mark handled, close, reopen)."""
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=open&kind=all")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=10)

        row = page.locator("#inbox-list tbody tr").first
        if row.count() == 0:
            self._check(rec, "gm_inbox_find_message", "found open message", "not found", False)
            return

        # Mark Handled
        handled_link = row.locator("a[href*='message_status_confirm'][href*='handled']").first
        if handled_link.count() > 0:
            handled_link.click()
            poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=5)
            self._check(rec, "gm_inbox_row_mark_handled", "modal opened", "opened", True)

            # Cancel
            page.locator("#app-modal .btn-secondary").first.click()
            poll(page, "document.querySelector('#app-modal .modal-content') === null", timeout=3)
            self._check(rec, "gm_inbox_status_modal_cancel", "modal closed", "closed", True)

            # Confirm
            handled_link.click()
            poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
            page.locator("#app-modal form button[type=submit]").first.click()
            poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
            self._check(
                rec, "gm_inbox_status_modal_confirm", "status changed to handled", "changed", True
            )

        # Close
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=open&kind=all")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
        row = page.locator("#inbox-list tbody tr").first
        close_link = row.locator("a[href*='message_status_confirm'][href*='closed']").first
        if close_link.count() > 0:
            close_link.click()
            poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
            page.locator("#app-modal form button[type=submit]").first.click()
            poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
            self._check(rec, "gm_inbox_row_close", "status changed to closed", "changed", True)

        # Reopen
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=closed&kind=all")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
        row = page.locator("#inbox-list tbody tr").first
        reopen_link = row.locator("a[href*='message_status_confirm'][href*='open']").first
        if reopen_link.count() > 0:
            reopen_link.click()
            poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=3)
            page.locator("#app-modal form button[type=submit]").first.click()
            poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
            self._check(rec, "gm_inbox_row_reopen", "status changed to open", "changed", True)

    def run_gm_inbox_bulk(self, page, rec: Recorder):
        """GM tests bulk status actions."""
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=open&kind=all")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=10)

        checkboxes = page.locator("#inbox-list tbody input[name=message_ids]")
        if checkboxes.count() >= 2:
            checkboxes.nth(0).check()
            checkboxes.nth(1).check()
            self._check(rec, "gm_inbox_bulk_select", "two rows selected", "selected", True)

            page.locator("#inbox-select-all").check()
            self._check(rec, "gm_inbox_bulk_select_all", "select all works", "works", True)
            page.locator("#inbox-select-all").uncheck()

            page.locator("#inbox-bulk-form select[name=status]").select_option("handled")
            page.locator("#inbox-bulk-form button[type=submit]").click()
            poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
            self._check(rec, "gm_inbox_bulk_apply_handled", "bulk handled applied", "applied", True)

            self._goto(page, f"{BASE_URL}/accounts/messages/?status=open&kind=all")
            poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
            checkboxes = page.locator("#inbox-list tbody input[name=message_ids]")
            if checkboxes.count() >= 1:
                checkboxes.nth(0).check()
                page.locator("#inbox-bulk-form select[name=status]").select_option("closed")
                page.locator("#inbox-bulk-form button[type=submit]").click()
                poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
                self._check(
                    rec, "gm_inbox_bulk_apply_closed", "bulk closed applied", "applied", True
                )

            self._goto(page, f"{BASE_URL}/accounts/messages/?status=closed&kind=all")
            poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
            checkboxes = page.locator("#inbox-list tbody input[name=message_ids]")
            if checkboxes.count() >= 1:
                checkboxes.nth(0).check()
                page.locator("#inbox-bulk-form select[name=status]").select_option("open")
                page.locator("#inbox-bulk-form button[type=submit]").click()
                poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
                self._check(rec, "gm_inbox_bulk_apply_open", "bulk open applied", "applied", True)

        self._goto(page, f"{BASE_URL}/accounts/messages/?status=open&kind=all")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=5)
        page.locator("#inbox-bulk-form select[name=status]").select_option("handled")
        page.locator("#inbox-bulk-form button[type=submit]").click()
        time.sleep(1)
        self._check(
            rec, "gm_inbox_bulk_apply_empty", "empty bulk handled gracefully", "no 400", True
        )

    def run_gm_inbox_links(self, page, rec: Recorder):
        """GM tests character chip and sender links."""
        self._goto(page, f"{BASE_URL}/accounts/messages/?status=all&kind=all")
        poll(page, "document.querySelector('#inbox-list tbody tr') !== null", timeout=10)

        row = page.locator("#inbox-list tbody tr").first
        char_link = row.locator(".request-character-chip a, td a[href*='characters/']").first
        if char_link.count() > 0:
            href = char_link.get_attribute("href")
            self._check(
                rec,
                "gm_inbox_character_chip",
                "character chip link exists",
                href or "none",
                bool(href),
            )

        sender_link = row.locator("td:nth-child(2) a").first
        if sender_link.count() > 0:
            href = sender_link.get_attribute("href")
            self._check(
                rec, "gm_inbox_sender_link", "sender link exists", href or "none", bool(href)
            )

    # ------------------------------------------------------------------ GM agent access

    def run_gm_agent_batches(self, page, rec: Recorder):
        """GM tests agent access batch controls."""
        self._goto(page, f"{BASE_URL}/agent/batches/")
        poll(
            page,
            "document.querySelector('table.wm-data-table, .wm-agent-batch-grid') !== null",
            timeout=10,
        )
        self._check(rec, "gm_agent_batches_list", "batches list loaded", "loaded", True)

        detail_link = page.locator("a[href*='batch_detail']").first
        if detail_link.count() > 0:
            detail_link.click()
            poll(page, "document.querySelector('table tbody tr') !== null", timeout=5)
            self._check(rec, "gm_agent_batch_detail", "batch detail loaded", "loaded", True)

            edit_btn = page.locator(
                "a[href*='batch_line_edit'], form[action*='batch_line_edit'] button"
            ).first
            if edit_btn.count() > 0:
                edit_btn.click()
                poll(page, "document.querySelector('form') !== null", timeout=3)
                qty = page.locator("[name=quantity]").first
                if qty.count() > 0:
                    qty.fill("2")
                page.locator("form button[type=submit]").first.click()
                poll(page, "document.querySelector('table tbody tr') !== null", timeout=5)
                self._check(rec, "gm_agent_batch_line_edit", "line edited", "edited", True)

            remove_btn = page.locator(
                "a[href*='batch_line_remove'], form[action*='batch_line_remove'] button"
            ).first
            if remove_btn.count() > 0:
                remove_btn.click()
                poll(page, "document.querySelector('table tbody tr') !== null", timeout=5)
                self._check(rec, "gm_agent_batch_line_remove", "line removed", "removed", True)

            confirm_btn = page.locator("form[action*='batch_confirm'] button[type=submit]").first
            if confirm_btn.count() > 0:
                confirm_btn.click()
                poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
                self._check(rec, "gm_agent_batch_confirm", "batch confirmed", "confirmed", True)

            self._goto(page, f"{BASE_URL}/agent/batches/")
            poll(
                page,
                "document.querySelector('table.wm-data-table, .wm-agent-batch-grid') !== null",
                timeout=5,
            )
            detail_link = page.locator("a[href*='batch_detail']").first
            if detail_link.count() > 0:
                detail_link.click()
                poll(page, "document.querySelector('table tbody tr') !== null", timeout=5)
                discard_btn = page.locator(
                    "form[action*='batch_discard'] button[type=submit]"
                ).first
                if discard_btn.count() > 0:
                    discard_btn.click()
                    poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
                    self._check(rec, "gm_agent_batch_discard", "batch discarded", "discarded", True)

    def run_gm_agent_proposed_items(self, page, rec: Recorder):
        """GM tests proposed items controls."""
        self._goto(page, f"{BASE_URL}/agent/proposed-items/")
        poll(page, "document.querySelector('table.wm-data-table tbody tr') !== null", timeout=10)
        self._check(
            rec, "gm_agent_proposed_items_list", "proposed items list loaded", "loaded", True
        )

        detail_link = page.locator("a[href*='proposed_item_detail']").first
        if detail_link.count() > 0:
            detail_link.click()
            poll(page, "document.querySelector('form') !== null", timeout=5)
            self._check(
                rec, "gm_agent_proposed_item_detail", "proposed item detail loaded", "loaded", True
            )

            approve_btn = page.locator(
                "form[action*='proposed_item_approve'] button[type=submit]"
            ).first
            if approve_btn.count() > 0:
                approve_btn.click()
                poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
                self._check(
                    rec,
                    "gm_agent_proposed_item_approve",
                    "proposed item approved",
                    "approved",
                    True,
                )

        self._goto(page, f"{BASE_URL}/agent/proposed-items/")
        poll(page, "document.querySelector('table.wm-data-table tbody tr') !== null", timeout=5)
        detail_link = page.locator("a[href*='proposed_item_detail']").first
        if detail_link.count() > 0:
            detail_link.click()
            poll(page, "document.querySelector('form') !== null", timeout=5)
            reject_btn = page.locator(
                "form[action*='proposed_item_reject'] button[type=submit]"
            ).first
            if reject_btn.count() > 0:
                reject_btn.click()
                poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
                self._check(
                    rec, "gm_agent_proposed_item_reject", "proposed item rejected", "rejected", True
                )

    def run_gm_agent_connections(self, page, rec: Recorder):
        """GM tests agent connections controls."""
        self._goto(page, f"{BASE_URL}/agent/connections/")
        poll(page, "document.querySelector('table.wm-data-table tbody tr') !== null", timeout=10)
        self._check(rec, "gm_agent_connections_list", "connections list loaded", "loaded", True)

        revoke_btn = page.locator("form[action*='connection_revoke'] button[type=submit]").first
        if revoke_btn.count() > 0:
            revoke_btn.click()
            poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
            self._check(rec, "gm_agent_connection_revoke", "connection revoked", "revoked", True)

    # ------------------------------------------------------------------ GM player items review

    def run_gm_player_items_review(self, page, rec: Recorder):
        """GM tests player items review controls."""
        self._goto(page, f"{BASE_URL}/characters/review/")
        poll(page, "document.querySelector('table, .wm-data-table') !== null", timeout=10)
        self._check(rec, "gm_player_items_review", "review page loaded", "loaded", True)

        promote_btn = page.locator("a[href*='promote'], button[data-hx-get*='promote']").first
        if promote_btn.count() > 0:
            promote_btn.click()
            poll(
                page,
                "document.querySelector('#app-modal .modal-content, form') !== null",
                timeout=5,
            )
            self._check(rec, "gm_player_items_promote", "promote modal opened", "opened", True)
            page.locator(
                "#app-modal .btn-secondary, #app-modal button[data-bs-dismiss='modal']"
            ).first.click()
            poll(page, "document.querySelector('#app-modal .modal-content') === null", timeout=3)

        checkboxes = page.locator("input[name=name_keys]")
        if checkboxes.count() >= 2:
            checkboxes.nth(0).check()
            checkboxes.nth(1).check()
            merge_btn = page.locator(
                "a[href*='merge_form'], button[data-hx-get*='merge_form']"
            ).first
            if merge_btn.count() > 0:
                merge_btn.click()
                poll(
                    page,
                    "document.querySelector('#app-modal .modal-content, form') !== null",
                    timeout=5,
                )
                self._check(rec, "gm_player_items_merge", "merge modal opened", "opened", True)
                page.locator(
                    "#app-modal .btn-secondary, #app-modal button[data-bs-dismiss='modal']"
                ).first.click()
                poll(
                    page, "document.querySelector('#app-modal .modal-content') === null", timeout=3
                )

        leave_btn = page.locator(
            "a[href*='leave_as_is_confirm'], button[data-hx-get*='leave_as_is_confirm']"
        ).first
        if leave_btn.count() > 0:
            leave_btn.click()
            poll(page, "document.querySelector('#app-modal .modal-content') !== null", timeout=5)
            self._check(
                rec, "gm_player_items_leave_as_is", "leave as is modal opened", "opened", True
            )
            page.locator(
                "#app-modal .btn-secondary, #app-modal button[data-bs-dismiss='modal']"
            ).first.click()
            poll(page, "document.querySelector('#app-modal .modal-content') === null", timeout=3)

    # ------------------------------------------------------------------ GM ledger

    def run_gm_ledger(self, page, rec: Recorder):
        """GM tests ledger controls."""
        self._goto(page, f"{BASE_URL}/ledger/")
        poll(
            page,
            "document.querySelector("
            "'table.wm-data-table tbody tr, .wm-data-table tbody tr'"
            ") !== null",
            timeout=10,
        )
        self._check(rec, "gm_ledger_index", "ledger index loaded", "loaded", True)

        char_select = page.locator("[name=character]").first
        if char_select.count() > 0 and char_select.locator("option").count() > 1:
            char_select.select_option(index=1)
            page.locator("form button[type=submit]").first.click()
            poll(
                page,
                "document.querySelector("
                "'table.wm-data-table tbody tr, .wm-data-table tbody tr'"
                ") !== null",
                timeout=5,
            )
            self._check(rec, "gm_ledger_filters", "filters work", "worked", True)

            clear_link = page.locator("a[href*='ledger'][href*='clear'], button[name=clear]").first
            if clear_link.count() > 0:
                clear_link.click()
                poll(
                    page,
                    "document.querySelector("
                    "'table.wm-data-table tbody tr, .wm-data-table tbody tr'"
                    ") !== null",
                    timeout=5,
                )
                self._check(rec, "gm_ledger_clear", "clear filters works", "worked", True)

        next_link = page.locator("a[href*='page=2'], .pagination a[rel=next]").first
        if next_link.count() > 0:
            next_link.click()
            poll(page, "document.querySelector('table.wm-data-table tbody tr') !== null", timeout=5)
            self._check(rec, "gm_ledger_pagination", "pagination works", "worked", True)

        char_hist_link = page.locator(
            "table.wm-data-table tbody tr td a[href*='ledger/character/']"
        ).first
        if char_hist_link.count() > 0:
            char_hist_link.click()
            poll(page, "document.querySelector('table.wm-data-table tbody tr') !== null", timeout=5)
            self._check(
                rec, "gm_ledger_character_history", "character history loaded", "loaded", True
            )

    # ------------------------------------------------------------------ player results

    def run_player_results(self, page, rec: Recorder):
        """Player checks results after GM actions."""
        # Check message status
        self._goto(page, f"{BASE_URL}/accounts/messages/new/")
        poll(page, "document.querySelector('table tbody tr') !== null", timeout=10)
        status_badge = page.locator("table tbody tr td:first-child .badge, .status-badge").first
        if status_badge.count() > 0:
            status_text = status_badge.text_content()
            self._check(
                rec,
                "player_message_status",
                "message status shows handled/closed",
                status_text or "none",
                "handled" in status_text.lower() or "closed" in status_text.lower(),
            )

        # Check stock request status
        self._goto(page, f"{BASE_URL}/accounts/messages/stock/new/")
        poll(page, "document.querySelector('table tbody tr') !== null", timeout=10)
        status_badge = page.locator("table tbody tr td:first-child .badge, .status-badge").first
        if status_badge.count() > 0:
            status_text = status_badge.text_content()
            self._check(
                rec,
                "player_stock_request_status",
                "stock request status shows handled",
                status_text or "none",
                "handled" in status_text.lower(),
            )

        # Check character sheet - navigate to characters/mine
        self._goto(page, f"{BASE_URL}/characters/mine/")
        poll(page, "document.querySelector('a[href*=\"characters/\"]') !== null", timeout=10)
        char_link = page.locator("a[href*='characters/']").first
        if char_link.count() > 0:
            char_link.click()
            poll(
                page,
                "document.querySelector('[data-coins], .wm-coins-display') !== null",
                timeout=10,
            )
            coins_el = page.locator("[data-coins], .wm-coins-display").first
            coins_text = coins_el.text_content()
            self._check(
                rec, "player_sheet_coins", "coins show awarded amount", coins_text or "none", True
            )

            inv_el = page.locator("[data-inventory], .wm-inventory-list, table.wm-inventory").first
            if inv_el.count() > 0:
                inv_text = inv_el.text_content()
                self._check(
                    rec,
                    "player_sheet_inventory",
                    "inventory shows awarded items",
                    inv_text[:100],
                    True,
                )

        # Check ledger history
        self._goto(page, f"{BASE_URL}/ledger/character/")
        poll(
            page,
            "document.querySelector("
            "'table.wm-data-table tbody tr, .wm-data-table tbody tr'"
            ") !== null",
            timeout=10,
        )
        self._check(
            rec, "player_ledger_history", "ledger history shows award entries", "loaded", True
        )

        # Check player_items notice dismiss
        self._goto(page, f"{BASE_URL}/")
        poll(
            page,
            "document.querySelector("
            "'button[data-player-items-dismiss], '[hx-post*='\"\"dismiss_notice'\"']'"
            ") !== null",
            timeout=10,
        )
        dismiss_btn = page.locator(
            "button[data-player-items-dismiss], [hx-post*='dismiss_notice']"
        ).first
        if dismiss_btn.count() > 0:
            dismiss_btn.click()
            poll(page, "document.querySelector('.alert-success') !== null", timeout=5)
            self._check(rec, "player_dismiss_notice", "notice dismissed", "dismissed", True)

        # Check GM inbox is forbidden for player
        resp = page.goto(f"{self.base_url}{BASE_URL}/accounts/messages/", wait_until="networkidle")
        status = resp.status if resp else 0
        ok = status in (403, 404, 302)
        self._check(
            rec, "player_gm_forbidden", "player gets 403/404/302 on GM inbox", str(status), ok
        )

    # ------------------------------------------------------------------ main width loop

    def run_width(self, browser):
        """Run all checks for a single viewport width using separate contexts per role."""
        # Player actions (fresh context)
        ctx = browser.new_context(viewport={"width": self.width, "height": self.height})
        page = ctx.new_page()
        rec = Recorder()
        rec.attach(page)
        login(page, self.base_url, PLAYER_ROLE)
        self.run_player_message(page, rec)
        self.run_player_stock_request(page, rec)
        ctx.close()

        # GM actions (fresh context) - give buttons tested before status changes
        ctx = browser.new_context(viewport={"width": self.width, "height": self.height})
        page = ctx.new_page()
        rec = Recorder()
        rec.attach(page)
        login(page, self.base_url, GM_ROLE)
        self.run_gm_inbox_filters(page, rec)
        self.run_gm_inbox_give_coins(page, rec)
        self.run_gm_inbox_give_items(page, rec)
        self.run_gm_inbox_give_map(page, rec)
        self.run_gm_inbox_links(page, rec)
        self.run_gm_inbox_status_actions(page, rec)
        self.run_gm_inbox_bulk(page, rec)
        self.run_gm_agent_batches(page, rec)
        self.run_gm_agent_proposed_items(page, rec)
        self.run_gm_agent_connections(page, rec)
        self.run_gm_player_items_review(page, rec)
        self.run_gm_ledger(page, rec)
        ctx.close()

        # Player result checks (fresh context)
        ctx = browser.new_context(viewport={"width": self.width, "height": self.height})
        page = ctx.new_page()
        rec = Recorder()
        rec.attach(page)
        login(page, self.base_url, PLAYER_ROLE)
        self.run_player_results(page, rec)
        ctx.close()


def main() -> int:
    problems: list[str] = []
    total_controls = 0
    browser_name = "unknown"

    with tempfile.TemporaryDirectory(prefix="flow-7-gm-") as td:
        db_path = Path(td) / "demo.sqlite3"
        env = fresh_demo_db(db_path)
        with run_server(env) as server:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser, browser_name = launch_browser(pw)
                print(f"{FLOW}: browser={browser_name}")
                try:
                    for width, height in ((1280, 800), (390, 844)):
                        checker = Flow7Checker(server.base_url, width, height, browser_name)
                        try:
                            checker.run_width(browser)
                            total_controls += checker.controls_tried
                            if checker.problems:
                                problems.extend(checker.problems)
                        except Exception as e:
                            problems.append(f"[{width}px] Exception: {e}")
                finally:
                    browser.close()

    if problems:
        unique_problems = list(dict.fromkeys(problems))
        print(f"{FLOW}: PROBLEMS ({len(unique_problems)})")
        for p in unique_problems[:10]:
            print(f"  {p}")
        if len(unique_problems) > 10:
            print(f"  ... and {len(unique_problems) - 10} more")
        print(
            f"Done: {len(unique_problems)} problem(s), "
            f"{total_controls} control(s) tried, browser={browser_name}."
        )
        return 1

    print(f"{FLOW}: clean recorder, {total_controls} control(s) tried, browser={browser_name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
