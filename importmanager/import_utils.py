import frappe
from frappe.utils import nowdate,datetime
from erpnext.accounts.utils import get_fiscal_year as erp_get_fiscal_year
from erpnext import get_default_cost_center
from erpnext.controllers.taxes_and_totals import get_itemised_tax_breakup_data
import time
from frappe.exceptions import TimestampMismatchError
from frappe.model.naming import make_autoname

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
    # Determine company from accounts or import_document
    company = None
    if import_document:
        # Try to get company from ImportDoc or Landed Cost Voucher
        try:
            import_doc = frappe.get_doc("ImportDoc", import_document)
            company = import_doc.company
        except Exception:
            try:
                lcv_doc = frappe.get_doc("Landed Cost Voucher", import_document)
                company = lcv_doc.company
            except Exception:
                pass
    if not company and accounts:
        # Try to get company from account (first account's company)
        acc_name = accounts[0].get("account")
        if acc_name:
            company = frappe.get_cached_value("Account", acc_name, "company")
    if not company:
        frappe.throw("Unable to determine company for round off calculation.")

    # 1. Round all amounts to nearest integer
    for acc in accounts:
        acc["debit"] = round(acc.get("debit", 0), 0)
        acc["credit"] = round(acc.get("credit", 0), 0)

    # 2. Calculate totals
    total_debit = sum(acc.get("debit", 0) for acc in accounts)
    total_credit = sum(acc.get("credit", 0) for acc in accounts)
    diff = total_debit - total_credit

    # 3. Add round off entry if needed
    if abs(diff) > 0:
        round_off_account = frappe.get_cached_value("Company", company, "round_off_account")
        if not round_off_account:
            frappe.throw("Please set Round Off Account in Company settings.")
        if diff > 0:
            accounts.append({"account": round_off_account, "debit": 0, "credit": abs(diff)})
        else:
            accounts.append({"account": round_off_account, "debit": abs(diff), "credit": 0})

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
        gl_entry.against = acc.get("against",None)

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
    debit_dict = {'account':company.custom_cess_account,'debit':lcv_item.custom_cess_amount,'credit':0}
    credit_dict = {'account':company.custom_default_gov_payable_account,'party_type':'Government','party':'Sindh Excise and Taxation','debit':0,'credit':lcv_item.custom_cess_amount}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def get_assessment_variance_transfer_entry(lcv_item,company):
    accounts_list = []
    debit_dict = {'account':company.custom_unallocated_import_charges_account,'debit':lcv_item.custom_base_assessment_difference,'credit':0}
    credit_dict = {'account':company.custom_default_import_assessment_charge_account,'debit':0,'credit':lcv_item.custom_base_assessment_difference}
    accounts_list.append(debit_dict)
    accounts_list.append(credit_dict)
    return accounts_list

