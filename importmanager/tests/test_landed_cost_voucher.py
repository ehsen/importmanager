import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import LandedCostVoucher
from importmanager.importmanager.overrides.custom_landed_cost_voucher import CustomLandedCostVoucher
from importmanager import import_utils


class _Row(frappe._dict):
    """Lightweight stand-in for a Landed Cost Item child row: supports the
    same .get()/.set() interface real Document rows expose, without needing
    a DB-backed doctype."""

    def set(self, key, value):
        self[key] = value


def _make_import_lcv(name, total_taxes_and_charges, custom_import_document="TEST-IMPORTDOC-0001"):
    lcv = CustomLandedCostVoucher({"doctype": "Landed Cost Voucher"})
    lcv.name = name
    lcv.custom_landed_cost_voucher_type = "Import"
    lcv.custom_import_document = custom_import_document
    lcv.distribute_charges_based_on = "Distribute Manually"
    lcv.total_taxes_and_charges = total_taxes_and_charges
    lcv.items = []
    lcv.validate_applicable_charges_for_item = MagicMock()
    return lcv


class TestLandedCostVoucherZeroCustomsDuty(unittest.TestCase):
    """
    Regression test for: LCV submit fails to generate ST/IT JV when Customs
    Duty is 0%. A 0%-CD shipment has total_taxes_and_charges == 0 (nothing to
    capitalize into stock), which must not block the ST/IT JV generation path.

    JV creation is also expected to run last inside on_submit's try block, so
    that if it fails, the whole submit fails/rolls back with it rather than
    leaving stock capitalized but taxes unposted.
    """

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.enqueue_import_doc_refresh")
    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.create_consolidated_import_taxes_jv")
    def test_zero_total_charges_submits_and_still_creates_jv(self, mock_create_jv, mock_enqueue_refresh):
        lcv = _make_import_lcv("TEST-LCV-ZERO-CD", total_taxes_and_charges=0)
        call_order = []
        lcv.update_landed_cost = MagicMock(side_effect=lambda: call_order.append("update_landed_cost"))
        mock_create_jv.side_effect = lambda name: call_order.append("create_jv")

        lcv.on_submit()

        lcv.validate_applicable_charges_for_item.assert_not_called()
        mock_create_jv.assert_called_once_with(lcv.name)
        lcv.update_landed_cost.assert_called_once()
        self.assertEqual(call_order, ["update_landed_cost", "create_jv"])
        mock_enqueue_refresh.assert_called_once_with(lcv.custom_import_document)

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.enqueue_import_doc_refresh")
    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.create_consolidated_import_taxes_jv")
    def test_nonzero_total_charges_still_validates_distribution(self, mock_create_jv, mock_enqueue_refresh):
        lcv = _make_import_lcv("TEST-LCV-NONZERO-CD", total_taxes_and_charges=15000)
        lcv.update_landed_cost = MagicMock()

        lcv.on_submit()

        lcv.validate_applicable_charges_for_item.assert_called_once()
        mock_create_jv.assert_called_once_with(lcv.name)
        lcv.update_landed_cost.assert_called_once()

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.enqueue_import_doc_refresh")
    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.create_consolidated_import_taxes_jv")
    def test_jv_failure_rolls_back_and_fails_the_whole_submit(self, mock_create_jv, mock_enqueue_refresh):
        lcv = _make_import_lcv("TEST-LCV-JV-FAILS", total_taxes_and_charges=0)
        lcv.update_landed_cost = MagicMock()
        mock_create_jv.side_effect = frappe.ValidationError("boom")

        with patch(
            "importmanager.importmanager.overrides.custom_landed_cost_voucher.frappe.db.rollback"
        ) as mock_rollback:
            with self.assertRaises(frappe.ValidationError):
                lcv.on_submit()
            mock_rollback.assert_called_once()

        # No refresh should be scheduled for a failed submit.
        mock_enqueue_refresh.assert_not_called()

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.enqueue_import_doc_refresh")
    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.create_consolidated_import_taxes_jv")
    def test_no_import_document_skips_refresh_scheduling(self, mock_create_jv, mock_enqueue_refresh):
        lcv = _make_import_lcv("TEST-LCV-NO-IMPORTDOC", total_taxes_and_charges=0, custom_import_document=None)
        lcv.update_landed_cost = MagicMock()

        lcv.on_submit()

        mock_enqueue_refresh.assert_not_called()


