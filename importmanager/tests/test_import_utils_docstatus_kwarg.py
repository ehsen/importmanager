"""
Regression tests for the docstatus kwarg bug in import_utils.py.

The bug: frappe.get_list() was being called with a stray `docstatus=1` kwarg
in update_cash_payment_vouchers() and update_bank_receipt_vouchers().
This raised TypeError in Frappe v16+ because DatabaseQuery.execute() has no **kwargs.
The docstatus=1 was already in the filters dict, so the kwarg was redundant.

Tests:
1. Dynamic test: mock frappe.get_list and verify update functions don't pass docstatus as kwarg
2. Static test: parse import_utils.py with ast and verify no get_list/get_all calls have docstatus keyword
"""

import frappe
import unittest
from unittest.mock import patch, MagicMock
import ast
import inspect


class TestImportUtilsDocstatusKwargDynamic(unittest.TestCase):
    """Dynamic tests that mock frappe.get_list and verify the calls."""

    def setUp(self):
        """Create a test ImportDoc."""
        self.import_doc = frappe.get_doc({
            "doctype": "ImportDoc",
            "name": "TEST-IMPORT-001",
            "company": "Test Company",
        })
        try:
            self.import_doc.insert()
        except Exception:
            pass  # May already exist in test DB

    def tearDown(self):
        """Clean up test ImportDoc if it exists."""
        try:
            frappe.delete_doc("ImportDoc", "TEST-IMPORT-001", force=True)
        except Exception:
            pass

    @patch("importmanager.import_utils.frappe.get_list")
    @patch("importmanager.import_utils.frappe.get_doc")
    def test_update_cash_payment_vouchers_no_docstatus_kwarg(self, mock_get_doc, mock_get_list):
        """
        Test that update_cash_payment_vouchers does not pass docstatus as a kwarg to frappe.get_list.
        """
        from importmanager.import_utils import update_cash_payment_vouchers

        # Mock get_list to return empty list
        mock_get_list.return_value = []

        # Mock get_doc to return the import doc
        mock_get_doc.return_value = self.import_doc

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
        call_args_positional = call_args[0]
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

        # Mock get_list to return empty list
        mock_get_list.return_value = []

        # Mock get_doc to return the import doc
        mock_get_doc.return_value = self.import_doc

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
        call_args_positional = call_args[0]
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

        # Mock get_list to return empty list
        mock_get_list.return_value = []

        # Mock get_doc to return the import doc
        mock_get_doc.return_value = self.import_doc

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
