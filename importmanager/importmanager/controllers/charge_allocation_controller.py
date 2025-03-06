"""
This controller will provide various utility functions to 
handle allocation charges
"""
import frappe
from frappe.utils import flt, nowdate, nowtime
from importmanager.import_utils import create_gl_entries
import time

def create_charge_allocation_gl(posting_date, charges, reference_doc_name, charge_type):
    """
    Creates GL entries for allocated charges on Sales Invoice.
    For returns, reverses the GL entries by swapping debit and credit.

    :param posting_date: Date for the GL Entries (e.g., '2024-12-07').
    :param charges: Total allocated charges.
    :param reference_doc_name: The name of the Sales Invoice (reference for the GL).
    :param charge_type: Type of charge ('Import Charges' or 'Assessment Variance').
    """
    # Fetch the Sales Invoice to check if it's a return
    sales_invoice = frappe.get_doc("Sales Invoice", reference_doc_name)
    is_return = sales_invoice.is_return

    # Fetch the Company linked to the Sales Invoice
    company = sales_invoice.company

    # Fetch the default accounts from the Company document
    company_doc = frappe.get_doc("Company", company)
    unallocated_import_charges_account = company_doc.custom_unallocated_import_charges_account
    default_import_charges_account = company_doc.custom_default_import_charges_account
    default_import_assessment_account = company_doc.custom_assessment_variance_account
    assessment_variance_charges_account = company_doc.custom_default_import_assessment_charge_account

    # Validate if accounts are found
    if not unallocated_import_charges_account or not default_import_charges_account:
        frappe.throw("Required accounts not found in the Company document.")

    if charge_type == "Import Charges":
        # For returns, swap debit and credit
        debit_account = unallocated_import_charges_account if is_return else default_import_charges_account
        credit_account = default_import_charges_account if is_return else unallocated_import_charges_account
        
        accounts = [
            {
                "account": debit_account,
                "debit": charges,
                "credit": 0,
                "party_type": None,
                "party": None,
                "voucher_type": "Sales Invoice",
                "voucher_subtype": "Sales Invoice",
                "against": credit_account,
                "voucher_no": reference_doc_name
            },
            {
                "account": credit_account,
                "debit": 0,
                "credit": charges,
                "party_type": None,
                "party": None,
                "voucher_type": "Sales Invoice",
                "voucher_subtype": "Sales Invoice",
                "against": debit_account,
                "voucher_no": reference_doc_name
            }
        ]

    elif charge_type == "Assessment Variance":
        # For returns, swap debit and credit
        debit_account = assessment_variance_charges_account if is_return else default_import_assessment_account
        credit_account = default_import_assessment_account if is_return else assessment_variance_charges_account
        
        accounts = [
            {
                "account": debit_account,
                "debit": charges,
                "credit": 0,
                "party_type": None,
                "party": None,
                "voucher_type": "Sales Invoice",
                "voucher_subtype": "Sales Invoice",
                "against": credit_account,
                "voucher_no": reference_doc_name
            },
            {
                "account": credit_account,
                "debit": 0,
                "credit": charges,
                "party_type": None,
                "party": None,
                "voucher_type": "Sales Invoice",
                "voucher_subtype": "Sales Invoice",
                "against": debit_account,
                "voucher_no": reference_doc_name
            }
        ]

    try:
        create_gl_entries(posting_date, accounts, company)
        frappe.msgprint(f"GL Entries created for Sales Invoice: {reference_doc_name}")
    except Exception as e:
        frappe.log_error(message=str(e), title="GL Entries Error")
        frappe.msgprint(f"Failed to create GL entries for Sales Invoice: {reference_doc_name}. Error: {str(e)}", alert=True)


