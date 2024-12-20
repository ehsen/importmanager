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
                                    import_document=lcv_doc.custom_import_document)
            
            if item.custom_ast > 0:
                
                create_journal_voucher("AST PakistanCustoms",lcv_doc.posting_date,get_additional_sales_tax_entries(item,company),
                                    import_document=lcv_doc.custom_import_document)
            
            if item.custom_it > 0:
                create_journal_voucher("IT PakistanCustoms",lcv_doc.posting_date,get_advance_income_tax_entries(item,company),
                                    import_document=lcv_doc.custom_import_document)
            
            if item.custom_cd > 0:
                create_journal_voucher("CD PakistanCustoms",lcv_doc.posting_date,get_custom_duty_entries(item,company),
                                    import_document=lcv_doc.custom_import_document)
            
            if item.custom_acd > 0:
                create_journal_voucher("ACD PakistanCustoms",lcv_doc.posting_date,get_additional_custom_duty_entries(item,company),
                                    import_document=lcv_doc.custom_import_document)
            
        
        except Exception as e:
            frappe.log_error(message=f"{str(e)}",title="Error Creating Import Jvs")
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
        calculate_import_taxes(item)
        #lcv_doc.save()
        #frappe.db.commit()

def get_taxes_by_category(tax_template_name):
    query = """
            select custom_tax_category,tax_rate from `tabItem Tax Template Detail` where parent = '{tax_template_name}';
            """.format(tax_template_name=tax_template_name)
    result = frappe.db.sql(query,as_dict=1)
    taxes_dict = {}
    for item in result:
        taxes_dict[item['custom_tax_category']] = item['tax_rate']
    
    return taxes_dict



def calculate_import_taxes(lcv_item):
    item = frappe.get_cached_doc("Item",lcv_item.item_code)
    tax_list = frappe.get_list("Item Tax Template",filters={'custom_customs_tariff_number':item.customs_tariff_number},
                               fields=['name'],pluck='name')
    if len(tax_list) > 0:
        # get taxes here
        tax_dict = get_taxes_by_category(tax_list[0])
        
        
        lcv_item.custom_cd = tax_dict.get('CD',0)/100 *lcv_item.custom_base_assessed_value
        lcv_item.custom_acd = tax_dict.get('ACD',0)/100 * lcv_item.custom_base_assessed_value
        amount_for_sales_tax = lcv_item.custom_base_assessed_value + lcv_item.custom_cd + lcv_item.custom_acd
        lcv_item.custom_ast = tax_dict.get('AST',0)/100 * amount_for_sales_tax
        lcv_item.custom_stamnt = tax_dict.get('Sales Tax',0)/100 * amount_for_sales_tax
        amount_for_it = amount_for_sales_tax + lcv_item.custom_ast + lcv_item.custom_stamnt
        lcv_item.custom_it = tax_dict.get('IT',0)/100 * amount_for_it
        lcv_item.custom_total_duties_and_taxes = lcv_item.custom_cd+lcv_item.custom_acd+lcv_item.custom_stamnt + lcv_item.custom_ast+lcv_item.custom_it
        lcv_item.custom_base_assessment_difference = lcv_item.custom_base_assessed_value - lcv_item.amount
        lcv_item.applicable_charges = lcv_item.custom_base_assessment_difference
        # Following asserrtion must pass if all above calculations are correct
        assert(lcv_item.amount + lcv_item.custom_base_assessment_difference == lcv_item.custom_base_assessed_value)

def update_import_charges_in_import(doc):
    # This function will accumualte import charges in ImportDoc from Individual Doc
    import_charges = []
    data_dict = {}
    import_doc = frappe.get_doc("ImportDoc",doc.custom_import_document)
    for item in doc.items:
        data_dict['document_type'] = "Purchase Invoice"
        data_dict['doc_name'] = doc.name
        data_dict['charge_item'] = item.item_name
        data_dict['paid_to'] = doc.supplier
        data_dict['amount'] = item.amount
        data_dict['purchase_invoice_item'] = item.name
        import_doc.append("linked_import_charges",data_dict)
    
    import_doc.save()

def update_line_items(import_doc_name):
    linked_items = []
    linked_pi = frappe.get_list("Purchase Invoice",filters={'docstatus':1,"custom_purchase_invoice_type":"Import",
                                                               "custom_import_document":import_doc_name},fields=['name'],pluck='name')
    
    linked_items = frappe.get_list('Purchase Invoice Item',filters={'parent':['in',linked_pi]},fields=['name'],pluck='name')
    print(linked_items)
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    data_dict = {}
    import_doc.items = []
    for item in linked_items:
        pi_item = frappe.get_doc("Purchase Invoice Item",item)
        data_dict['purchase_invoice'] = pi_item.parent
        data_dict['item_code'] = pi_item.item_code
        data_dict['item_name'] = pi_item.item_name
        data_dict['uom'] = pi_item.uom
        data_dict['qty'] = pi_item.qty
        data_dict['amount'] = pi_item.base_amount
        import_doc.append("items",data_dict)
    
    import_doc.save()



def update_misc_import_charges(import_doc_name):
    # This function will fetch all charges not covered in service invoices
    # For now it ll deal with LC Charges/ Any Exchange Gains/Losses
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    lc_settlements = frappe.get_list("LC Settlement",filters={'import_document':import_doc_name,'docstatus':1},fields=[
        'name','lc_charges','letter_of_credit_to_settle'
    ])
    print(lc_settlements)
    if len(lc_settlements) > 0:
        lc_doc = frappe.get_doc("Letter Of Credit",lc_settlements[0]['letter_of_credit_to_settle'])
        print(lc_doc)
        data_dict = {}
        for item in lc_settlements:
            data_dict['document_type'] = 'LC Settlement'
            data_dict['document_name'] = item['name']
            data_dict['import_charge_type'] = "LC Charges"
            data_dict['paid_to'] = lc_doc.issuing_bank
            data_dict['amount'] = item['lc_charges']
            import_doc.append("linked_misc_import_charges",data_dict)
        import_doc.save()

def bulk_update_import_charges(import_doc_name):
    linked_pi = frappe.get_list("Purchase Invoice",filters={'docstatus':1,"custom_purchase_invoice_type":"Import Service Charges",
                                                               "custom_import_document":import_doc_name},fields=['name'],pluck='name')

    for item in linked_pi:
        
        update_import_charges_in_import(frappe.get_doc("Purchase Invoice",item))


    #frappe.db.commit()

def update_data_in_import_doc(import_doc_name):
    #bulk_update_import_charges(import_doc_name)
    update_misc_import_charges(import_doc_name)
    update_line_items(import_doc_name)
    
    frappe.db.commit()






 
    
    

    

            


        
        




