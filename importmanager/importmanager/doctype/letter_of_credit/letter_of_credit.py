# Copyright (c) 2024, SpotLedger and contributors
# For license information, please see license.txt

import frappe
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
    
    def update_party_status(self):
        party_name = frappe.db.exists(
            "Party",
            {"party_type": "Letter of Credit", "party_name": self.name}
        )
        if not party_name:
            return

        # Party should be usable only if LC is Active
        disabled = 0 if self.status == "Active" else 1
        frappe.db.set_value("Party", party_name, "disabled", disabled)

    def on_submit(self):
        

        self.update_party_status()

    def on_update(self):
        self.update_party_status()

    def on_cancel(self):
        self.status = "Cancelled"
        self.update_party_status()

    
    
