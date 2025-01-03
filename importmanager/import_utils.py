import frappe
from frappe.utils import nowdate
from erpnext import get_default_cost_center

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
    jv.is_system_generated = 1 # All entries via this method shoudl be marked as system generated
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


def create_gl_entries(posting_date, accounts, company):
    """
    Create GL Entries in ERPNext.

    :param posting_date: Date for the GL Entries (e.g., '2024-12-07').
    :param accounts: List of account details (each dict with account, debit, credit, and cost_center if needed).
                     Example:
                     [
                         {"account": "Debtors - CO", "debit": 1000, "credit": 0},
                         {"account": "Sales - CO", "debit": 0, "credit": 1000},
                     ]
    :param against_voucher_type: (Optional) Type of the voucher for the entry.
    :param against_voucher: (Optional) The voucher for which the GL entry is created.
    :return: List of GL Entry names or an error message.
    """
    
    print(accounts)
    # Prepare GL Entry details
    gl_entries = []
    for acc in accounts:
        gl_entry = frappe.new_doc("GL Entry")
        gl_entry.posting_date = posting_date or nowdate()
        gl_entry.account = acc["account"]
        gl_entry.debit = acc.get("debit", 0)
        gl_entry.credit = acc.get("credit", 0)
        gl_entry.cost_center = acc.get("cost_center", get_default_cost_center(company))
        gl_entry.party_type = acc.get("party_type", None)
        gl_entry.party = acc.get("party", None)
        gl_entry.company = company

        
        gl_entry.voucher_type = acc.get("voucher_type",None)
        gl_entry.voucher_no = acc.get("voucher_no",None)
        gl_entry.voucher_subtype = acc.get("voucher_subtype",None)
        gl_entry.against = acc.get("account",None)

        # Insert GL Entry one by one (instead of bulk insert)
        try:
            gl_entry.insert()  # This will trigger validation and insert each entry individually
            gl_entries.append(gl_entry)
        except Exception as e:
            frappe.log_error(f"Error inserting GL Entry: {str(e)}", "GL Entry Insertion Error")

    # Return the list of names of successfully inserted entries
    return [entry.name for entry in gl_entries]


    

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

