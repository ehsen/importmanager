"""
Tests for import_utils.py docstatus kwarg fix and excluded misc charge types.

Tests cover:
1. Docstatus kwarg bug (regression)
2. Excluded misc charge types filtering:
   - LC Margin, LC Retirement, Wire Transfer should not be appended
   - Non-excluded types should still be appended
   - Totals should exclude these types defensively
"""

import frappe
import unittest
from unittest.mock import patch, MagicMock
import ast
import inspect


class TestImportUtilsDocstatusKwargDynamic(unittest.TestCase):
    """Dynamic tests that mock frappe.get_list and verify the calls."""

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_update_cash_payment_vouchers_no_docstatus_kwarg(self, mock_get_doc, mock_get_list):
        """
        Test that update_cash_payment_vouchers does not pass docstatus as a kwarg to frappe.get_list.
        """
        from importmanager.import_utils import update_cash_payment_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Mock get_list to return empty list
        mock_get_list.return_value = []

        # Mock get_doc to return the mock import doc
        mock_get_doc.return_value = mock_import_doc

        # Call the function
        update_cash_payment_vouchers("TEST-IMPORT-001")

        # Verify frappe.get_list was called exactly once
        self.assertEqual(mock_get_list.call_count, 1)

        # Get the call arguments
        call_args = mock_get_list.call_args

        # Verify that 'docstatus' is NOT in the kwargs
        self.assertNotIn("docstatus", call_args.kwargs,
            "docstatus should not be passed as a kwarg to frappe.get_list in update_cash_payment_vouchers")

        # Verify that docstatus IS in the filters dict (the correct place)
        call_kwargs = call_args[1]
        self.assertIn("filters", call_kwargs)
        self.assertIn("docstatus", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["docstatus"], 1)

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_update_bank_receipt_vouchers_no_docstatus_kwarg(self, mock_get_doc, mock_get_list):
        """
        Test that update_bank_receipt_vouchers does not pass docstatus as a kwarg to frappe.get_list.
        """
        from importmanager.import_utils import update_bank_receipt_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Mock get_list to return empty list
        mock_get_list.return_value = []

        # Mock get_doc to return the mock import doc
        mock_get_doc.return_value = mock_import_doc

        # Call the function
        update_bank_receipt_vouchers("TEST-IMPORT-001")

        # Verify frappe.get_list was called exactly once
        self.assertEqual(mock_get_list.call_count, 1)

        # Get the call arguments
        call_args = mock_get_list.call_args

        # Verify that 'docstatus' is NOT in the kwargs
        self.assertNotIn("docstatus", call_args.kwargs,
            "docstatus should not be passed as a kwarg to frappe.get_list in update_bank_receipt_vouchers")

        # Verify that docstatus IS in the filters dict (the correct place)
        call_kwargs = call_args[1]
        self.assertIn("filters", call_kwargs)
        self.assertIn("docstatus", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["docstatus"], 1)

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_update_bank_payment_vouchers_no_stray_kwarg(self, mock_get_doc, mock_get_list):
        """
        Test that update_bank_payment_vouchers does not have stray kwargs.
        """
        from importmanager.import_utils import update_bank_payment_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Mock get_list to return empty list
        mock_get_list.return_value = []

        # Mock get_doc to return the mock import doc
        mock_get_doc.return_value = mock_import_doc

        # Call the function
        update_bank_payment_vouchers("TEST-IMPORT-001")

        # Verify frappe.get_list was called exactly once
        self.assertEqual(mock_get_list.call_count, 1)

        # Get the call arguments
        call_args = mock_get_list.call_args

        # Verify that no unexpected kwargs are passed
        # Valid kwargs: filters, fields, ignore_permissions, or_filters, group_by, order_by, limit, etc.
        valid_kwargs = {
            "filters", "fields", "ignore_permissions", "or_filters",
            "group_by", "order_by", "limit", "offset", "as_list",
            "pluck", "distinct", "count", "with_comment_count"
        }

        call_kwargs = call_args[1]
        for key in call_kwargs:
            self.assertIn(key, valid_kwargs,
                f"Unexpected kwarg '{key}' passed to frappe.get_list in update_bank_payment_vouchers")