def create_consolidated_import_taxes_jv(landed_cost_voucher):
    """
    Creates consolidated journal entries for import taxes from landed cost voucher.
    Creates one JV for assessment variance and one JV for all other tax entries.
    Includes GD number in JV titles.
    
    Args:
        landed_cost_voucher: Name of the Landed Cost Voucher
    """
    lcv_doc = frappe.get_doc("Landed Cost Voucher", landed_cost_voucher)
    company = frappe.get_cached_doc("Company", lcv_doc.company)
    
    # Get GD number from ImportDoc
    import_doc = frappe.get_doc("ImportDoc", lcv_doc.custom_import_document)
    gd_no = import_doc.gd_no if import_doc.gd_no else "NO-GD"
    
    # Initialize lists for different types of entries
    regular_tax_entries = []
    assessment_entries = []
    
    for item in lcv_doc.get("items"):
        try:
            # Collect assessment variance entries
            if item.custom_base_assessment_difference > 0:
                assessment_entries.extend(get_assessment_variance_transfer_entry(item, company))
            
            # Collect all other tax entries
            if item.custom_stamnt > 0:
                regular_tax_entries.extend(get_sales_tax_entries(item, company))
            if item.custom_ast > 0:
                regular_tax_entries.extend(get_additional_sales_tax_entries(item, company))
            if item.custom_it > 0:
                regular_tax_entries.extend(get_advance_income_tax_entries(item, company))
            if item.custom_cd > 0:
                regular_tax_entries.extend(get_custom_duty_entries(item, company))
            if item.custom_acd > 0:
                regular_tax_entries.extend(get_additional_custom_duty_entries(item, company))
            if item.custom_cess_amount > 0:
                regular_tax_entries.extend(get_cess_amount_entries(item, company))
                
        except Exception as e:
            frappe.log_error(message=f"{str(e)}", title="Error Creating Import Tax JVs")
            frappe.throw("Error Creating Import Tax JVs. Please Contact Support")

    # Create separate JV for assessment variance
    

    if assessment_entries:
        create_journal_voucher(
            f"Assessment Variance Transfer - GD-{gd_no}",
            lcv_doc.posting_date,
            assessment_entries,
            import_document=lcv_doc.custom_import_document
        )
    

    # Create consolidated JV for all other tax entries
    if regular_tax_entries:
        # Group entries by account, party_type, and party
        consolidated_entries = {}
        
        for entry in regular_tax_entries:
            # Create unique key for grouping
            key = (
                entry["account"],
                entry.get("party_type", ""),
                entry.get("party", "")
            )
            
            if key in consolidated_entries:
                # Add to existing entry
                consolidated_entries[key]["debit"] += entry.get("debit", 0)
                consolidated_entries[key]["credit"] += entry.get("credit", 0)
            else:
                # Create new entry
                consolidated_entries[key] = {
                    "account": entry["account"],
                    "debit": entry.get("debit", 0),
                    "credit": entry.get("credit", 0),
                    "party_type": entry.get("party_type"),
                    "party": entry.get("party")
                }
        
        # Convert consolidated entries to list
        final_entries = list(consolidated_entries.values())
        frappe.log_error(message=f"{final_entries}",title="final entries")
        
        # Create single JV for all tax entries
        create_journal_voucher(
            f"Consolidated Import Taxes - GD-{gd_no}",
            lcv_doc.posting_date,
            final_entries,
            import_document=lcv_doc.custom_import_document
        )

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
        incoterm = "Cost and Freight"
    
    ex_assess_value = lcv_doc_item.custom_assessed_value_per_unit * lcv_doc_item.qty
    lcv_doc_item.custom_cfr_value = ex_assess_value
    lcv_doc_item.custom_landing_charges__1 = round((ex_assess_value + lcv_doc_item.custom_insurance) * 0.01,2)
    lcv_doc_item.custom_assessed_value = lcv_doc_item.custom_cfr_value + lcv_doc_item.custom_landing_charges__1 + lcv_doc_item.custom_insurance
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
    lcv_doc = frappe.get_cached_doc("Landed Cost Voucher",lcv_item.parent)
    item = frappe.get_cached_doc("Item",lcv_item.item_code)
    tax_list = frappe.get_list("Item Tax Template",filters={'custom_customs_tariff_number':item.customs_tariff_number,
                                                            'custom_country_of_origin':lcv_doc.custom_country_of_origin},
                               fields=['name'],pluck='name')
    if len(tax_list) > 0:
        # get taxes here
        """
        All GD taxes will be rounded off, we are forcing it from backend,
        but I think it should be avoided, will be dealt later on
        """
        tax_dict = get_taxes_by_category(tax_list[0])
        
        lcv_item.custom_cd = round(tax_dict.get('CD',0)/100 *lcv_item.custom_base_assessed_value,0)
        lcv_item.custom_acd = round(tax_dict.get('ACD',0)/100 * lcv_item.custom_base_assessed_value,0)
        amount_for_sales_tax = round(lcv_item.custom_base_assessed_value + lcv_item.custom_cd + lcv_item.custom_acd,0)
        lcv_item.custom_ast = round(tax_dict.get('AST',0)/100 * amount_for_sales_tax,0)
        lcv_item.custom_stamnt = round(tax_dict.get('Sales Tax',0)/100 * amount_for_sales_tax,0)
        amount_for_it = round(amount_for_sales_tax + lcv_item.custom_ast + lcv_item.custom_stamnt,0)
        lcv_item.custom_it = round(tax_dict.get('IT',0)/100 * amount_for_it,0)
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
        #data_dict['charge_item'] = item.item_name
        data_dict['import_charge_type'] = item.item_name
        data_dict['paid_to'] = doc.supplier
        data_dict['amount'] = item.amount
        data_dict['total_st'] = item.custom_st
        data_dict['total_incl_tax'] = item.custom_total_incl_tax
        #data_dict['purchase_invoice_item'] = item.name
        import_doc.append("linked_import_charges",data_dict)
    
    import_doc.save()

