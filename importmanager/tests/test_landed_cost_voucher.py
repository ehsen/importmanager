import unittest
from unittest.mock import MagicMock, patch

import frappe

from importmanager.importmanager.overrides.custom_landed_cost_voucher import CustomLandedCostVoucher
from importmanager import import_utils


def _make_import_lcv(name, total_taxes_and_charges):
    lcv = CustomLandedCostVoucher({"doctype": "Landed Cost Voucher"})
    lcv.name = name
    lcv.custom_landed_cost_voucher_type = "Import"
    lcv.distribute_charges_based_on = "Distribute Manually"
    lcv.total_taxes_and_charges = total_taxes_and_charges
    lcv.items = []
    lcv.validate_applicable_charges_for_item = MagicMock()
    lcv.update_landed_cost = MagicMock()
    return lcv


class TestLandedCostVoucherZeroCustomsDuty(unittest.TestCase):
    """
    Regression test for: LCV submit fails to generate ST/IT JV when Customs
    Duty is 0%. A 0%-CD shipment has total_taxes_and_charges == 0 (nothing to
    capitalize into stock), which must not block the ST/IT JV generation path.
    """

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.create_consolidated_import_taxes_jv")
    def test_zero_total_charges_submits_and_still_creates_jv(self, mock_create_jv):
        lcv = _make_import_lcv("TEST-LCV-ZERO-CD", total_taxes_and_charges=0)

        lcv.on_submit()

        lcv.validate_applicable_charges_for_item.assert_not_called()
        mock_create_jv.assert_called_once_with(lcv.name)
        lcv.update_landed_cost.assert_called_once()

    @patch("importmanager.importmanager.overrides.custom_landed_cost_voucher.create_consolidated_import_taxes_jv")
    def test_nonzero_total_charges_still_validates_distribution(self, mock_create_jv):
        lcv = _make_import_lcv("TEST-LCV-NONZERO-CD", total_taxes_and_charges=15000)

        lcv.on_submit()

        lcv.validate_applicable_charges_for_item.assert_called_once()
        mock_create_jv.assert_called_once_with(lcv.name)
        lcv.update_landed_cost.assert_called_once()


class TestConsolidatedImportTaxesJv(unittest.TestCase):
    """
    Regression test for the per-item ST/IT consolidation math and the JV
    hook wiring. Uses the reproduction figures from the bug report (0% CD
    shipment, four items) and mocks all DB/document access so no fixtures
    (Company/Item/PI) are required.
    """

    def _lcv_item(self, stamnt, it):
        item = frappe._dict(
            custom_base_assessment_difference=0,
            custom_stamnt=stamnt,
            custom_ast=0,
            custom_it=it,
            custom_cd=0,
            custom_acd=0,
            custom_cess_amount=0,
        )
        return item

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


class TestOnSubmitLandedCostVoucherHook(unittest.TestCase):
    """
    Regression test to guard against re-introducing a duplicate/mis-argumented
    call to create_consolidated_import_taxes_jv from the doc_events on_submit
    hook - the LCV controller's own on_submit already creates the JV using the
    LCV's name, so the hook must not create a second one.
    """

    @patch("importmanager.import_utils.create_consolidated_import_taxes_jv")
    @patch("importmanager.import_utils.frappe.db.after_commit")
    def test_hook_does_not_create_a_second_jv(self, mock_after_commit, mock_create_jv):
        doc = frappe._dict(
            name="TEST-LCV-0001",
            custom_import_document="TEST-IMPORTDOC-0001",
            custom_landed_cost_voucher_type="Import",
        )

        import_utils.on_submit_landed_cost_voucher(doc, "on_submit")

        mock_create_jv.assert_not_called()
        mock_after_commit.add.assert_called_once()


if __name__ == "__main__":
    unittest.main()