def update_allocated_charges(sales_invoice_name, item_code, charges,charge_type):
    """
    Update the allocated_charges field in the Sales Invoice Item using frappe.db.set_value.

    :param sales_invoice_name: Name of the Sales Invoice (parent).
    :param item_code: The item code for which allocated charges need to be updated.
    :param charges: The charge amount to update.
    """
    
    try:
        if charge_type == "Import Charges":
        # Update the allocated_charges field
            frappe.db.set_value(
                "Sales Invoice Item",
                {"parent": sales_invoice_name, "item_code": item_code},
                "custom_allocated_charges",
                charges
            )
        elif charge_type == "Assessment Variance":
            frappe.db.set_value(
                "Sales Invoice Item",
                {"parent": sales_invoice_name, "item_code": item_code},
                "custom_assessment_charges",
                charges
            )
        
        frappe.db.commit()
        time.sleep(1) # to handle 
        
    except Exception as e:
        frappe.log_error(message=str(e), title="Error Updating Allocated Charges")
        raise



        

def create_charge_allocation_entry_backup(entry_type, charge_type, item_code, qty, charges, reference_doc, reference_doc_name):
    """
    Creates an entry in the Charge Allocation Ledger.

    :param entry_type: 'Addition' or 'Allocation'.
    :param charge_type: Type of charge ('Import' or 'Assessment').
    :param item_code: Item for which the entry is being made.
    :param qty: Quantity involved.
    :param charges: Charges to be added/allocated.
    :param reference_doc: Reference document causing the ledger update.
    :param reference_doc_name: Reference document name.
    """
    print('called allocation function')

    if entry_type not in ["Addition", "Allocation"]:
        frappe.throw("Invalid entry type. Must be 'Addition' or 'Allocation'.")

    if entry_type == "Addition":
        frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "charge_type": charge_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": qty,
            "charges": charges,
            "remaining_qty": qty,
            "remaining_charges": charges,
            "reference_doc": reference_doc,
            "reference_doc_name": reference_doc_name
        }).insert(ignore_permissions=True)

    elif entry_type == "Allocation":
        print("allocation section called")
        # Fetch non-canceled allocation sources
        allocation_sources = frappe.get_all(
            "Charge Allocation Ledger",
            filters={
                "entry_type": "Addition",
                "charge_type": charge_type,
                "item_code": item_code,
                "remaining_qty": [">", 0],
                "is_cancelled": 0
            },
            fields=["name", "remaining_qty", "remaining_charges"],
            order_by="posting_datetime asc"
        )
    
        if not allocation_sources:
            pass # Most likely all allocated charges are exhausted now.

        allocated_qty = 0
        allocated_charges = 0
        source_references = []

        print(f"Allocation sources are {allocation_sources}")
        for source in allocation_sources:
            print(f"Current Source is {source}")
            if allocated_qty >= qty:
                break
            
            allocatable_qty = min(source["remaining_qty"], qty - allocated_qty)
            print(f"allocatable_qty is {allocatable_qty} qty = {qty} allocated_qty={allocated_qty}")
            charges_per_unit = source["remaining_charges"] / source["remaining_qty"]
            allocatable_charges = flt(charges_per_unit * allocatable_qty)
            source_references.append({
                "source_entry": source["name"],
                "allocated_qty": allocatable_qty,
                "allocated_charges": allocatable_charges,
                "charge_type":charge_type
            })

            allocated_qty += allocatable_qty
            allocated_charges += allocatable_charges

        if allocated_qty < qty:
            frappe.throw(f"Insufficient quantity to allocate {qty} for item {item_code}.")

        # Create Allocation Entry
        allocation_entry = frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "charge_type": charge_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": allocated_qty,
            "charges": allocated_charges,
            "source_references": source_references,  # Storing source references
            "reference_doc": reference_doc,
            "reference_doc_name": reference_doc_name,
            "is_cancelled": 0
        })
        allocation_entry.insert(ignore_permissions=True)

        # Mark allocation for cancellation if needed
        for source_ref in source_references:
            source_doc = frappe.get_doc("Charge Allocation Ledger", source_ref["source_entry"])
            source_doc.remaining_qty -= source_ref["allocated_qty"]
            source_doc.remaining_charges -= source_ref["allocated_charges"]
            source_doc.save()

        print("going to update sales invoice")
        # Update the Sales Invoice Item
        update_allocated_charges(reference_doc_name, item_code, allocated_charges, charge_type)

