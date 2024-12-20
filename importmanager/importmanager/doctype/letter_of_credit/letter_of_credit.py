# Copyright (c) 2024, SpotLedger and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LetterOfCredit(Document):
	
	def validate(self):
		self.calc_lc_base_amount()

		"""
		Thses validation shoudl be passed here
		1. expiry cant be less then issue date
		2. effective date cant be less then epxiry, or issue date
		
		"""
	
	def calc_lc_base_amount(self):
		self.base_lc_amount = self.exchange_rate * self.lc_amount
	
	
	
