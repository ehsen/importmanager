"""
This controller will provide various utility functions to 
handle allocation charges
"""
import frappe
from frappe.utils import flt, nowdate, nowtime
from importmanager.import_utils import create_gl_entries

def create_charge_allocation_gl(posting_date, charges, reference_doc_name):
    """
    Creates GL entries for allocated charges on Sales Invoice.

    :param posting_date: Date for the GL Entries (e.g., '2024-12-07').
    :param charges: Total allocated charges.
    :param reference_doc_name: The name of the Sales Invoice (reference for the GL).
    """
    # Fetch the Company linked to the Sales Invoice
    company = frappe.get_doc("Sales Invoice", reference_doc_name).company

    # Fetch the default accounts from the Company document
    company_doc = frappe.get_doc("Company", company)
    unallocated_import_charges_account = company_doc.custom_unallocated_import_charges_account
    default_import_charges_account = company_doc.custom_default_import_charges_account

    # Validate if accounts are found
    if not unallocated_import_charges_account or not default_import_charges_account:
        frappe.throw("Required accounts not found in the Company document.")

    # Prepare GL Entry details
    accounts = [
        # Debit the P&L Account for allocated charges
        {
            "account": default_import_charges_account,
            "debit": charges,
            "credit": 0,
            
            "party_type": None,
            "party": None,
            "voucher_type": "Sales Invoice",
            "voucher_subtype":"Sales Invoice",
            "against":unallocated_import_charges_account,
            "voucher_no": reference_doc_name
        },
        # Credit the Balance Sheet Account (Unallocated Import Charges)
        {
            "account": unallocated_import_charges_account,
            "debit": 0,
            "credit": charges,
            
            "party_type": None,
            "party": None,
            "voucher_type": "Sales Invoice",
            "voucher_subtype":"Sales Invoice",
            "against":default_import_charges_account,
            "voucher_no": reference_doc_name
        }
    ]

    #TODO: Add assertion here that debit and credits are equal or use erpnext default function

    # Call the function to create GL entries
    try:
        create_gl_entries(posting_date, accounts,company)
        frappe.msgprint(f"GL Entries created for Sales Invoice: {reference_doc_name}")
    except Exception as e:
        # Log the error if GL entries creation fails
        frappe.log_error(message=str(e), title="GL Entries Error")
        frappe.msgprint(f"Failed to create GL entries for Sales Invoice: {reference_doc_name}. Error: {str(e)}", alert=True)


def update_allocated_charges(sales_invoice_name, item_code, charges):
    """
    Update the allocated_charges field in the Sales Invoice Item using frappe.db.set_value.

    :param sales_invoice_name: Name of the Sales Invoice (parent).
    :param item_code: The item code for which allocated charges need to be updated.
    :param charges: The charge amount to update.
    """
    print(f"allocated charges are {charges}")
    try:
        # Update the allocated_charges field
        frappe.db.set_value(
            "Sales Invoice Item",
            {"parent": sales_invoice_name, "item_code": item_code},
            "custom_allocated_charges",
            charges
        )
        frappe.db.commit()
        frappe.msgprint(f"Allocated charges updated for Item: {item_code} in Sales Invoice: {sales_invoice_name}.")
    except Exception as e:
        frappe.log_error(message=str(e), title="Error Updating Allocated Charges")
        frappe.throw(f"Could not update allocated charges for Item: {item_code}. Error: {str(e)}")


def create_charge_allocation_entry(entry_type, item_code, qty, charges, reference_doc,reference_doc_name):
    """
    Creates an entry in the Charge Allocation Ledger.
    
    :param entry_type: 'Addition' or 'Allocation'.
    :param item_code: Item for which the entry is being made.
    :param qty: Quantity involved.
    :param charges: Charges to be added/allocated.
    :param reference_doc: Reference document causing the ledger update.
    """
    if entry_type not in ["Addition", "Allocation"]:
        frappe.throw("Invalid entry type. Must be 'Addition' or 'Allocation'.")

    # Handle 'Addition' entry
    if entry_type == "Addition":
        frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": qty,
            "charges": charges,
            "remaining_qty": qty,
            "remaining_charges": charges,
            "reference_doc": reference_doc,
        }).insert(ignore_permissions=True)

    # Handle 'Allocation' entry
    elif entry_type == "Allocation":
        # Fetch the latest 'Addition' entry for the item
        allocation_sources = frappe.get_all(
            "Charge Allocation Ledger",
            filters={
                "entry_type": "Addition",
                "item_code": item_code,
                "remaining_qty": [">", 0]
            },
            fields=["name", "remaining_qty", "remaining_charges"],
            order_by="posting_datetime asc"  # Use FIFO method
        )

        if not allocation_sources:
            frappe.throw(f"No remaining charges to allocate for item {item_code}.")

        allocated_qty = 0
        allocated_charges = 0

        # Allocate charges from multiple sources if necessary
        for source in allocation_sources:
            if allocated_qty >= qty:
                break

            source_doc = frappe.get_doc("Charge Allocation Ledger", source["name"])

            # Calculate allocation from this source
            allocatable_qty = min(source_doc.remaining_qty, qty - allocated_qty)
            charges_per_unit = source_doc.remaining_charges / source_doc.remaining_qty
            allocatable_charges = flt(charges_per_unit * allocatable_qty)

            # Update the source entry
            source_doc.remaining_qty -= allocatable_qty
            source_doc.remaining_charges -= allocatable_charges
            source_doc.save()

            # Update cumulative allocation
            allocated_qty += allocatable_qty
            allocated_charges += allocatable_charges

        # Validate final allocation
        if allocated_qty < qty:
            frappe.throw(f"Insufficient quantity to allocate {qty} for item {item_code}.")

        
        # Create a new Allocation entry
        frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": allocated_qty,
            "charges": allocated_charges,
            "reference_doc": reference_doc,
            "reference_doc_name":reference_doc_name
        }).insert(ignore_permissions=True)

        # Update the Sales Invoice Item
    update_allocated_charges(reference_doc_name, item_code, charges) 
        

def create_line_wise_charge_entry(import_doc):
    # This will loop over all ImportDoc Items and create Charge Entries
    
    print(import_doc.name)
    for item in import_doc.items:
        create_charge_allocation_entry("Addition",item.item_code,item.qty,
                                       item.allocated_charges_ex_cd,"ImportDoc",import_doc.name)





def on_submit_create_allocation_entries(doc, method):
    """
    Hook function triggered on the 'on_submit' event of a Sales Invoice.
    Creates allocation charge entries for each item in the Sales Invoice using the allocation charge function.

    :param doc: The Sales Invoice document that triggered the hook.
    :param method: The method triggering the hook (standard Frappe hook parameter).
    """
    for item in doc.items:
        try:
            # Call the create_charge_allocation_entry function
            create_charge_allocation_entry(
                entry_type="Allocation",
                item_code=item.item_code,
                qty=item.qty,
                charges=0,  # Charges calculation will be handled by the function
                reference_doc="Sales Invoice",
                reference_doc_name=doc.name
            
            )
        except Exception as e:
            # Log errors to avoid stopping the on_submit process
            frappe.log_error(message=str(e), title="Charge Allocation Error")
            frappe.msgprint(
                f"Failed to create allocation entry for Item: {item.item_code}. Error: {str(e)}",
                alert=True
            )
        
            create_charge_allocation_gl(posting_date=nowdate(), charges=item.custom_allocated_charges, reference_doc_name=doc.name)
    
    