# For cancellation:
def cancel_allocation(reference_doc_name):
    """
    Marks all allocation entries for the given reference_doc_name as canceled.

    :param reference_doc_name: Name of the reference document.
    """
    allocations = frappe.get_all(
        "Charge Allocation Ledger",
        filters={
            "reference_doc_name": reference_doc_name,
            "entry_type": "Allocation",
            "is_cancelled": 0
        },
        fields=["name"]
    )

    for allocation in allocations:
        allocation_doc = frappe.get_doc("Charge Allocation Ledger", allocation["name"])
        allocation_doc.is_cancelled = 1
        allocation_doc.save()

        # Recalculate remaining quantities and charges in source entries
        if allocation_doc.source_references:
            for source_ref in allocation_doc.source_references:
                source_doc = frappe.get_doc("Charge Allocation Ledger", source_ref["source_entry"])
                source_doc.remaining_qty += source_ref["allocated_qty"]
                source_doc.remaining_charges += source_ref["allocated_charges"]
                source_doc.save()


def get_last_allocation(item_code,charge_type):
    last_allocation_entry = frappe.get_all(
            "Charge Allocation Ledger",
            filters={
                "entry_type": "Allocation",
                "charge_type":charge_type,
                "item_code": item_code,
                "is_cancelled": 0
            },
            order_by="posting_datetime desc",
            limit=1,
            fields=["charges", "qty", "source_references"]
        )

def calculate_allocation_charges(item_code, qty, charge_type, entry_type="Allocation"):
    """
    Calculate allocation charges for an item, handling both allocations and returns.
    
    Args:
        item_code (str): The item code to calculate charges for
        qty (float): Quantity to allocate
        charge_type (str): Either "Import Charges" or "Assessment Variance"
        entry_type (str): "Allocation" or "Return"
        
    Returns:
        float: The calculated allocation charges
    """
    try:
        if entry_type == "Return":
            # Fetch all relevant allocation entries for the item
            allocation_entries = frappe.get_all(
                "Charge Allocation Ledger",
                filters={
                    "entry_type": "Allocation",
                    "charge_type": charge_type,
                    "item_code": item_code,
                    "is_cancelled": 0
                },
                order_by="posting_datetime desc",  # Most recent first
                fields=["name", "charges", "qty"]
            )

            if not allocation_entries:
                frappe.throw(f"No previous allocation entries found for item {item_code}.")

            remaining_return_qty = abs(qty)  # Work with absolute value for calculations
            total_return_charges = 0

            for allocation in allocation_entries:
                if remaining_return_qty <= 0:
                    break

                alloc_doc = frappe.get_doc("Charge Allocation Ledger", allocation.name)
                per_unit_charge = alloc_doc.charges / alloc_doc.qty if alloc_doc.qty > 0 else 0
                
                # Calculate how much quantity we can return from this allocation
                returnable_qty = min(remaining_return_qty, alloc_doc.qty)
                return_charges = per_unit_charge * returnable_qty
                
                total_return_charges += return_charges
                remaining_return_qty -= returnable_qty

            if remaining_return_qty > 0:
                frappe.throw(f"Cannot find enough allocation entries to return {qty} units of item {item_code}")

            # Make the total charges negative since this is a return
            total_return_charges = -1 * total_return_charges
            return total_return_charges
        
        else:
            # For allocations, fetch from Addition entries
            allocation_sources = frappe.get_all(
                "Charge Allocation Ledger",
                filters={
                    "entry_type": "Addition",
                    "charge_type": charge_type,
                    "item_code": item_code,
                    "remaining_qty": [">", 0],
                    "is_cancelled": 0
                },
                fields=["name", "remaining_qty", "remaining_charges"],
                order_by="posting_datetime asc"  # Oldest additions first for FIFO
            )

        if not allocation_sources:
            frappe.log_error(
                message=f"No {entry_type.lower()} sources found for {item_code} with {charge_type}",
                title="Charge Allocation Warning"
            )
            return 0

        allocated_qty = 0
        allocated_charges = 0

        for source in allocation_sources:
            if allocated_qty >= qty:
                break
            
            allocatable_qty = min(source["remaining_qty"], qty - allocated_qty)
            charges_per_unit = source["remaining_charges"] / source["remaining_qty"]
            allocatable_charges = flt(charges_per_unit * allocatable_qty)

            allocated_qty += allocatable_qty
            allocated_charges += allocatable_charges

        if allocated_qty < qty:
            frappe.log_error(
                message=(
                    f"Partial {entry_type.lower()} for {item_code}:\n"
                    f"Requested Qty: {qty}\n"
                    f"Allocated Qty: {allocated_qty}\n"
                    f"Charge Type: {charge_type}\n"
                    f"Allocated Charges: {allocated_charges}"
                ),
                title=f"Partial Charge {entry_type} Warning"
            )

        # For returns, the charges should be negative
        if entry_type == "Return":
            allocated_charges = -1 * allocated_charges

        return allocated_charges

    except Exception as e:
        frappe.log_error(
            message=f"Error calculating {entry_type.lower()} charges: {str(e)}",
            title=f"Charge {entry_type} Calculation Error"
        )
        raise

