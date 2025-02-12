import frappe
import unittest
from importmanager.controllers.charge_allocation_controller import create_charge_allocation_entry

class TestChargeAllocationController(unittest.TestCase):

    def setUp(self):
        # Create a test ImportDoc document
        self.import_doc = frappe.get_doc({
            "doctype": "ImportDoc",
            "name": "Test ImportDoc",
            "items": [
                {
                    "item_code": "Test Item",
                    "qty": 10,
                    "allocated_charges_ex_cd": 100,
                    "purchase_receipt_item": "Test Purchase Receipt Item"
                }
            ]
        })
        self.import_doc.insert()

        # Create a linked Purchase Receipt Item
        self.purchase_receipt_item = frappe.get_doc({
            "doctype": "Purchase Receipt Item",
            "item_code": "Test Item",
            "purchase_receipt": "Test Purchase Receipt",
            "qty": 10
        }).insert()

        # Create a linked Landed Cost Item
        self.landed_cost_item = frappe.get_doc({
            "doctype": "Landed Cost Item",
            "purchase_receipt_item": self.purchase_receipt_item.name,
            "custom_base_assessment_difference": 50
        }).insert()

    def test_create_charge_allocation_entry_correct_allocation(self):
        # Test for correct allocation amount charged against qty
        create_charge_allocation_entry(
            entry_type="Addition",
            charge_type="Import Charges",
            item_code="Test Item",
            qty=10,
            charges=100,
            reference_doc="ImportDoc",
            reference_doc_name=self.import_doc.name
        )

        # Verify that the charge allocation entry was created
        allocation_entries = frappe.get_all(
            "Charge Allocation Ledger",
            filters={"reference_doc_name": self.import_doc.name},
            fields=["name", "charges", "qty"]
        )

        self.assertEqual(len(allocation_entries), 1, "No allocation entry was created.")
        self.assertEqual(allocation_entries[0]["charges"], 100, "Allocated charges do not match.")
        self.assertEqual(allocation_entries[0]["qty"], 10, "Allocated quantity does not match.")

    def test_create_charge_allocation_entry_multiple_sources(self):
        # Create multiple addition entries to simulate multiple sources
        create_charge_allocation_entry(
            entry_type="Addition",
            charge_type="Import Charges",
            item_code="Test Item",
            qty=10,
            charges=100,
            reference_doc="ImportDoc",
            reference_doc_name=self.import_doc.name
        )

        create_charge_allocation_entry(
            entry_type="Addition",
            charge_type="Import Charges",
            item_code="Test Item",
            qty=5,
            charges=50,
            reference_doc="ImportDoc",
            reference_doc_name=self.import_doc.name
        )

        # Now create an allocation entry that uses the above additions
        create_charge_allocation_entry(
            entry_type="Allocation",
            charge_type="Import Charges",
            item_code="Test Item",
            qty=8,
            charges=80,  # This should be allocated from the two addition entries
            reference_doc="ImportDoc",
            reference_doc_name=self.import_doc.name
        )

        # Verify that the allocation entry was created
        allocation_entries = frappe.get_all(
            "Charge Allocation Ledger",
            filters={"reference_doc_name": self.import_doc.name, "entry_type": "Allocation"},
            fields=["name", "charges", "qty"]
        )

        self.assertEqual(len(allocation_entries), 1, "No allocation entry was created.")
        self.assertEqual(allocation_entries[0]["charges"], 80, "Allocated charges do not match.")
        self.assertEqual(allocation_entries[0]["qty"], 8, "Allocated quantity does not match.")

    def tearDown(self):
        # Clean up test data
        frappe.delete_doc("ImportDoc", self.import_doc.name)
        frappe.delete_doc("Purchase Receipt Item", self.purchase_receipt_item.name)
        frappe.delete_doc("Landed Cost Item", self.landed_cost_item.name)

if __name__ == "__main__":
    unittest.main()