def update_line_items(import_doc_name):
    linked_items = []
    linked_pi = frappe.get_list("Purchase Invoice",filters={'docstatus':1,"custom_purchase_invoice_type":"Import",
                                                               "custom_import_document":import_doc_name},fields=['name'],pluck='name',ignore_permissions=True)
    
    linked_items = frappe.get_list('Purchase Invoice Item',filters={'parent':['in',linked_pi]},fields=['name'],pluck='name',ignore_permissions=True)
    print(linked_items)
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    data_dict = {}
    import_doc.items = []
    for item in linked_items:
        pi_item = frappe.get_doc("Purchase Invoice Item",item,ignore_permissions=True)
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
    lcv = frappe.get_list("Landed Cost Voucher",filters={'custom_import_document':import_doc_name, 'docstatus':1},fields=['name'],pluck='name',ignore_permissions=True)
    custom_duty = 0
    acd = 0
    cess = 0
    stamnt = 0
    ast = 0
    it = 0
    item_wise_duty = {}
    print(f"lcv is {lcv}")
    
    # Check if lcv list is empty
    if not lcv:
        return {
            'landed_cost_voucher_name': None,
            'item_wise_duty': item_wise_duty,
            'total': {
                'custom_duty': custom_duty,
                'acd': acd,
                'cess': cess,
                'stamnt': stamnt,
                'ast': ast,
                'it': it
            }
        }
    
    for item in lcv:
        lcv_doc = frappe.get_doc("Landed Cost Voucher",item,ignore_permissions=True)
        for lcv_item in lcv_doc.items:
            custom_duty += lcv_item.custom_cd
            acd += lcv_item.custom_acd
            cess += lcv_item.custom_cess_amount
            stamnt += lcv_item.custom_stamnt
            ast += lcv_item.custom_ast
            it += lcv_item.custom_it
            if lcv_item.item_code not in item_wise_duty:
                item_wise_duty[lcv_item.item_code] = {'custom_duty':lcv_item.custom_cd,'acd':lcv_item.custom_acd,'cess':
                lcv_item.custom_cess_amount,'stamnt':lcv_item.custom_stamnt,'ast':lcv_item.custom_ast,'it':lcv_item.custom_it}
            elif lcv_item.item_code in item_wise_duty:
                item_wise_duty[lcv_item.item_code]['custom_duty'] += lcv_item.custom_cd
                item_wise_duty[lcv_item.item_code]['acd'] += lcv_item.custom_acd
                item_wise_duty[lcv_item.item_code]['cess'] += lcv_item.custom_cess_amount
                item_wise_duty[lcv_item.item_code]['stamnt'] += lcv_item.custom_stamnt
                item_wise_duty[lcv_item.item_code]['ast'] += lcv_item.custom_ast
                item_wise_duty[lcv_item.item_code]['it'] += lcv_item.custom_it
        
    return {'landed_cost_voucher_name':lcv[0],'item_wise_duty':item_wise_duty,'total':{'custom_duty':custom_duty,'acd':acd,'cess':cess,'stamnt':stamnt,'ast':ast,'it':it}}

    