def create_charge_allocation_entry(entry_type, charge_type, item_code, qty, charges, reference_doc, reference_doc_name):
    """
    Creates an entry in the Charge Allocation Ledger.

    :param entry_type: 'Addition', 'Allocation', or 'Return'.
    :param charge_type: Type of charge ('Import' or 'Assessment').
    :param item_code: Item for which the entry is being made.
    :param qty: Quantity involved.
    :param charges: Charges to be added/allocated.
    :param reference_doc: Reference document causing the ledger update.
    :param reference_doc_name: Reference document name.
    """
    print('called allocation function')

    print(f"entry type is {entry_type}")
    if entry_type not in ["Addition", "Allocation", "Return"]:
        frappe.throw("Invalid entry type. Must be 'Addition', 'Allocation', or 'Return'.")

    if entry_type == "Return":
        # Fetch the last Allocation entry for the same item code
        last_allocation_entry = frappe.get_all(
            "Charge Allocation Ledger",
            filters={
                "entry_type": "Allocation",
                "charge_type":charge_type,
                "item_code": item_code,
                "is_cancelled": 0
            },
            order_by="posting_datetime desc",
            limit=1,
            fields=["name","charges", "qty", "source_references"]
        )

        if not last_allocation_entry:
            print(f"no allocation entry foud for {charge_type}")
            frappe.throw(f"No previous allocation entry found for item {item_code}.")

        last_entry = last_allocation_entry[0]
        print(f"Last allocation entry is {last_entry}")
        last_entry = frappe.get_doc("Charge Allocation Ledger",last_entry['name'])
        print(f"last entry references is {last_entry.source_references}")
        per_unit_charge = last_entry.charges / last_entry.qty if last_entry.qty > 0 else 0
        print(f"per unit charge is {per_unit_charge}")
        total_return_charges = per_unit_charge * qty
        frappe.log_error(message=f"total return charges are {total_return_charges}",title="total return charges")
        # Handle 'Return' entry
        frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "charge_type": charge_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": qty,  # Negative quantity for return
            "charges": total_return_charges,  # Negative charges for return
            "reference_doc": reference_doc,
            "reference_doc_name": reference_doc_name
        }).insert(ignore_permissions=True)

        # Update the Sales Invoice Item for return
        #update_allocated_charges(reference_doc_name, item_code, -total_return_charges, charge_type)  # Deduct charges
        
        # Increase the source document's remaining quantity and charges
        if len(last_entry.source_references)>0:
            
            
            # Get the first source reference
            source_reference = last_entry.source_references[0]
            
            source_doc = frappe.get_doc("Charge Allocation Ledger", source_reference.source_entry)
            source_doc.remaining_qty += abs(qty)  # Increase remaining quantity
            source_doc.remaining_charges += abs(total_return_charges)  # Increase remaining charges
            source_doc.save()
        else:
            frappe.log_error(message=f"No source references found in the last allocation entry for item {item_code}.", title="Return Allocation Warning")

    elif entry_type == "Addition":
        # Existing logic for Addition
        frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "charge_type": charge_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": qty,
            "charges": charges,
            "remaining_qty": qty,
            "remaining_charges": charges,
            "reference_doc": reference_doc,
            "reference_doc_name": reference_doc_name
        }).insert(ignore_permissions=True)

    elif entry_type == "Allocation":
        # Existing logic for Allocation
        print("allocation section called")
        # Fetch non-canceled allocation sources
        allocation_sources = frappe.get_all(
            "Charge Allocation Ledger",
            filters={
                "entry_type": "Addition",
                "charge_type": charge_type,
                "item_code": item_code,
                "remaining_qty": [">", 0],
                "is_cancelled": 0
            },
            fields=["name", "remaining_qty", "remaining_charges"],
            order_by="posting_datetime asc"
        )
    
        if not allocation_sources:
            pass # Most likely all allocated charges are exhausted now.

        allocated_qty = 0
        allocated_charges = 0
        source_references = []

        print(f"Allocation sources are {allocation_sources}")
        for source in allocation_sources:
            print(f"Current Source is {source}")
            if allocated_qty >= qty:
                break
            
            allocatable_qty = min(source["remaining_qty"], qty - allocated_qty)
            print(f"allocatable_qty is {allocatable_qty} qty = {qty} allocated_qty={allocated_qty}")
            charges_per_unit = source["remaining_charges"] / source["remaining_qty"]
            allocatable_charges = flt(charges_per_unit * allocatable_qty)
            source_references.append({
                "source_entry": source["name"],
                "allocated_qty": allocatable_qty,
                "allocated_charges": allocatable_charges,
                "charge_type": charge_type
            })

            allocated_qty += allocatable_qty
            allocated_charges += allocatable_charges

        if allocated_qty < qty:
            frappe.throw(f"Insufficient quantity to allocate {qty} for item {item_code}.")

        # Create Allocation Entry
        allocation_entry = frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "charge_type": charge_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": allocated_qty,
            "charges": allocated_charges,
            "source_references": source_references,  # Storing source references
            "reference_doc": reference_doc,
            "reference_doc_name": reference_doc_name,
            "is_cancelled": 0
        })
        allocation_entry.insert(ignore_permissions=True)

        # Mark allocation for cancellation if needed
        for source_ref in source_references:
            source_doc = frappe.get_doc("Charge Allocation Ledger", source_ref["source_entry"])
            source_doc.remaining_qty -= source_ref["allocated_qty"]
            source_doc.remaining_charges -= source_ref["allocated_charges"]
            source_doc.save()

        print("going to update sales invoice")
        # Update the Sales Invoice Item
        #update_allocated_charges(reference_doc_name, item_code, allocated_charges, charge_type)
        