class TestLandedCostVoucherOnCancel(unittest.TestCase):
    """
    on_cancel must also schedule the ImportDoc refresh directly (this used to
    live in the now-removed doc_events on_cancel hook).
    """

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.enqueue_import_doc_refresh")
    def test_on_cancel_schedules_import_doc_refresh(self, mock_enqueue_refresh):
        lcv = _make_import_lcv("TEST-LCV-CANCEL", total_taxes_and_charges=0)
        lcv.update_landed_cost = MagicMock()
        lcv.cancel_all_linked_jvs = MagicMock()

        lcv.on_cancel()

        lcv.update_landed_cost.assert_called_once()
        lcv.cancel_all_linked_jvs.assert_called_once()
        mock_enqueue_refresh.assert_called_once_with(lcv.custom_import_document)


class TestImportDocRefreshScheduling(unittest.TestCase):
    """
    The ImportDoc refresh must run as a background job enqueued after commit —
    never synchronously in the request (a bare after_commit callback stalls
    the request for minutes on lock waits against the Repost Item Valuation
    worker, then fails). System-generated JVs must not trigger it: their
    parent flows already schedule a refresh, and the refresh job itself
    cancels/recreates JVs, so reacting to them would loop forever.
    """

    @patch("importmanager.import_utils.frappe.enqueue")
    def test_refresh_is_enqueued_as_deduplicated_background_job_after_commit(self, mock_enqueue):
        import_utils.enqueue_import_doc_refresh("TEST-IMPORTDOC-0001")

        mock_enqueue.assert_called_once()
        kwargs = mock_enqueue.call_args.kwargs
        self.assertTrue(kwargs["enqueue_after_commit"])
        self.assertTrue(kwargs["deduplicate"])
        self.assertEqual(kwargs["job_id"], "importdoc_refresh::TEST-IMPORTDOC-0001")
        self.assertEqual(kwargs["import_doc_name"], "TEST-IMPORTDOC-0001")

    @patch("importmanager.import_utils.enqueue_import_doc_refresh")
    def test_system_generated_jv_does_not_trigger_refresh(self, mock_enqueue_refresh):
        doc = frappe._dict(
            name="TEST-JV-SYSTEM",
            custom_import_document="TEST-IMPORTDOC-0001",
            is_system_generated=1,
        )

        import_utils.on_submit_journal_entry(doc, "on_submit")
        import_utils.on_cancel_journal_entry(doc, "on_cancel")

        mock_enqueue_refresh.assert_not_called()

    @patch("importmanager.import_utils.enqueue_import_doc_refresh")
    def test_manual_jv_triggers_refresh(self, mock_enqueue_refresh):
        doc = frappe._dict(
            name="TEST-JV-MANUAL",
            custom_import_document="TEST-IMPORTDOC-0001",
            is_system_generated=0,
        )

        import_utils.on_submit_journal_entry(doc, "on_submit")

        mock_enqueue_refresh.assert_called_once_with("TEST-IMPORTDOC-0001")


