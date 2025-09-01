# Copyright (c) 2024, SpotLedger and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from importmanager.import_utils import update_data_in_import_doc
from importmanager.importmanager.controllers.charge_allocation_controller import create_charge_allocation_entry
from erpnext.accounts.utils import get_fiscal_year

class ImportDoc(Document):
	
	def autoname(self):
		if self.linked_purchase_order:
			from datetime import datetime
			#current_year = datetime.now().strftime('%y')  # Gets current year as 2-digit number (e.g., '24' for 2024)
			try:
				fiscal_year = get_fiscal_year(self.date, company=self.company)[0]
			except Exception:
				frappe.throw("This date doesnt fall in any fiscal year list")
			
			# Handle PO naming for both regular and cancelled POs
			po_parts = self.linked_purchase_order.split("-")
			
			# Check if this is a cancelled PO (has more than 4 parts or ends with a single digit)
			if len(po_parts) > 4 or (len(po_parts) == 4 and po_parts[-1].isdigit() and len(po_parts[-1]) == 1):
				# For cancelled POs like "ACQ-IPO-26-0002-1", use "0002-1"
				# Get the last two parts and join them
				po_number = "-".join(po_parts[-2:])
			else:
				# For regular POs like "ACQ-IPO-25-0018", use just the last part "0018"
				po_number = po_parts[-1]
			
			abbr = frappe.get_cached_doc("Company",self.company).abbr
			# Create the import doc name with proper format including current year
			self.name = f"{abbr}-IMD-{fiscal_year}-{po_number}"
		else:
			frappe.throw("Please select a Linked Purchase Order")

	

	def create_import_charge_allocations(self):
		"""
		Create charge allocation entries for all items in the ImportDoc
		"""
		try:
			for item in self.items:
				# Create Import Charges allocation entry
				if item.allocated_charges_ex_cd > 0:
					create_charge_allocation_entry(
						entry_type="Addition",
						charge_type="Import Charges",
						item_code=item.item_code,
						qty=item.qty,
						charges=item.allocated_charges_ex_cd,
						reference_doc="ImportDoc",
						reference_doc_name=self.name
					)
				
				# Create Assessment Variance allocation entry
				if item.assessment_variance > 0:
					create_charge_allocation_entry(
						entry_type="Addition",
						charge_type="Assessment Variance",
						item_code=item.item_code,
						qty=item.qty,
						charges=item.assessment_variance,
						reference_doc="ImportDoc",
						reference_doc_name=self.name
					)
		except Exception as e:
			frappe.log_error(f"Error creating charge allocations: {str(e)}", "Import Charge Allocation Error")
			frappe.throw(f"Failed to create charge allocations: {str(e)}")

	def on_submit(self):
		"""
		Override standard submit behavior to:
		1. Create charge allocation entries
		2. Set status to 'Locked' instead of actually submitting
		"""
		try:
			# Create charge allocations
			self.create_import_charge_allocations()
			
			# Set status to Locked
			self.status = "Locked"
			self.docstatus = 0  # Keep as draft
			self.save()
			
			frappe.msgprint("Import Document has been locked and charges have been allocated.")
			
		except Exception as e:
			frappe.log_error(f"Error in ImportDoc submission: {str(e)}", "ImportDoc Submit Error")
			frappe.throw(f"Failed to process ImportDoc: {str(e)}")

	def on_cancel(self):
		"""
		Prevent cancellation if status is Locked
		"""
		if self.status == "Locked":
			frappe.throw("Cannot cancel a Locked Import Document")
	
	
@frappe.whitelist()
def lock_and_allocate_charges(doc_name):
	"""
	Lock the ImportDoc and create charge allocation entries
	"""
	doc = frappe.get_doc("ImportDoc", doc_name)
	
	try:
		# Create charge allocation entries
		doc.create_import_charge_allocations()
		
		# Update status to Locked
		doc.status = "Locked"
		doc.save()
		
		frappe.db.commit()
		return True
		
	except Exception as e:
		frappe.log_error(f"Error in locking ImportDoc: {str(e)}", "ImportDoc Lock Error")
		frappe.throw(f"Failed to lock document: {str(e)}")