def create_line_wise_charge_entry(import_doc):
    # This will loop over all ImportDoc Items and create Charge Entries
    
    print(import_doc.name)
    for item in import_doc.items:
        create_charge_allocation_entry("Addition",item.item_code,item.qty,
                                       item.allocated_charges_ex_cd,"ImportDoc",import_doc.name)





def on_submit_create_allocation_entries(doc, method):
    """
    Hook function triggered on the 'on_submit' event of a Sales Invoice.
    """
    entry_type = "Return" if doc.is_return == 1 else "Allocation"
    
    for item in doc.items:
        try:
            # Calculate charges first
            import_charges = calculate_allocation_charges(
                item_code=item.item_code,
                qty=item.qty,
                charge_type="Import Charges",
                entry_type=entry_type  # Pass the entry type to handle returns properly
            )
            
            assessment_charges = calculate_allocation_charges(
                item_code=item.item_code,
                qty=item.qty,
                charge_type="Assessment Variance",
                entry_type=entry_type  # Pass the entry type to handle returns properly
            )
            
            # Process import charges (both positive and negative)
            if import_charges != 0:  # Changed from > 0 to != 0
                create_charge_allocation_entry(
                    entry_type=entry_type,
                    charge_type="Import Charges",
                    item_code=item.item_code,
                    qty=item.qty,
                    charges=import_charges,
                    reference_doc="Sales Invoice",
                    reference_doc_name=doc.name
                )
                create_charge_allocation_gl(
                    posting_date=doc.posting_date,
                    charges=abs(import_charges),  # Use absolute value for GL
                    reference_doc_name=doc.name,
                    charge_type="Import Charges"
                )
            
            # Process assessment charges (both positive and negative)
            if assessment_charges != 0:  # Changed from > 0 to != 0
                create_charge_allocation_entry(
                    entry_type=entry_type,
                    charge_type="Assessment Variance",
                    item_code=item.item_code,
                    qty=item.qty,
                    charges=assessment_charges,
                    reference_doc="Sales Invoice",
                    reference_doc_name=doc.name
                )
                create_charge_allocation_gl(
                    posting_date=doc.posting_date,
                    charges=abs(assessment_charges),  # Use absolute value for GL
                    reference_doc_name=doc.name,
                    charge_type="Assessment Variance"
                )
            
            # Update Sales Invoice Item after everything else is done
            # For returns, the charges are already negative from calculate_allocation_charges
            update_allocated_charges(doc.name, item.item_code, import_charges, "Import Charges")
            update_allocated_charges(doc.name, item.item_code, assessment_charges, "Assessment Variance")
            
        except Exception as e:
            frappe.log_error(message=str(e), title=f"Allocation Error - {item.item_code}")
            frappe.throw(f"Failed to process item {item.item_code}: {str(e)}")