class TestConsolidatedImportTaxesJv(unittest.TestCase):
    """
    Regression test for the per-item ST/IT consolidation math. Uses the
    reproduction figures from the bug report (0% CD shipment, four items) and
    mocks all DB/document access so no fixtures (Company/Item/PI) are needed.
    """

    def _lcv_item(self, stamnt, it):
        return frappe._dict(
            custom_base_assessment_difference=0,
            custom_stamnt=stamnt,
            custom_ast=0,
            custom_it=it,
            custom_cd=0,
            custom_acd=0,
            custom_cess_amount=0,
        )

    @patch("importmanager.import_utils.frappe.log_error")
    @patch("importmanager.import_utils.create_journal_voucher")
    @patch("importmanager.import_utils.frappe.get_cached_doc")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_consolidated_jv_credits_pakistan_customs_for_st_and_it(
        self, mock_get_doc, mock_get_cached_doc, mock_create_jv, mock_log_error
    ):
        items = [
            self._lcv_item(1274524, 167104),
            self._lcv_item(1033729, 135533),
            self._lcv_item(1125185, 147524),
            self._lcv_item(2085804, 273473),
        ]

        lcv_doc = frappe._dict(
            company="Test Company",
            custom_import_document="TEST-IMPORTDOC-0001",
            posting_date="2026-01-01",
            items=items,
        )
        import_doc = frappe._dict(gd_no="TEST-GD-0001")

        def get_doc_side_effect(doctype, name):
            if doctype == "Landed Cost Voucher":
                return lcv_doc
            if doctype == "ImportDoc":
                return import_doc
            raise AssertionError(f"Unexpected frappe.get_doc call: {doctype}, {name}")

        mock_get_doc.side_effect = get_doc_side_effect
        mock_get_cached_doc.return_value = frappe._dict(
            custom_sales_tax_input_account="Sales Tax Input - TC",
            custom_advance_income_tax="Advance Income Tax - TC",
            custom_default_gov_payable_account="Pakistan Customs Payable - TC",
        )

        import_utils.create_consolidated_import_taxes_jv("TEST-LCV-0001")

        # No assessment variance in this shipment -> only the one consolidated JV.
        mock_create_jv.assert_called_once()
        call_args, call_kwargs = mock_create_jv.call_args
        title, posting_date, accounts = call_args
        self.assertIn("Consolidated Import Taxes", title)
        self.assertEqual(call_kwargs["import_document"], "TEST-IMPORTDOC-0001")

        by_account = {a["account"]: a for a in accounts}

        total_st = sum(i.custom_stamnt for i in items)
        total_it = sum(i.custom_it for i in items)

        self.assertEqual(total_st, 5519242)
        self.assertEqual(total_it, 723634)

        self.assertEqual(by_account["Sales Tax Input - TC"]["debit"], total_st)
        self.assertEqual(by_account["Advance Income Tax - TC"]["debit"], total_it)

        gov_payable = by_account["Pakistan Customs Payable - TC"]
        self.assertEqual(gov_payable["party_type"], "Government")
        self.assertEqual(gov_payable["party"], "Pakistan Customs")
        self.assertEqual(gov_payable["credit"], total_st + total_it)
        self.assertEqual(total_st + total_it, 6242876)


class TestLandedCostVoucherHooksRegistration(unittest.TestCase):
    """
    Guard against re-introducing a doc_events hook for Landed Cost Voucher.
    JV creation and the import-doc refresh now live entirely inside
    CustomLandedCostVoucher.on_submit()/on_cancel() so they share its
    rollback-on-failure semantics; a doc_events hook would run as a second,
    disconnected step and risks duplicating (or losing) that behaviour.
    """

    def test_no_doc_events_hook_registered_for_landed_cost_voucher(self):
        from importmanager import hooks

        self.assertNotIn("Landed Cost Voucher", hooks.doc_events)

    def test_legacy_hook_functions_removed(self):
        self.assertFalse(hasattr(import_utils, "on_submit_landed_cost_voucher"))
        self.assertFalse(hasattr(import_utils, "on_cancel_landed_cost_voucher"))


