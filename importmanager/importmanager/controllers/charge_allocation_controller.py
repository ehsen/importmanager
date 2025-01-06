"""
This controller will provide various utility functions to 
handle allocation charges
"""
import frappe
from frappe.utils import flt, nowdate, nowtime
from importmanager.import_utils import create_gl_entries

def create_charge_allocation_gl(posting_date, charges, reference_doc_name,charge_type):
    """
    Creates GL entries for allocated charges on Sales Invoice.

    :param posting_date: Date for the GL Entries (e.g., '2024-12-07').
    :param charges: Total allocated charges.
    :param reference_doc_name: The name of the Sales Invoice (reference for the GL).
    """
    print(f"Hitting Charge allocation GL")
    # Fetch the Company linked to the Sales Invoice
    company = frappe.get_doc("Sales Invoice", reference_doc_name).company

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

    elif charge_type == "Assessment Variance":
        # If postive charges means Assessment > Declared Value
        accounts = [
            # Debit the P&L Account for allocated charges
            {
                "account": default_import_assessment_account,
                "debit": charges,
                "credit": 0,
                
                "party_type": None,
                "party": None,
                "voucher_type": "Sales Invoice",
                "voucher_subtype":"Sales Invoice",
                "against":assessment_variance_charges_account,
                "voucher_no": reference_doc_name
            },
            # Credit the Balance Sheet Account (Unallocated Import Charges)
            {
                "account": assessment_variance_charges_account,
                "debit": 0,
                "credit": charges,
                
                "party_type": None,
                "party": None,
                "voucher_type": "Sales Invoice",
                "voucher_subtype":"Sales Invoice",
                "against":default_import_assessment_account,
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
        
    except Exception as e:
        frappe.log_error(message=str(e), title="Error Updating Allocated Charges")
        raise


def create_charge_allocation_entry_new(entry_type, charge_type,item_code, qty, charges, reference_doc,reference_doc_name):
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
            "charge_type":charge_type,
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": f"{nowdate()} {nowtime()}",
            "item_code": item_code,
            "qty": qty,
            "charges": charges,
            "remaining_qty": qty,
            "remaining_charges": charges,
            "reference_doc": reference_doc,
            "reference_doc_name":reference_doc_name
        }).insert(ignore_permissions=True)

    # Handle 'Allocation' entry
    elif entry_type == "Allocation":
        # Fetch the latest 'Addition' entry for the item
        allocation_sources = frappe.get_all(
            "Charge Allocation Ledger",
            filters={
                "entry_type": "Addition",
                "charge_type":charge_type,
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
            print(f"allocatable qty is {allocatable_qty}")
            charges_per_unit = source_doc.remaining_charges / source_doc.remaining_qty
            allocatable_charges = flt(charges_per_unit * allocatable_qty)

            # Update the source entry
            source_doc.remaining_qty -= allocatable_qty
            source_doc.remaining_charges -= allocatable_charges
            source_doc.save()

            # Update cumulative allocation
            allocated_qty += allocatable_qty
            allocated_charges += allocatable_charges
            print(f"allocated charges are {allocated_charges}")
        # Validate final allocation
        if allocated_qty < qty:
            frappe.throw(f"Insufficient quantity to allocate {qty} for item {item_code}.")

        
        # Create a new Allocation entry
        frappe.get_doc({
            "doctype": "Charge Allocation Ledger",
            "entry_type": entry_type,
            "chage_type":charge_type,
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
        update_allocated_charges(reference_doc_name, item_code, allocated_charges,charge_type) 
        

def create_charge_allocation_entry(entry_type, charge_type, item_code, qty, charges, reference_doc, reference_doc_name):
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

        
        for source in allocation_sources:
           
            if allocated_qty >= qty:
                break
            
            allocatable_qty = min(source["remaining_qty"], qty - allocated_qty)
            
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
                charge_type="Import Charges",
                item_code=item.item_code,
                qty=item.qty,
                charges=0,  # Charges calculation will be handled by the function
                reference_doc="Sales Invoice",
                reference_doc_name=doc.name
            
            )
            frappe.log_error(message=f"Allocation Amount is {item.custom_allocated_charges}",title="Allocation Amount GL ISSUe")  
            create_charge_allocation_gl(posting_date=nowdate(), charges=item.custom_allocated_charges, reference_doc_name=doc.name,charge_type="Import Charges")
            
            # Create Assessment Variance Entry
            # Call the create_charge_allocation_entry function
            create_charge_allocation_entry(
                entry_type="Allocation",
                charge_type="Assessment Variance",
                item_code=item.item_code,
                qty=item.qty,
                charges=0,  # Charges calculation will be handled by the function
                reference_doc="Sales Invoice",
                reference_doc_name=doc.name,
                
            
            )
            frappe.log_error(message=f"Import Assessment Amount is {item.custom_assessment_charges}",title="Assessment Variance GL ISSUe")  
            create_charge_allocation_gl(posting_date=nowdate(), charges=item.custom_assessment_charges, reference_doc_name=doc.name,charge_type="Assessment Variance")
            
        except Exception as e:
            # Log errors to avoid stopping the on_submit process
            frappe.log_error(message=str(e), title="Charge Allocation Error")
            frappe.msgprint(
                f"Failed to create allocation entry for Item: {item.item_code}. Error: {str(e)}",
                alert=True
            )
        
            #create_charge_allocation_gl(posting_date=nowdate(), charges=item.custom_allocated_charges, reference_doc_name=doc.name)


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



    
    