def on_submit_import_doc(doc, method):
    """
    Hook function executed on submission of ImportDoc.
    
    Processes each item in the ImportDoc to create charge allocation entries
    for `custom_base_assessment_difference` and `allocated_charges_ex_cd`.
    """
    for item in doc.items:
        purchase_receipt_item = item.purchase_receipt_item

        if not purchase_receipt_item:
            frappe.throw(f"Purchase Receipt Item not found for Item {item.item_code} in ImportDoc {doc.name}.")

        # Fetch the linked Landed Cost Item for the Purchase Receipt Item
        landed_cost_item = frappe.db.get_value(
            "Landed Cost Item",
            {"purchase_receipt_item": purchase_receipt_item, "docstatus": 1},
            ["custom_base_assessment_difference"]
        )

        if not landed_cost_item:
            frappe.throw(f"Landed Cost Item not found or not submitted for Purchase Receipt Item {purchase_receipt_item}.")

        custom_base_assessment_difference = flt(landed_cost_item)
        allocated_charges_ex_cd = flt(item.allocated_charges_ex_cd)

        # Validate charges
        if custom_base_assessment_difference <= 0 and allocated_charges_ex_cd <= 0:
            frappe.throw(f"No charges available for Item {item.item_code} in ImportDoc {doc.name}.")

        # Create charge allocation entry for `custom_base_assessment_difference`
        if custom_base_assessment_difference > 0:
            create_charge_allocation_entry(
                entry_type="Addition",
                charge_type="Assessment Variance",
                item_code=item.item_code,
                qty=item.qty,
                charges=custom_base_assessment_difference,
                reference_doc="ImportDoc",
                reference_doc_name=doc.name
            )

        # Create charge allocation entry for `allocated_charges_ex_cd`
        if allocated_charges_ex_cd > 0:
            create_charge_allocation_entry(
                entry_type="Addition",
                charge_type="Import Charges",
                item_code=item.item_code,
                qty=item.qty,
                charges=allocated_charges_ex_cd,
                reference_doc="ImportDoc",
                reference_doc_name=doc.name
            )


