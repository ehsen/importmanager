import unittest
from unittest.mock import MagicMock, patch

import frappe

from importmanager.importmanager.overrides.custom_landed_cost_voucher import CustomLandedCostVoucher
from importmanager import import_utils


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


if __name__ == "__main__":
    unittest.main()