class TestEnsurePurchaseReceiptItemLinks(unittest.TestCase):
    """
    Regression test for: a "Regular" (or "Import") Landed Cost Voucher submits
    with no error, applicable_charges is computed and distributed correctly,
    but the linked Purchase Invoice's landed_cost_voucher_amount/valuation_rate
    never change and no GL Entry reflects the capitalized amount.

    Root cause: erpnext's set_landed_cost_voucher_amount() (called from
    update_landed_cost() on submit) only sums Landed Cost Item rows that carry
    a purchase_receipt_item (or stock_entry_item) link back to the exact
    source-document item row. Rows added without that link - typed in
    manually, or built via API/script instead of clicking "Get Items from
    Purchase Receipts" - still compute applicable_charges correctly (that math
    only uses amount/qty), so the voucher looks fully successful, but the
    capitalization step silently finds nothing to sum.

    ensure_purchase_receipt_item_links() (wired into validate_line_items(),
    which both the "Import" and "Regular" code paths call) backfills that link
    by matching item_code against the receipt document's own item rows, and
    throws instead of silently proceeding when the match isn't unique.
    """

    def setUp(self):
        # Build the (unsaved, in-memory) doc *without* frappe.get_all patched -
        # constructing/meta-loading a Document legitimately calls frappe.get_all
        # for permissions/DocType Link/etc., and patching it globally for the
        # whole test would corrupt those unrelated calls too.
        self.lcv = CustomLandedCostVoucher({"doctype": "Landed Cost Voucher"})
        self.lcv.custom_landed_cost_voucher_type = "Regular"

    def _get_all_patch(self):
        return patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.frappe.get_all")

    def test_backfills_missing_link_on_unique_match(self):
        self.lcv.items = [
            _Row(
                idx=1,
                item_code="ITEM-A",
                receipt_document_type="Purchase Invoice",
                receipt_document="PI-0001",
                purchase_receipt_item=None,
            )
        ]

        with self._get_all_patch() as mock_get_all:
            mock_get_all.return_value = ["pi-item-row-1"]
            self.lcv.ensure_purchase_receipt_item_links()

            mock_get_all.assert_called_once_with(
                "Purchase Invoice Item",
                filters={"parent": "PI-0001", "item_code": "ITEM-A"},
                pluck="name",
            )
        self.assertEqual(self.lcv.items[0].purchase_receipt_item, "pi-item-row-1")

    def test_leaves_already_linked_rows_untouched(self):
        self.lcv.items = [
            _Row(
                idx=1,
                item_code="ITEM-A",
                receipt_document_type="Purchase Invoice",
                receipt_document="PI-0001",
                purchase_receipt_item="already-linked-row",
            )
        ]

        with self._get_all_patch() as mock_get_all:
            self.lcv.ensure_purchase_receipt_item_links()
            mock_get_all.assert_not_called()

        self.assertEqual(self.lcv.items[0].purchase_receipt_item, "already-linked-row")

    def test_throws_when_item_not_found_in_receipt_document(self):
        self.lcv.items = [
            _Row(
                idx=1,
                item_code="NOT-ON-THE-PI",
                receipt_document_type="Purchase Invoice",
                receipt_document="PI-0001",
                purchase_receipt_item=None,
            )
        ]

        with self._get_all_patch() as mock_get_all:
            mock_get_all.return_value = []
            with self.assertRaises(frappe.ValidationError):
                self.lcv.ensure_purchase_receipt_item_links()

    def test_throws_when_item_code_ambiguous(self):
        self.lcv.items = [
            _Row(
                idx=1,
                item_code="ITEM-A",
                receipt_document_type="Purchase Invoice",
                receipt_document="PI-0001",
                purchase_receipt_item=None,
            )
        ]

        with self._get_all_patch() as mock_get_all:
            mock_get_all.return_value = ["row-1", "row-2"]
            with self.assertRaises(frappe.ValidationError):
                self.lcv.ensure_purchase_receipt_item_links()

    def test_stock_entry_rows_use_stock_entry_item_field(self):
        self.lcv.items = [
            _Row(
                idx=1,
                item_code="ITEM-A",
                receipt_document_type="Stock Entry",
                receipt_document="STE-0001",
                stock_entry_item=None,
                purchase_receipt_item=None,
            )
        ]

        with self._get_all_patch() as mock_get_all:
            mock_get_all.return_value = ["se-detail-row"]
            self.lcv.ensure_purchase_receipt_item_links()

            mock_get_all.assert_called_once_with(
                "Stock Entry Detail",
                filters={"parent": "STE-0001", "item_code": "ITEM-A"},
                pluck="name",
            )
        self.assertEqual(self.lcv.items[0].stock_entry_item, "se-detail-row")

    def test_validate_line_items_backfills_links_before_core_validation(self):
        self.lcv.ensure_purchase_receipt_item_links = MagicMock()

        with patch.object(LandedCostVoucher, "validate_line_items") as mock_super_validate:
            self.lcv.validate_line_items()

        self.lcv.ensure_purchase_receipt_item_links.assert_called_once()
        mock_super_validate.assert_called_once()


class TestCalculateImportAssessmentNoMidLoopCommit(unittest.TestCase):
    """
    Regression test for: calculate_import_assessment() used to call
    frappe.db.commit() between calculate_assessed_value(item) and
    calculate_import_taxes(item) inside its per-item loop. This function
    runs from on_update(), which fires before on_submit()'s own
    try/except frappe.db.rollback() boundary - so that commit made
    docstatus=1 (and item tax fields) durable ahead of time, and a genuine
    downstream JV failure could no longer roll them back.
    """

    @patch("importmanager.import_utils.calculate_import_taxes")
    @patch("importmanager.import_utils.calculate_assessed_value")
    @patch("importmanager.import_utils.frappe.db.commit")
    def test_does_not_commit_between_items(self, mock_commit, mock_assessed_value, mock_import_taxes):
        # frappe._dict can't hold an "items" key accessed via dot notation -
        # dict.items (the builtin method) always shadows it - so use a plain
        # namespace instead.
        lcv_doc = SimpleNamespace(items=[frappe._dict(name="item-1"), frappe._dict(name="item-2")])

        import_utils.calculate_import_assessment(lcv_doc)

        mock_commit.assert_not_called()
        self.assertEqual(mock_assessed_value.call_count, 2)
        self.assertEqual(mock_import_taxes.call_count, 2)