def update_misc_import_charges(import_doc_name):
    # This function will fetch all charges not covered in service invoices
    # For now it ll deal with LC Charges/ Any Exchange Gains/Losses
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    lc_settlements = frappe.get_list("LC Settlement",filters={'import_document':import_doc_name,'docstatus':1},fields=['name','lc_charges','letter_of_credit_to_settle'],ignore_permissions=True
    )
    print(lc_settlements)
    if len(lc_settlements) > 0:
        lc_doc = frappe.get_doc("Letter Of Credit",lc_settlements[0]['letter_of_credit_to_settle'],ignore_permissions=True)
        
        data_dict = {}
        for item in lc_settlements:
            data_dict['document_type'] = 'LC Settlement'
            data_dict['document_name'] = item['name']
            data_dict['import_charge_type'] = "LC Charges"
            data_dict['paid_to'] = lc_doc.issuing_bank
            data_dict['amount'] = item['lc_charges']
            import_doc.append("linked_misc_import_charges",data_dict)

    lcv_data = get_customs_duty(import_doc_name)
 
    custom_data = lcv_data['total']
    
    total_customs_duty = custom_data['custom_duty'] + custom_data['acd']
    total_cess = custom_data['cess']
    lcv_doc = lcv_data['landed_cost_voucher_name']
    
    print(f"lcv data is {lcv_data}")
    print(f"Total Custom Duty is {total_customs_duty}")
    # Only add customs duty entries if there are actual LCV documents
    if total_customs_duty >= 0 and lcv_doc:
        import_doc.append("linked_misc_import_charges", {'import_charge_type':'Customs Duty',
        'amount':total_customs_duty,'document_type':'Landed Cost Voucher','document_name':lcv_doc,
        'paid_to':'Pakistan Customs'})
        print('appended row')
    
    if total_cess > 0 and lcv_doc:
        import_doc.append("linked_misc_import_charges", {'import_charge_type':'Cess',
        'amount':total_cess,'document_type':'Landed Cost Voucher','document_name':lcv_doc,
        'paid_to':'Sindh Excise and Taxation'})
    
    

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
        filters={"custom_import_document": import_doc_name, "docstatus": 1,'is_system_generated':0},ignore_permissions=True,
        fields=["name"]
    )
    
    if not journal_entries:
        #frappe.msgprint(f"No submitted Journal Entries found for ImportDoc {import_doc_name}.")
        return

    # Process each Journal Entry and update misc import charges
    for je in journal_entries:
        je_doc = frappe.get_doc("Journal Entry", je["name"],ignore_permissions=True)
        for account in je_doc.accounts:
            if account.debit_in_account_currency > 0:
                # Prepare misc charges entry
                misc_charge = {
                    "import_charge_type": je_doc.custom_import_charge_type,
                    #"amount": account.debit_in_account_currency - account.credit_in_account_currency,
                    "amount":account.debit_in_account_currency,
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
    #frappe.msgprint(f"Misc import charges updated for ImportDoc {import_doc_name}.")




def bulk_update_import_charges(import_doc_name):
    linked_pi = frappe.get_list("Purchase Invoice",filters={'docstatus':1,"custom_purchase_invoice_type":"Import Service Charges",
                                                               "custom_import_document":import_doc_name},fields=['name'],pluck='name',ignore_permissions=True)

    

    for item in linked_pi:
        
        update_import_charges_in_import(frappe.get_doc("Purchase Invoice",item,ignore_permissions=True))


    #frappe.db.commit()


    




def calculate_total_import_charges(import_doc_name):
    # this function will loop over all ex tax import charges and accumualte them for
    # allocating to item
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    
    total_import_charges = sum(row.amount for row in import_doc.linked_import_charges) or 0
    total_service_sales_tax = sum(row.total_st for row in import_doc.linked_import_charges) or 0
    total_misc_import_charges = sum(row.amount for row in import_doc.linked_misc_import_charges) or 0
    total_invoices_amount = sum(row.total_base_value for row in import_doc.linked_purchase_invoices) or 0
    total_customs_duty = sum(row.amount for row in import_doc.linked_misc_import_charges if row.import_charge_type=="Customs Duty") or 0


    import_doc.total_import_charges = total_import_charges + total_misc_import_charges
    import_doc.total_cost = import_doc.total_import_charges + total_invoices_amount
    import_doc.total_customs_duty = total_customs_duty
    import_doc.sales_tax_on_services = total_service_sales_tax


    import_doc.save()

def get_landed_cost_item(import_doc_name,purchase_receipt_item,ignore_permissions=False):
    """
    This function will return the appropirately landed cost item for PR/PI Item if avialable, to 
    extract the import_related_charges from it
    """
    lcv_item = frappe.get_list("Landed Cost Item",filters={'purchase_receipt_item':purchase_receipt_item,'docstatus':1},fields=['name'],
                               pluck='name',ignore_permissions=True)
    print(f"lcv item is {lcv_item}")

    if len(lcv_item) == 0:
        return None
    return frappe.get_doc("Landed Cost Item",lcv_item[0],ignore_permissions=True)

def allocate_import_charges(import_doc_name):
    # Import Charges Will be allocated proporitanlly as per item amount
    #TODO: This function should striclty be tested for ImportDoc where multiple Items are added
    # TODO: This function shoudl be optimzied the way it pulls the import charges from LCV. 
    
    time.sleep(3)
    print('allocate import charges executed')
    import_doc = frappe.get_doc("ImportDoc",import_doc_name)
    import_taxes_data = get_customs_duty(import_doc_name)
    item_wise_total_duty = import_taxes_data['item_wise_duty']
    print(f"Item Wise Total Duty {item_wise_total_duty}")
    # Update Totals In Import Doc

    import_doc.sales_tax_on_import = import_taxes_data['total']['stamnt']+import_taxes_data['total']['ast']
    import_doc.total_income_tax = import_taxes_data['total']['it']
    import_doc.total_import_value = import_doc.total_cost + import_doc.sales_tax_on_import+import_doc.sales_tax_on_services + import_doc.total_income_tax
    
    # Allocate Charges. Services Sales Tax, will distributed Proporionately to all items
    print(f"ImportDOc Total Import Charges {import_doc.total_import_charges}")
    if import_doc.total_import_charges >= 0:
        total_items_amount = sum(row.amount for row in import_doc.items)
        for item in import_doc.items:
            item_customs_duty = 0
            item_sales_tax = 0
            lcv_item = get_landed_cost_item(import_doc_name,item.purchase_receipt_item,ignore_permissions=True)


            print('starting item wise calculation')
            if item.item_code in item_wise_total_duty.keys():
                print(f"{item.item_code}------")
                item_customs_duty += (item_wise_total_duty[item.item_code]['custom_duty']+item_wise_total_duty[item.item_code]['acd'])
                item_sales_tax += (item_wise_total_duty[item.item_code]['stamnt']+item_wise_total_duty[item.item_code]['ast'])
            item.allocated_charges_ex_cd = (item.amount/total_items_amount * (import_doc.total_import_charges-import_doc.total_customs_duty)) or 0
            item.allocated_import_charges = item_customs_duty + item.allocated_charges_ex_cd
            print(f"item wise Allocated Import Charges EX CD {item.allocated_import_charges_ex_cd}")
            print(f"Allocated Import Charg {item.custom_import_dutu}")
            item.net_unit_cost = (item.allocated_import_charges + item.amount)/item.qty
            print(f" Net unit cost {item.net_unit_cost}")
            item.st_unit_cost = 0
            allocated_service_sales_tax = (item.amount/total_items_amount) * import_doc.sales_tax_on_services
        
            if lcv_item is not None:
                item.assessment_variance = lcv_item.custom_base_assessment_difference
                item.st_unit_cost += ((lcv_item.custom_base_assessed_value + item_customs_duty)/item.qty)
                item.total_unit_cost = (item.amount + item_customs_duty + allocated_service_sales_tax+item.allocated_charges_ex_cd+lcv_item.custom_it+item_sales_tax)/item.qty

                
        total_allocated_charges = sum(item.allocated_import_charges for item in import_doc.items)
        
        assert(round(total_allocated_charges) == round(import_doc.total_import_charges))
        import_doc.sales_tax_on_import = import_taxes_data['total']['stamnt']+import_taxes_data['total']['ast']
        import_doc.total_income_tax = import_taxes_data['total']['it']
        import_doc.total_import_value = import_doc.total_cost + import_doc.sales_tax_on_import+import_doc.sales_tax_on_services + import_doc.total_income_tax
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
        #company = frappe.get_doc("Company", doc.company)
        import_charge_doc = frappe.get_doc("Import Charge Type",doc.custom_import_charge_type)
        
        if import_charge_doc.account_head == None:
            frappe.throw(f"Please set account head in Import Charge - {doc.custom_import_charge_type}")
        unallocated_charges_account = import_charge_doc.account_head

        

        # Update expense head in items
        for item in doc.items:
            #frappe.log_error(message=f"Unallocated Import Account is {unallocated_charges_account}",title="Unalloacated issue")
            item.expense_account = unallocated_charges_account

        # Indicate that the document has been modified
        doc.flags.ignore_validate_update_after_submit = True

def update_purchase_invoices(import_doc_name):
    """
    Update the ImportDoc's linked_purchase_invoices table with related Purchase Invoices.
    Only includes Purchase Invoices that are submitted and of type 'Import'.

    :param import_doc_name: Name of the ImportDoc to update
    """
    # Get list of submitted Import Purchase Invoices linked to this ImportDoc
    linked_pi = frappe.get_list("Purchase Invoice",
        filters={
            'docstatus': 1,
            'custom_purchase_invoice_type': 'Import',
            'custom_import_document': import_doc_name
        },
        fields=['name']
    )
    
    # Get the ImportDoc
    import_doc = frappe.get_doc("ImportDoc", import_doc_name)
    
    # Clear existing linked purchase invoices

    
    # Add each Purchase Invoice to the table
    for pi in linked_pi:
        import_doc.append("linked_purchase_invoices", {
            "purchase_invoice": pi.name
            # Other fields (total_value, total_base_value, party_account_currency)
            # will be auto-fetched due to fetch_from properties in the DocType
        })
    
    # Save the ImportDoc
    import_doc.save()

def update_data_in_import_doc(import_doc_name):
    # Prevent concurrent updates
    updating_status = frappe.db.get_value("ImportDoc", import_doc_name, "custom_updating")
    if updating_status == 1:  # Explicitly check for 1, not truthy
        print("Already updating, skip")
        frappe.log_error(f"ImportDoc {import_doc_name} already being updated", "Duplicate Update Prevented")
        return
    
    # Set updating flag
    frappe.db.set_value("ImportDoc", import_doc_name, "custom_updating", 1)
    frappe.db.commit()
    
    try:
        print("Updating Import Doc")
        doc = frappe.get_doc("ImportDoc", import_doc_name)
        doc.items = []
        doc.linked_import_charges = []
        doc.linked_misc_import_charges = []
        doc.linked_purchase_invoices = []
        doc.save()
        print("Updated Import Doc")
        update_purchase_invoices(import_doc_name)
        update_line_items(import_doc_name)
        bulk_update_import_charges(import_doc_name)
        print("Updated Import Charges")
        doc.reload()
        if doc.linked_purchase_invoices:
            update_misc_import_charges(import_doc_name)
        print("Updated Misc Import Charges")
        update_unallocated_misc_charges_jv(import_doc_name)
        calculate_total_import_charges(import_doc_name)
        print("Updated Total Import Charges")
        if doc.linked_purchase_invoices:
            allocate_import_charges(import_doc_name)
        print("Updated Allocate Import Charges")
    except Exception as e:
        frappe.log_error(f"ImportDoc update failed: {str(e)}", f"ImportDoc {import_doc_name}")
        raise
    finally:
        # Clear updating flag
        frappe.db.set_value("ImportDoc", import_doc_name, "custom_updating", 0)
        frappe.db.commit()
    print("Import Doc updated")


def generate_outstanding_payments_report():
    # Fetch all ImportDoc documents where status is not "Locked"
    import_docs = frappe.get_list("ImportDoc", filters={"status": ["!=", "Locked"]}, fields=["name"])

    report_data = []  # Initialize a list to hold all report rows

    for doc in import_docs:
        import_doc = frappe.get_doc("ImportDoc", doc.name)

        # Calculate Open Expenses
        open_exps = sum(row.amount for row in import_doc.linked_misc_import_charges) or 0

        # Calculate Other Expenses
        other_exp = sum(row.total_st for row in import_doc.linked_import_charges) or 0

        # Calculate LC Total
        lc_total = sum(row.total_value for row in import_doc.linked_purchase_invoices) or 0

        # Concatenate item names into a single string
        item_names = ", ".join(item.item_name for item in import_doc.items)

        # Prepare the report row
        report_row = {
            "ImportDoc": import_doc.name,
            "Items": item_names,
            "LC No.": import_doc.lc_no,
            "Margin": None,  # Ignored for now
            "Open Exps": open_exps,
            "L/CFORM": None,  # Ignored for now
            "AMD": None,  # Ignored for now
            "Other Exp": other_exp,
            "B.BILL": None,  # Ignored for now
            "Shipment": None,  # Ignored for now
            "Expiry": None,  # Ignored for now
            "LC Total": lc_total
        }

        report_data.append(report_row)  # Add the report row to the list

    return report_data  # Return the complete report data



def on_submit_purchase_invoice(doc, method):
    if doc.custom_import_document:
        frappe.db.after_commit.add(
            lambda: update_data_in_import_doc(doc.custom_import_document)
        )

def on_cancel_purchase_invoice(doc, method):
    if doc.custom_import_document:
        frappe.db.after_commit.add(
            lambda: update_data_in_import_doc(doc.custom_import_document)
        )

def on_submit_journal_entry(doc, method):
    if doc.custom_import_document:
        frappe.db.after_commit.add(
            lambda: update_data_in_import_doc(doc.custom_import_document)
        )

def on_cancel_journal_entry(doc, method):
    if doc.custom_import_document:
        frappe.db.after_commit.add(
            lambda: update_data_in_import_doc(doc.custom_import_document)
        )

def on_submit_landed_cost_voucher(doc, method):
    time.sleep(2)
    frappe.db.commit()
    if doc.custom_import_document:
        time.sleep(5)
        print("Updating Import Doc on submit LCV")
        # Create import taxes JVs
        #create_import_taxes_jv(doc.name)
        
        frappe.db.after_commit.add(
            lambda: update_data_in_import_doc(doc.custom_import_document)
        )

def on_cancel_landed_cost_voucher(doc, method):
    if doc.custom_import_document:
        frappe.db.after_commit.add(
            lambda: update_data_in_import_doc(doc.custom_import_document)
        )





def autoname_purchase_invoice(doc, method):
    """
    Autoname Purchase Invoice using fiscal year based on document date.
    Uses existing naming logic, replacing current year with fiscal year name.
    """
    def ensure_unique_name(doctype, base_name):
        """Append -1/-2/... if name exists."""
        candidate = base_name
        counter = 1
        while frappe.db.exists(doctype, candidate):
            candidate = f"{base_name}-{counter}"
            counter += 1
        return candidate
    # Determine fiscal year based on posting_date and company
    fiscal_year_name = None
    try:
        fy_info = erp_get_fiscal_year(doc.posting_date, company=doc.company, as_dict=True)
        # fy_info can be a dict with key 'name' like '2024-2025'
        if isinstance(fy_info, dict):
            fiscal_year_name = fy_info.get('name')
        elif isinstance(fy_info, (list, tuple)) and fy_info:
            fiscal_year_name = fy_info[0]
    except Exception:
        pass

    # Fallback to two-digit current year if fiscal year resolution fails
    if not fiscal_year_name:
        fiscal_year_name = datetime.datetime.now().strftime('%y')

    # Get company abbreviation
    company_abbr = doc.custom_abbr or ''

    # Handle different naming based on purchase invoice type
    if doc.custom_purchase_invoice_type == "Import":
        if doc.custom_import_document:
            import_doc = frappe.get_doc("ImportDoc", doc.custom_import_document)
            if getattr(import_doc, 'gd_no', None):
                base_name = f"{company_abbr}-IPI-{fiscal_year_name}-{import_doc.gd_no}"
                doc.name = ensure_unique_name("Purchase Invoice", base_name)

    elif doc.custom_purchase_invoice_type == "Local Purchase":
        if doc.is_return:
            # Local Purchase Return
            doc.name = make_autoname(f"{company_abbr}-LPI-RTN{fiscal_year_name}-.#####")
        else:
            # Regular Local Purchase
            doc.name = make_autoname(f"{company_abbr}-LPI-{fiscal_year_name}-.#####")

    elif doc.custom_purchase_invoice_type == "Import Service Charges":
        if doc.is_return:
            # Import Service Charges Return
            doc.name = make_autoname(f"{company_abbr}-SC-RTN-{fiscal_year_name}-.#####")
        else:
            # Regular Import Service Charges
            doc.name = make_autoname(f"{company_abbr}-SC-{fiscal_year_name}-.#####")








 
    
    

    

            


        
        




