import frappe
from frappe.utils import nowdate

def create_journal_voucher(title, posting_date, accounts,import_document=None):
    """
    Create a Journal Voucher (Journal Entry) in ERPNext.

    :param title: Title for the Journal Voucher.
    :param posting_date: Date for the Journal Entry (e.g., '2024-12-07').
    :param accounts: List of account details (each dict with account, debit, credit, and cost_center if needed).
                     Example:
                     [
                         {"account": "Debtors - CO", "debit": 1000, "credit": 0},
                         {"account": "Sales - CO", "debit": 0, "credit": 1000},
                     ]
    :return: Name of the created Journal Entry or an error message.
    """
    
    # Create a new Journal Entry document
    jv = frappe.new_doc("Journal Entry")
    jv.title = title
    jv.posting_date = posting_date or nowdate()
    jv.voucher_type = "Journal Entry"
    if import_document is not None:
        jv.custom_import_document = import_document

    # Add accounts to the Journal Entry
    for acc in accounts:
        jv.append("accounts", {
            "account": acc["account"],
            "debit_in_account_currency": acc.get("debit", 0),
            "credit_in_account_currency": acc.get("credit", 0),
            "cost_center": acc.get("cost_center", None),
            "party_type":acc.get("party_type",None),
            "party":acc.get("party",None),

        })

    # Validate and save the document
    jv.insert()
    jv.submit()
    
    
    return f"Journal Entry '{jv.name}' created successfully."

    

def get_sales_tax_entries(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_sales_tax_input_account,'debit':lcv_item.custom_stamnt,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Pakistan Customs','debit':0,'credit':lcv_item.custom_stamnt}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def get_additional_sales_tax_entries(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_sales_tax_input_account,'debit':lcv_item.custom_ast,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Pakistan Customs','debit':0,'credit':lcv_item.custom_ast}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def get_advance_income_tax_entries(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_advance_income_tax,'debit':lcv_item.custom_it,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Pakistan Customs','debit':0,'credit':lcv_item.custom_it}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def get_custom_duty_entries(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_unallocated_import_charges_account,'debit':lcv_item.custom_cd,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Pakistan Customs','debit':0,'credit':lcv_item.custom_cd}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def get_additional_custom_duty_entries(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_unallocated_import_charges_account,'debit':lcv_item.custom_acd,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Pakistan Customs','debit':0,'credit':lcv_item.custom_acd}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def create_import_taxes_jv(landed_cost_voucher):
    lcv_doc = frappe.get_doc("Landed Cost Voucher",landed_cost_voucher)
    company = frappe.get_cached_doc("Company",lcv_doc.company)
    # Loop over LCV items
    
    

    for item in lcv_doc.get("items"):
        try:
            if item.custom_stamnt > 0:
                
                create_journal_voucher("ST PakistanCustoms",lcv_doc.posting_date,get_sales_tax_entries(item,company),
                                    import_document=lcv_doc.name)
            
            if item.custom_ast > 0:
                
                create_journal_voucher("AST PakistanCustoms",lcv_doc.posting_date,get_additional_sales_tax_entries(item,company),
                                    import_document=lcv_doc.name)
            
            if item.custom_it > 0:
                create_journal_voucher("IT PakistanCustoms",lcv_doc.posting_date,get_advance_income_tax_entries(item,company),
                                    import_document=lcv_doc.name)
            
            if item.custom_cd > 0:
                create_journal_voucher("CD PakistanCustoms",lcv_doc.posting_date,get_custom_duty_entries(item,company),
                                    import_document=lcv_doc.name)
            
            if item.custom_acd > 0:
                create_journal_voucher("ACD PakistanCustoms",lcv_doc.posting_date,get_additional_custom_duty_entries(item,company),
                                    import_document=lcv_doc.name)
            
            frappe.db.commit() # Commit the transaction to DB
        except Exception as e:
            frappe.log_error(message=f"{str(e)}",title="Error Creating Import Jvs")
            frappe.db.rollback()
            frappe.throw("Error Creating Import JVs. Please Contact Support")
def calculate_assessed_value(lcv_doc_item):
    incoterm = frappe.get_doc(lcv_doc_item.receipt_document_type,lcv_doc_item.receipt_document).incoterm
    
    if incoterm is None:
        frappe.throw("No Incoterm found in Purchase Invoice")
    
    ex_assess_value = lcv_doc_item.custom_assessed_value_per_unit * lcv_doc_item.qty
    lcv_doc_item.custom_cfr_value = ex_assess_value
    lcv_doc_item.custom_landing_charges_1 = (ex_assess_value + lcv_doc_item.custom_insurance) * 0.01
    lcv_doc_item.custom_assessed_value = lcv_doc_item.custom_cfr_value + lcv_doc_item.custom_landing_charges_1 + lcv_doc_item.custom_insurance
    lcv_doc_item.custom_base_assessed_value = round(lcv_doc_item.custom_assessed_value * lcv_doc_item.custom_exchange_rate)





def calculate_import_assessment(lcv_doc):
    print(f"lcv doc items are {lcv_doc.items}")
    for item in lcv_doc.items:
        
        calculate_assessed_value(item)
        #lcv_doc.save()
        #frappe.db.commit()

def calculate_import_taxes(lcv_item):
    item = frappe.get_cached_doc("Item",lcv_item.item_code)
    


    

            


        
        