class TestImportAssessmentDoesNotPartiallyCommitDocstatus(unittest.TestCase):
    """
    Integration regression test for the same defect, reproducing the actual
    db_update() -> on_update() -> on_submit() sequence with real (initially
    uncommitted) DB writes: Document._save() runs db_update() - which writes
    docstatus=1 to the DB - *before* run_post_save_methods() calls
    on_update() and then on_submit() (frappe/model/document.py). If
    calculate_import_assessment() (called from on_update()) ever
    re-introduces a mid-loop frappe.db.commit(), that earlier docstatus=1
    write becomes durable right there, and on_submit()'s own
    "except: frappe.db.rollback(); raise" (custom_landed_cost_voucher.py) can
    no longer undo it when a downstream step (e.g. JV creation failing for a
    missing Government Party Type / Company account) genuinely fails -
    leaving a voucher that looks submitted with no corresponding JV.
    """

    def setUp(self):
        self.lcv = frappe.get_doc(
            {
                "doctype": "Landed Cost Voucher",
                "naming_series": "MAT-LCV-.YYYY.-",
                "custom_landed_cost_voucher_type": "Import",
                "distribute_charges_based_on": "Distribute Manually",
                "docstatus": 0,
            }
        )
        self.lcv.db_insert()

        self.item = frappe.get_doc(
            {
                "doctype": "Landed Cost Item",
                "parent": self.lcv.name,
                "parentfield": "items",
                "parenttype": "Landed Cost Voucher",
                "idx": 1,
                # Points at a document that doesn't exist: calculate_assessed_value
                # swallows the resulting DoesNotExistError itself (broad
                # try/except + frappe.log_error) and writes nothing, so this
                # fixture only ever exercises the commit-boundary behaviour
                # under test, never the real assessment math.
                "receipt_document_type": "Purchase Receipt",
                "receipt_document": "NON-EXISTENT-PR-FOR-TEST",
            }
        )
        self.item.db_insert()

    def tearDown(self):
        # If a mid-loop commit regresses, the rows below were durably
        # committed by the code under test and must be cleaned up for real;
        # if not, this delete+commit is a no-op against an already-rolled-back
        # transaction.
        frappe.db.sql("delete from `tabLanded Cost Item` where name=%s", self.item.name)
        frappe.db.sql("delete from `tabLanded Cost Voucher` where name=%s", self.lcv.name)
        frappe.db.commit()

    @patch("importmanager.import_utils.calculate_import_taxes")
    def test_failed_downstream_jv_rolls_back_docstatus(self, mock_import_taxes):
        # Simulate db_update() having just written docstatus=1 to the DB
        # (uncommitted) as part of submit(), before on_update()/on_submit() run.
        frappe.db.set_value("Landed Cost Voucher", self.lcv.name, "docstatus", 1, update_modified=False)

        lcv_doc = frappe.get_doc("Landed Cost Voucher", self.lcv.name)
        import_utils.calculate_import_assessment(lcv_doc)

        # Simulate on_submit()'s own try/except: a genuine downstream failure
        # (e.g. missing Government Party Type / Company account config) during
        # create_consolidated_import_taxes_jv rolls back and re-raises.
        with self.assertRaises(frappe.ValidationError):
            try:
                raise frappe.ValidationError("Simulated: missing Government Party Type")
            except Exception:
                frappe.db.rollback()
                raise

        persisted_docstatus = frappe.db.get_value("Landed Cost Voucher", self.lcv.name, "docstatus")
        self.assertNotEqual(
            persisted_docstatus,
            1,
            "docstatus=1 survived the rollback: calculate_import_assessment() must have "
            "committed mid-loop, making the earlier docstatus write durable before "
            "on_submit()'s failure could roll it back.",
        )


if __name__ == "__main__":
    unittest.main()
