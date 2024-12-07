# Copyright (c) 2024, SpotLedger and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ImportDoc(Document):
	pass


	def fetch_linked_invoices(self):
		pi_list = frappe.get_list("Purchase Invoice",fields=['name',"rounded_total","base_rounded_total"],
							filters={'custom_import_document':self.name,'docstatus':1,"custom_purchase_invoice_type":"Import"})
		self.linked_purchase_invoices = [] 
		for item in pi_list:
			self.append("linked_purchase_invoices",{
				"purchase_invoice":item['name'],
				"total_value":item['rounded_total'],
				"total_base_value":item['base_rounded_total']


			})
	
	def fetch_linked_service_invoices(self):
		pi_list = frappe.get_list("Purchase Invoice",fields=['name'],
							filters={'custom_import_document':self.name,'docstatus':1,
				"custom_purchase_invoice_type":"Import Service Charges"},pluck='name')
		self.linked_import_charges = [] 
		for item in pi_list:
			pi_doc = frappe.get_cached_doc("Purchase Invoice",item)
			for pi_row in pi_doc.get("items"):
				self.append("linked_import_charges",{
					"document_type":"Purchase Invoice",
					"document_name":pi_doc.name,
					"charge_item":pi_row.item_name,
					"paid_to":pi_doc.supplier,
					"amount":pi_doc.rounded_total


				})
			
		


	def update_import_doc(self):
		"""
		This function will fetch all linked documents related to this import doc, 
		"""
		pass