class TestExcludedMiscChargeTypes(unittest.TestCase):
    """Tests for excluded misc import charge types (LC Margin, LC Retirement, Wire Transfer)."""

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_excluded_lc_margin_not_appended_in_cpv(self, mock_get_doc, mock_get_list):
        """Test that 'LC Margin' is skipped when processing Cash Payment Vouchers."""
        from importmanager.import_utils import update_cash_payment_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Create a mock CPV with LC Margin type
        mock_cpv = MagicMock()
        mock_cpv.__getitem__ = lambda self, key: "CPV-001" if key == "name" else None

        mock_cpv_doc = MagicMock()
        mock_cpv_doc.import_charge_type = "LC Margin"
        mock_cpv_doc.total_payment = 1000

        # Mock get_list to return the CPV
        mock_get_list.return_value = [mock_cpv]

        # Mock get_doc to return the appropriate doc
        def get_doc_side_effect(doctype, name, **kwargs):
            if doctype == "ImportDoc":
                return mock_import_doc
            elif doctype == "Cash Payment Voucher":
                return mock_cpv_doc
            return None

        mock_get_doc.side_effect = get_doc_side_effect

        # Call the function
        update_cash_payment_vouchers("TEST-IMPORT-001")

        # Verify that append was NOT called for the excluded type
        mock_import_doc.append.assert_not_called()
        # Verify save was still called
        mock_import_doc.save.assert_called_once()

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_excluded_wire_transfer_not_appended_in_bpv(self, mock_get_doc, mock_get_list):
        """Test that 'Wire Transfer' is skipped when processing Bank Payment Vouchers."""
        from importmanager.import_utils import update_bank_payment_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Create a mock BPV with Wire Transfer type
        mock_bpv = MagicMock()
        mock_bpv.__getitem__ = lambda self, key: "BPV-001" if key == "name" else None

        mock_bpv_doc = MagicMock()
        mock_bpv_doc.import_charge_type = "Wire Transfer"
        mock_bpv_doc.total_payment = 500

        # Mock get_list to return the BPV
        mock_get_list.return_value = [mock_bpv]

        # Mock get_doc to return the appropriate doc
        def get_doc_side_effect(doctype, name, **kwargs):
            if doctype == "ImportDoc":
                return mock_import_doc
            elif doctype == "Bank Payment Voucher":
                return mock_bpv_doc
            return None

        mock_get_doc.side_effect = get_doc_side_effect

        # Call the function
        update_bank_payment_vouchers("TEST-IMPORT-001")

        # Verify that append was NOT called for the excluded type
        mock_import_doc.append.assert_not_called()
        # Verify save was still called
        mock_import_doc.save.assert_called_once()

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_excluded_lc_retirement_not_appended_in_brv(self, mock_get_doc, mock_get_list):
        """Test that 'LC Retirement' is skipped when processing Bank Receipt Vouchers."""
        from importmanager.import_utils import update_bank_receipt_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Create a mock BRV with LC Retirement type
        mock_brv = MagicMock()
        mock_brv.__getitem__ = lambda self, key: "BRV-001" if key == "name" else None

        mock_brv_doc = MagicMock()
        mock_brv_doc.import_charge_type = "LC Retirement"
        mock_brv_doc.total_payment = 2000

        # Mock get_list to return the BRV
        mock_get_list.return_value = [mock_brv]

        # Mock get_doc to return the appropriate doc
        def get_doc_side_effect(doctype, name, **kwargs):
            if doctype == "ImportDoc":
                return mock_import_doc
            elif doctype == "Bank Receipt Voucher":
                return mock_brv_doc
            return None

        mock_get_doc.side_effect = get_doc_side_effect

        # Call the function
        update_bank_receipt_vouchers("TEST-IMPORT-001")

        # Verify that append was NOT called for the excluded type
        mock_import_doc.append.assert_not_called()
        # Verify save was still called
        mock_import_doc.save.assert_called_once()

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_non_excluded_type_still_appended(self, mock_get_doc, mock_get_list):
        """Test that non-excluded types are still appended (e.g., 'Customs Duty')."""
        from importmanager.import_utils import update_cash_payment_vouchers

        # Create a mock import doc
        mock_import_doc = MagicMock()
        mock_import_doc.append = MagicMock()
        mock_import_doc.save = MagicMock()

        # Create a mock CPV with non-excluded type
        mock_cpv = MagicMock()
        mock_cpv.__getitem__ = lambda self, key: "CPV-002" if key == "name" else None

        mock_cpv_doc = MagicMock()
        mock_cpv_doc.import_charge_type = "Customs Duty"
        mock_cpv_doc.total_payment = 5000
        mock_cpv_doc.paid_to = "Pakistan Customs"

        # Mock get_list to return the CPV
        mock_get_list.return_value = [mock_cpv]

        # Mock get_doc to return the appropriate doc
        def get_doc_side_effect(doctype, name, **kwargs):
            if doctype == "ImportDoc":
                return mock_import_doc
            elif doctype == "Cash Payment Voucher":
                return mock_cpv_doc
            return None

        mock_get_doc.side_effect = get_doc_side_effect

        # Call the function
        update_cash_payment_vouchers("TEST-IMPORT-001")

        # Verify that append WAS called for the non-excluded type
        mock_import_doc.append.assert_called_once()
        call_args = mock_import_doc.append.call_args
        self.assertEqual(call_args[0][0], "linked_misc_import_charges")
        # Verify save was called
        mock_import_doc.save.assert_called_once()

    def test_calculate_total_import_charges_excludes_types(self):
        """Test that calculate_total_import_charges excludes the specified types from totals."""
        from importmanager.import_utils import EXCLUDED_MISC_CHARGE_TYPES, calculate_total_import_charges

        # Create a mock import doc with mixed charge types
        mock_import_doc = MagicMock()

        # Create mock rows for linked_misc_import_charges
        row1 = MagicMock()
        row1.import_charge_type = "Customs Duty"
        row1.amount = 1000

        row2 = MagicMock()
        row2.import_charge_type = "LC Margin"  # Excluded
        row2.amount = 500

        row3 = MagicMock()
        row3.import_charge_type = "Cess"
        row3.amount = 200

        row4 = MagicMock()
        row4.import_charge_type = "Wire Transfer"  # Excluded
        row4.amount = 300

        mock_import_doc.linked_misc_import_charges = [row1, row2, row3, row4]
        mock_import_doc.linked_import_charges = []
        mock_import_doc.linked_purchase_invoices = []

        with patch("importmanager.import_utils.frappe.get_doc", return_value=mock_import_doc):
            # Call the function
            calculate_total_import_charges("TEST-IMPORT-001")

            # Verify that the total only includes non-excluded types
            # Customs Duty (1000) + Cess (200) = 1200 (excluding LC Margin and Wire Transfer)
            expected_total = 1000 + 200  # Excluding 500 + 300
            self.assertEqual(mock_import_doc.total_import_charges, expected_total)