def get_cess_amount_entries(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_unallocated_import_charges_account,'debit':lcv_item.custom_cess_amount,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Sindh Excise and Taxation','debit':0,'credit':lcv_item.custom_cess_amount}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def get_assessment_variance_transfer_entry(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_unallocated_import_charges_account,'debit':lcv_item.custom_base_assessment_difference,'credit':0}
    credit_dict = {'account':company.custom_assessment_variance_account,'debit':0,'credit':lcv_item.custom_base_assessment_difference}
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
            
            if item.custom_cess_amount > 0:
                create_journal_voucher("Cess Sindh Excise and Taxation",lcv_doc.posting_date,get_cess_amount_entries(item,company),
                                    import_document=lcv_doc.custom_import_document)
            
            if item.custom_base_assessment_difference > 0:
                create_journal_voucher("Assessment Variance Transfer",lcv_doc.posting_date,get_assessment_variance_transfer_entry(item,company),
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
        lcv_item.applicable_charges = lcv_item.custom_base_assessment_difference + lcv_item.custom_cd + lcv_item.custom_acd
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
        data_dict['purchase_receipt_item']  = pi_item.name
        import_doc.append("items",data_dict)
    
    import_doc.save()

def get_customs_duty(import_doc_name):
    lcv = frappe.get_list("Landed Cost Voucher",filters={'custom_import_document':import_doc_name, 'docstatus':1},fields=['name'],pluck='name')
    custom_duty = 0
    acd = 0
    cess = 0
    item_wise_duty = {}
    
    for item in lcv:
        lcv_doc = frappe.get_doc("Landed Cost Voucher",item)
        for lcv_item in lcv_doc.items:
            custom_duty += lcv_item.custom_cd
            acd += lcv_item.custom_acd
            cess += lcv_item.custom_cess_amount
            if lcv_item.item_code not in item_wise_duty:
                item_wise_duty[lcv_item.item_code] = {'custom_duty':lcv_item.custom_cd,'acd':lcv_item.custom_acd,'cess':
                lcv_item.custom_cess_amount}
            elif lcv_item.item_code in item_wise_duty:
                item_wise_duty[lcv_item.item_code]['custom_duty'] += lcv_item.custom_cd
                item_wise_duty[lcv_item.item_code]['acd'] += lcv_item.custom_acd
                item_wise_duty[lcv_item.item_code]['cess'] += lcv_item.custom_acd
        
    return {'item_wise_duty':item_wise_duty,'total':{'custom_duty':custom_duty,'acd':acd,'cess':cess}}

    
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
        
    custom_data = get_customs_duty(import_doc_name)['total']
    total_customs_duty = custom_data['custom_duty'] + custom_data['acd']
    total_cess = custom_data['cess']
    if total_customs_duty > 0:
        import_doc.append("linked_misc_import_charges", {'import_charge_type':'Customs Duty',
        'amount':total_customs_duty})
    
    if total_cess > 0:
        import_doc.append("linked_misc_import_charges", {'import_charge_type':'Cess',
        'amount':total_cess})
    
    

    import_doc.save()

def update_unallocated_misc_charges_jv(import_doc_name):
    """
    Update the ImportDoc's misc import charges based on related Journal Entries.

    :param import_doc_name: Name of the ImportDoc to update.
    """
    import_doc = frappe.get_doc("ImportDoc", import_doc_name)
    
    # Get the default unallocated import charges account from the Company document
    company = frappe.get_doc("Company", import_doc.company)
    unallocated_import_charges_account = company.custom_unallocated_import_charges_account

    if not unallocated_import_charges_account:
        frappe.throw(f"Please set 'Default Unallocated Import Charges Account' in the Company {import_doc.company}.")

    # Fetch submitted Journal Entries related to the ImportDoc
    journal_entries = frappe.get_list(
        "Journal Entry",
        filters={"custom_import_document": import_doc_name, "docstatus": 1,'is_system_generated':0},
        fields=["name"]
    )
    
    if not journal_entries:
        frappe.msgprint(f"No submitted Journal Entries found for ImportDoc {import_doc_name}.")
        return

    # Process each Journal Entry and update misc import charges
    for je in journal_entries:
        je_doc = frappe.get_doc("Journal Entry", je["name"])
        for account in je_doc.accounts:
            if account.account == unallocated_import_charges_account:
                # Prepare misc charges entry
                misc_charge = {
                    "import_charge_type": je_doc.custom_import_charge_type,
                    "amount": account.debit_in_account_currency - account.credit_in_account_currency,
                    "document_type": "Journal Entry",
                    "document_name": je_doc.name
                }
                
                # Include party information if available
                if account.party:
                    misc_charge["paid_to"] = account.party

                # Append the charge to ImportDoc
                import_doc.append("linked_misc_import_charges", misc_charge)

    # Save the updated ImportDoc
    import_doc.save()
    frappe.msgprint(f"Misc import charges updated for ImportDoc {import_doc_name}.")




def bulk_update_import_charges(import_doc_name):
    linked_pi = frappe.get_list("Purchase Invoice",filters={'docstatus':1,"custom_purchase_invoice_type":"Import Service Charges",
                                                               "custom_import_document":import_doc_name},fields=['name'],pluck='name')

    

    for item in linked_pi:
        
        update_import_charges_in_import(frappe.get_doc("Purchase Invoice",item))


    #frappe.db.commit()


    




def calculate_total_import_charges(import_doc_name):
    # this function will loop over all ex tax import charges and accumualte them for
    # allocating to item
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    
    total_import_charges = sum(row.amount for row in import_doc.linked_import_charges) or 0
    total_misc_import_charges = sum(row.amount for row in import_doc.linked_misc_import_charges) or 0
    total_invoices_amount = sum(row.total_base_value for row in import_doc.linked_purchase_invoices) or 0
    total_customs_duty = sum(row.amount for row in import_doc.linked_misc_import_charges if row.import_charge_type=="Customs Duty") or 0

    

    import_doc.total_import_charges = total_import_charges + total_misc_import_charges
    import_doc.total_cost = import_doc.total_import_charges + total_invoices_amount
    import_doc.total_customs_duty = total_customs_duty
    import_doc.save()

def get_landed_cost_item(import_doc_name,purchase_receipt_item):
    """
    This function will return the appropirately landed cost item for PR/PI Item if avialable, to 
    extract the import_related_charges from it
    """
    lcv_item = frappe.get_list("Landed Cost Item",filters={'purchase_receipt_item':purchase_receipt_item,'docstatus':1},fields=['name'],
                               pluck='name')
    print(f"lcv item is {lcv_item}")
    if len(lcv_item) == 0:
        return None
    return frappe.get_doc("Landed Cost Item",lcv_item[0])

def allocate_import_charges(import_doc_name):
    # Import Charges Will be allocated proporitanlly as per item amount
    #TODO: This function should striclty be tested for ImportDoc where multiple Items are added
    # TODO: This function shoudl be optimzied the way it pulls the import charges from LCV. 
    
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    item_wise_total_duty = get_customs_duty(import_doc_name)['item_wise_duty']
    if import_doc.total_import_charges > 0:
        total_items_amount = sum(row.amount for row in import_doc.items)
        for item in import_doc.items:
            item_customs_duty = 0
            lcv_item = get_landed_cost_item(import_doc_name,item.purchase_receipt_item)
            


            if item.item_code in item_wise_total_duty.keys():
                item_customs_duty += (item_wise_total_duty[item.item_code]['custom_duty']+item_wise_total_duty[item.item_code]['acd'])

            item.allocated_charges_ex_cd = (item.amount/total_items_amount * (import_doc.total_import_charges-import_doc.total_customs_duty)) or 0
            item.allocated_import_charges = item_customs_duty + item.allocated_charges_ex_cd
            item.net_unit_cost = (item.allocated_import_charges + item.amount)/item.qty
            item.st_unit_cost = 0
            if lcv_item is not None:
                item.st_unit_cost += ((lcv_item.custom_base_assessed_value + item_customs_duty)/item.qty)
            

                
        total_allocated_charges = sum(item.allocated_import_charges for item in import_doc.items)
        assert(total_allocated_charges == import_doc.total_import_charges)
        import_doc.save()

    



def set_expense_head(doc, method):
    """
    Hook for Purchase Invoice on_save event.
    If custom_purchase_invoice_type == "Import Service Charges" and import_document is not None,
    set the expense head of each Purchase Invoice Item to the custom_unallocated_import_charges_account
    from the Company Doc.
    """
    if doc.custom_purchase_invoice_type == "Import Service Charges" and doc.custom_import_document:
        # Fetch the Company document to get the account
        company = frappe.get_doc("Company", doc.company)
        unallocated_charges_account = company.custom_unallocated_import_charges_account

        if not unallocated_charges_account:
            frappe.throw("Please set 'Unallocated Import Charges Account' in Company settings.")

        # Update expense head in items
        for item in doc.items:
            #frappe.log_error(message=f"Unallocated Import Account is {unallocated_charges_account}",title="Unalloacated issue")
            item.expense_account = unallocated_charges_account

        # Indicate that the document has been modified
        doc.flags.ignore_validate_update_after_submit = True


def update_data_in_import_doc(import_doc_name):
    doc = frappe.get_doc("ImportDoc",import_doc_name)
    doc.items = []
    doc.linked_import_charges = []
    doc.linked_misc_import_charges = []
    doc.save()
    
    
    bulk_update_import_charges(import_doc_name)
    update_misc_import_charges(import_doc_name)
    update_unallocated_misc_charges_jv(import_doc_name)
    update_line_items(import_doc_name)
    calculate_total_import_charges(import_doc_name)
    allocate_import_charges(import_doc_name)
    frappe.db.commit()






 
    
    

    

            


        
        