def repost_import_charges(import_doc_name, item_code, new_charges):
    """
    Handles changes in allocated_charges_ex_cd after ImportDoc submission.
    Creates new allocation entries based on the difference in charges.
    
    :param import_doc_name: Name of the ImportDoc
    :param item_code: Item code for which charges are being adjusted
    :param new_charges: New total charges amount
    """
    # Get original Addition entry
    original_addition = frappe.get_all(
        "Charge Allocation Ledger",
        filters={
            "reference_doc": "ImportDoc",
            "reference_doc_name": import_doc_name,
            "item_code": item_code,
            "entry_type": "Addition",
            "charge_type": "Import Charges",
            "is_cancelled": 0
        },
        fields=["name", "charges", "qty"],
        limit=1
    )

    if not original_addition:
        frappe.throw(f"No original Addition entry found for {item_code} in ImportDoc {import_doc_name}")

    original_entry = original_addition[0]
    charge_difference = new_charges - original_entry.charges

    if charge_difference <= 0:
        # If there is no increase in charges, no action is needed
        return

    # Create a new Addition entry for the increased charges
    create_charge_allocation_entry(
        entry_type="Addition",
        charge_type="Import Charges",
        item_code=item_code,
        qty=original_entry.qty,
        charges=charge_difference,
        reference_doc="ImportDoc",
        reference_doc_name=import_doc_name
    )

    # Get all allocation entries that have this Addition entry as a source
    allocation_entries = frappe.get_all(
        "Charge Allocation Ledger",
        filters={
            "entry_type": "Allocation",
            "charge_type": "Import Charges",
            "is_cancelled": 0
        },
        fields=["name"]
    )

    # Filter allocations that use our specific Addition entry as source
    existing_allocations = []
    for alloc in allocation_entries:
        allocation_doc = frappe.get_doc("Charge Allocation Ledger", alloc.name)
        for source_ref in allocation_doc.source_references:
            if source_ref.source_entry == original_addition[0].name:
                existing_allocations.append({
                    "name": allocation_doc.name,
                    "qty": source_ref.allocated_qty,
                    "charges": source_ref.allocated_charges,
                    "reference_doc": allocation_doc.reference_doc,
                    "reference_doc_name": allocation_doc.reference_doc_name,
                    "source_reference": source_ref
                })
                break

    if not existing_allocations:
        # If no allocations exist, we are done after creating the addition entry
        return

    # Use the original quantity from the ImportDoc for calculating additional charge per unit
    total_original_qty = original_entry.qty  # This is the original quantity from the Addition entry

    # Calculate the additional charge per unit
    additional_charge_per_unit = charge_difference / total_original_qty if total_original_qty > 0 else 0

    # Allocate the additional charges to existing allocations
    for allocation in existing_allocations:
        # Create new allocation entry for the additional charge per unit
        create_charge_allocation_entry(
            entry_type="Allocation",
            charge_type="Import Charges",
            item_code=item_code,
            qty=allocation["qty"],
            charges=additional_charge_per_unit * allocation["qty"],
            reference_doc=allocation["reference_doc"],
            reference_doc_name=allocation["reference_doc_name"]
        )

        # Update allocated charges in the reference document (e.g., Sales Invoice)
        if allocation["reference_doc"] == "Sales Invoice":
            current_charges = frappe.db.get_value(
                "Sales Invoice Item",
                {"parent": allocation["reference_doc_name"], "item_code": item_code},
                "custom_allocated_charges"
            ) or 0
            
            update_allocated_charges(
                allocation["reference_doc_name"],
                item_code,
                current_charges + (additional_charge_per_unit * allocation["qty"]),
                "Import Charges"
            )

            # Create GL entries for the additional charges
            create_charge_allocation_gl(
                posting_date=nowdate(),
                charges=(additional_charge_per_unit * allocation["qty"]),
                reference_doc_name=allocation["reference_doc_name"],
                charge_type="Import Charges"
            )



    
    