class TestImportUtilsDocstatusKwargStatic(unittest.TestCase):
    """Static analysis test that parses import_utils.py and checks for docstatus kwargs."""

    def test_no_docstatus_kwarg_in_get_list_calls(self):
        """
        Parse import_utils.py and verify that no get_list or get_all calls
        have a 'docstatus' keyword argument.
        """
        # Import the module to get its file path
        from importmanager import import_utils
        import_utils_path = inspect.getfile(import_utils)

        # Parse the source code
        with open(import_utils_path, 'r') as f:
            source_code = f.read()

        tree = ast.parse(source_code)

        # Find all Call nodes
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is a frappe.get_list or frappe.get_all call
                is_get_list_call = False
                is_get_all_call = False

                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name) and
                        node.func.value.id == "frappe" and
                        node.func.attr in ("get_list", "get_all")):
                        is_get_list_call = node.func.attr == "get_list"
                        is_get_all_call = node.func.attr == "get_all"

                if is_get_list_call or is_get_all_call:
                    # Check if this call has a 'docstatus' keyword argument
                    for keyword in node.keywords:
                        if keyword.arg == "docstatus":
                            func_name = "frappe.get_list" if is_get_list_call else "frappe.get_all"
                            issues.append(
                                f"Line {node.lineno}: {func_name} call has 'docstatus' as a keyword argument"
                            )

        # Assert no issues found
        self.assertEqual(len(issues), 0,
            f"Found {len(issues)} issue(s) with docstatus kwarg:\n" + "\n".join(issues))


if __name__ == "__main__":
    unittest.main()
