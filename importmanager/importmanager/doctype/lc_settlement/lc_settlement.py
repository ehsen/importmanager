# Copyright (c) 2024, SpotLedger and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from importmanager.import_utils import create_journal_voucher


class LCSettlement(Document):
	def validate(self):
		self.calc_exchange_diff()
		self.calc_total_settlement()

	def calc_exchange_diff(self):
		self.settlement_base_lc_amount = self.settlement_exchange_rate * self.lc_amount
		self.base_exchange_gains_losses = self.settlement_base_lc_amount - self.base_lc_amount
	
	def update_letter_of_credit(self):
		frappe.db.set_value("Letter Of Credit",self.letter_of_credit_to_settle,"lc_settlement",self.name)
	
	def calc_total_settlement(self):
		self.total_settlement_amount = self.settlement_base_lc_amount + self.lc_charges
	
	def unlinkp_letter_of_credit(self):
		frappe.db.set_value("Letter Of Credit",self.letter_of_credit_to_settle,"lc_settlement",None)

	def on_submit(self):
		self.update_letter_of_credit()
	
	def on_cancel(self):
		#self.cancel_linked_lc_doc()
		self.unlinkp_letter_of_credit()


	


	
