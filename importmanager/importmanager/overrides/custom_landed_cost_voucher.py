# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.query_builder.custom import ConstantColumn
from frappe.utils import flt,datetime
from importmanager.import_utils import calculate_import_assessment,create_import_taxes_jv,create_consolidated_import_taxes_jv,enqueue_import_doc_refresh

import erpnext
from erpnext.controllers.taxes_and_totals import init_landed_taxes_and_totals
from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
from erpnext.accounts.utils import get_fiscal_year as erp_get_fiscal_year
from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import LandedCostVoucher


class CustomLandedCostVoucher(LandedCostVoucher):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.stock.doctype.landed_cost_item.landed_cost_item import LandedCostItem
		from erpnext.stock.doctype.landed_cost_purchase_receipt.landed_cost_purchase_receipt import (
			LandedCostPurchaseReceipt,
		)
		from erpnext.stock.doctype.landed_cost_taxes_and_charges.landed_cost_taxes_and_charges import (
			LandedCostTaxesandCharges,
		)

		amended_from: DF.Link | None
		company: DF.Link
		distribute_charges_based_on: DF.Literal["Qty", "Amount", "Distribute Manually"]
		items: DF.Table[LandedCostItem]
		naming_series: DF.Literal["MAT-LCV-.YYYY.-"]
		posting_date: DF.Date
		purchase_receipts: DF.Table[LandedCostPurchaseReceipt]
		taxes: DF.Table[LandedCostTaxesandCharges]
		total_taxes_and_charges: DF.Currency
	# end: auto-generated types

	@frappe.whitelist()
	def get_items_from_purchase_receipts(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			self.set("items", [])
			for pr in self.get("purchase_receipts"):
				if pr.receipt_document_type and pr.receipt_document:
					pr_items = get_pr_items(pr)

					for d in pr_items:
						item = self.append("items")
						item.item_code = d.item_code
						item.description = d.description
						item.qty = d.qty
						item.rate = d.base_rate
						item.cost_center = d.cost_center or erpnext.get_default_cost_center(self.company)
						item.amount = d.base_amount
						item.receipt_document_type = pr.receipt_document_type
						item.receipt_document = pr.receipt_document
						item.purchase_receipt_item = d.name
						item.is_fixed_asset = d.is_fixed_asset
		else:
			super().get_items_from_purchase_receipts()

	def autoname(self):
		if self.custom_landed_cost_voucher_type == 'Import' and self.custom_import_document:
			import_doc = frappe.get_doc("ImportDoc", self.custom_import_document)

			if import_doc.gd_no:
				# Use fiscal year (based on posting_date and company) in the name
				fiscal_year_name = None
				try:
					fy_info = erp_get_fiscal_year(self.posting_date or frappe.utils.nowdate(), company=self.company, as_dict=True)
					if isinstance(fy_info, dict):
						fiscal_year_name = fy_info.get('name')
					elif isinstance(fy_info, (list, tuple)) and fy_info:
						fiscal_year_name = fy_info[0]
				except Exception:
					pass

				# Fallback to two-digit current year if fiscal year resolution fails
				if not fiscal_year_name:
					fiscal_year_name = datetime.datetime.now().strftime('%y')

				base_name = f"ALP-LCV-{fiscal_year_name}-{import_doc.gd_no}"

				# Get all names that match the pattern
				existing = frappe.db.get_all(
					"Landed Cost Voucher",
					filters={"name": ["like", f"{base_name}%"]},
					fields=["name"]
				)
				existing_names = {d.name for d in existing}
				# Find the next available suffix
				if base_name not in existing_names:
					self.name = base_name
				else:
					i = 1
					while f"{base_name}-{i}" in existing_names:
						i += 1
					self.name = f"{base_name}-{i}"
		else:
			if hasattr(super(), 'autoname'):
				super().autoname()

	def validate_country_of_rigin(self):
		if not self.custom_country_of_origin:
			frappe.throw("Please Select Country Of Origin in Landed Cost Voucher")

	def validate(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			self.check_mandatory()
			self.validate_receipt_documents()
			self.validate_line_items()
			init_landed_taxes_and_totals(self)
			self.set_total_taxes_and_charges()
			if not self.get("items"):
				self.get_items_from_purchase_receipts()
		else:
			super().validate()

	def on_update(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			# If its an import voucher, in that case all charges will be applied systematically
			# User cant add manually anything in it, to streamline the costing & regulatory compliance
			self.validate_country_of_rigin()
			calculate_import_assessment(self)
			self.distribute_charges_based_on = 'Distribute Manually'
			self.set_applicable_import_charges()
			# Re-initialize ERPNext taxes/totals so base amounts are computed for new tax rows
			init_landed_taxes_and_totals(self)
			# Then compute total taxes and charges
			self.set_total_taxes_and_charges()
			self.set_applicable_charges_on_item()
		else:
			if hasattr(super(), 'on_update'):
				super().on_update()

	def apply_assessment_difference_and_duty(self):
		"""
		This function should suppose to enter unallocated import charges in baalnce sheet,
		however on client request we are adjusting it in profit and loss which is technically wrong
		"""
		total_assessment_diff = 0
		total_custom_duty = 0
		
		# Check if company exists
		if not self.company:
			frappe.throw("Company is required")
			
		company_doc = frappe.get_doc("Company", self.company)
		unallocated_import_charges_account = company_doc.custom_unallocated_import_charges_account
		assessment_variance_account = company_doc.custom_default_import_assessment_charge_account
		
		if not unallocated_import_charges_account:
			frappe.throw("Please Set Unallocated Import Charges Account in Company Settings")
		items = self.get('items') or []
		for d in items:
			total_assessment_diff += d.custom_base_assessment_difference
			total_custom_duty += (d.custom_cd + d.custom_acd)
		
		if unallocated_import_charges_account and assessment_variance_account:
			self.append("taxes",{
				'expense_account': unallocated_import_charges_account,
				'import_charge_type':'CD+Assessment Difference',
				'description':'Custom Duty  Charged to Stock Valuation & Pakistan Customs',
				'amount':total_custom_duty + 0
			})

	def set_applicable_import_charges(self):
		self.taxes = []
		self.apply_assessment_difference_and_duty()

	def validate_import_document(self):
		if self.landed_cost_voucher_type == 'Import' and not self.get('import_document'):
			frappe.throw('Please attach an import document')
		
		if self.get('import_document'):
			import_doc = frappe.get_doc("ImportDoc",self.get('import_document'))
			doc_status = [1,2]
			if import_doc.docstatus in doc_status:
				frappe.throw("Import document must be in Draft State, Import Doc {import_doc.name} is in {import_doc.status} state")

	def validate_applicable_charges_for_item(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			if self.distribute_charges_based_on == "Distribute Manually" and len(self.taxes) > 1:
				frappe.throw(
					_(
						"Please keep one Applicable Charges, when 'Distribute Charges Based On' is 'Distribute Manually'. For more charges, please create another Landed Cost Voucher."
					)
				)
			super().validate_applicable_charges_for_item()
		else:
			super().validate_applicable_charges_for_item()

	def on_submit(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			# CD/ACD total (total_taxes_and_charges) can legitimately be zero for a
			# 0%-CD shipment. The core "Distribute Manually" validation treats an
			# all-zero distribution as a user error, so only run it when there is
			# actually something to distribute/capitalize into stock. The ST/IT JV
			# below is independent of CD/ACD and must still be generated either way.
			if flt(self.total_taxes_and_charges):
				self.validate_applicable_charges_for_item()
			try:
				self.update_landed_cost()
				# Kept last: if JV creation fails, the exception below rolls back
				# and re-raises so the whole submit fails with it, instead of
				# leaving stock capitalized but taxes unposted.
				create_consolidated_import_taxes_jv(self.name)
			except Exception:
				frappe.db.rollback()
				raise
			if self.custom_import_document:
				enqueue_import_doc_refresh(self.custom_import_document)
		else:
			super().on_submit()

	def cancel_all_linked_jvs(self):
		linked_jv = frappe.get_list("Journal Entry",filters={'custom_import_document':self.custom_import_document,'docstatus':1,'is_system_generated':1},fields=['name'],pluck='name')
		for item in linked_jv:
			frappe.get_doc("Journal Entry",item).cancel()

	def on_cancel(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			self.update_landed_cost()
			self.cancel_all_linked_jvs()
			if self.custom_import_document:
				enqueue_import_doc_refresh(self.custom_import_document)
		else:
			super().on_cancel()

	def update_landed_cost(self):
		if self.custom_landed_cost_voucher_type == 'Import':
			for d in self.get("purchase_receipts"):
				doc = frappe.get_doc(d.receipt_document_type, d.receipt_document)
				if self.docstatus != 2:
					self.validate_asset_qty_and_status(d.receipt_document_type, doc)

				doc.set_landed_cost_voucher_amount()
				doc.update_valuation_rate(reset_outgoing_rate=False)

				for item in doc.get("items"):
					item.db_update()

				self.update_rate_in_serial_no_for_non_asset_items(doc)

			for d in self.get("purchase_receipts"):
				doc = frappe.get_doc(d.receipt_document_type, d.receipt_document)
				doc.docstatus = 2
				doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
				doc.make_gl_entries_on_cancel()

				doc.docstatus = 1
				doc.make_bundle_using_old_serial_batch_fields(via_landed_cost_voucher=True)
				doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
				if d.receipt_document_type == "Purchase Receipt":
					doc.make_gl_entries(via_landed_cost_voucher=True)
				else:
					doc.make_gl_entries()
				doc.repost_future_sle_and_gle(via_landed_cost_voucher=True)
		else:
			super().update_landed_cost()

	def validate_asset_qty_and_status(self, receipt_document_type, receipt_document):
		if self.custom_landed_cost_voucher_type == 'Import':
			for item in self.get("items"):
				if item.is_fixed_asset:
					receipt_document_type = (
						"purchase_invoice"
						if item.receipt_document_type == "Purchase Invoice"
						else "purchase_receipt"
					)
					docs = frappe.db.get_all(
						"Asset",
						filters={receipt_document_type: item.receipt_document, "item_code": item.item_code},
						fields=["name", "docstatus"],
					)
					if not docs or len(docs) < item.qty:
						frappe.throw(
							_(
								"There are only {0} asset created or linked to {1}. Please create or link {2} Assets with respective document."
							).format(len(docs), item.receipt_document, item.qty)
						)
					if docs:
						for d in docs:
							if d.docstatus == 1:
								frappe.throw(
									_(
										"{0} <b>{1}</b> has submitted Assets. Remove Item <b>{2}</b> from table to continue."
									).format(item.receipt_document_type, item.receipt_document, item.item_code)
								)
		else:
			super().validate_asset_qty_and_status(receipt_document_type, receipt_document)

	def update_rate_in_serial_no_for_non_asset_items(self, receipt_document):
		if self.custom_landed_cost_voucher_type == 'Import':
			for item in receipt_document.get("items"):
				if not item.is_fixed_asset and item.serial_no:
					serial_nos = get_serial_nos(item.serial_no)
					if serial_nos:
						frappe.db.sql(
							"update `tabSerial No` set purchase_rate=%s where name in ({})".format(
								", ".join(["%s"] * len(serial_nos))
							),
							tuple([item.valuation_rate, *serial_nos]),
						)
		else:
			super().update_rate_in_serial_no_for_non_asset_items(receipt_document)


def get_pr_items(purchase_receipt):
	item = frappe.qb.DocType("Item")
	pr_item = frappe.qb.DocType(purchase_receipt.receipt_document_type + " Item")
	return (
		frappe.qb.from_(pr_item)
		.inner_join(item)
		.on(item.name == pr_item.item_code)
		.select(
			pr_item.item_code,
			pr_item.description,
			pr_item.qty,
			pr_item.base_rate,
			pr_item.base_amount,
			pr_item.name,
			pr_item.cost_center,
			pr_item.is_fixed_asset,
			ConstantColumn(purchase_receipt.receipt_document_type).as_("receipt_document_type"),
			ConstantColumn(purchase_receipt.receipt_document).as_("receipt_document"),
		)
		.where(
			(pr_item.parent == purchase_receipt.receipt_document)
			& ((item.is_stock_item == 1) | (item.is_fixed_asset == 1))
		)
		.run(as_dict=True)
	)