# Copyright (c) 2025, SpotLedger
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = generate_outstanding_lc_report(filters)
    return columns, data


def get_columns():
    return [
        {"label": "ImportDoc", "fieldname": "ImportDoc", "fieldtype": "Data", "width": 120},
        {"label": "Items", "fieldname": "Items", "fieldtype": "Data", "width": 200},
        {"label": "LC No.", "fieldname": "LC No.", "fieldtype": "Data", "width": 120},
        {"label": "Margin", "fieldname": "Margin", "fieldtype": "Data", "width": 100},
        {"label": "Misc Import Charges", "fieldname": "Misc Import Charges", "fieldtype": "Currency", "width": 150},
        {"label": "Service Invoice Charges", "fieldname": "Service Invoice Charges", "fieldtype": "Currency", "width": 180},
        {"label": "Duties and Taxes", "fieldname": "Duties and Taxes", "fieldtype": "Currency", "width": 150},
        {"label": "Total Outstanding Expenses", "fieldname": "Total Outstanding Expenses", "fieldtype": "Currency", "width": 200},
        {"label": "LC Amount", "fieldname": "LC Amount", "fieldtype": "Currency", "width": 120},
        {"label": "Currency", "fieldname": "Currency", "fieldtype": "Data", "width": 100},
    ]


def generate_outstanding_lc_report(filters):
    report_data = []

    # Fetch ImportDocs that are not "Locked"
    import_docs = frappe.get_list("ImportDoc", filters={"status": ["!=", "Locked"]}, fields=["name"])

    for doc in import_docs:
        import_doc = frappe.get_doc("ImportDoc", doc.name)

        # Skip if any clearing PI is found
        if has_clearing_purchase_invoice(import_doc):
            continue

        # Get currency from linked PO
        currency = "N/A"
        po = None
        if import_doc.linked_purchase_order:
            try:
                po = frappe.get_doc("Purchase Order", import_doc.linked_purchase_order)
                currency = po.currency
            except Exception as e:
                frappe.log_error(f"Error retrieving PO {import_doc.linked_purchase_order}: {str(e)}", "LC Report")

        # Calculate charges
        misc_charges = sum(row.amount for row in import_doc.get("linked_misc_import_charges") or [])
        service_charges = sum(row.total_incl_tax for row in import_doc.get("linked_import_charges") or [])
        duties_and_taxes = 0  # Placeholder for future logic
        total_outstanding = misc_charges + service_charges + duties_and_taxes

        # Calculate LC amount from only non-clearing PIs
        lc_amount = 0
        for pi_ref in import_doc.get("linked_purchase_invoices") or []:
            try:
                pi = frappe.get_doc("Purchase Invoice", pi_ref.purchase_invoice)
                if not (
                    pi.get("custom_purchase_invoice_type") == "Import"
                    and pi.docstatus == 1
                    and pi.update_stock == 1
                ):
                    lc_amount += pi.get("total", 0)
            except Exception as e:
                frappe.log_error(f"Error reading PI {pi_ref.purchase_invoice}: {str(e)}", "LC Report")

        # ✅ Get item names from linked PO (not from ImportDoc)
        item_names = ""
        if po:
            try:
                item_names = ", ".join([item.item_name for item in po.get("items", []) if item.item_name])
            except Exception as e:
                frappe.log_error(f"Error getting items from PO {po.name}: {str(e)}", "LC Report")

        # Prepare report row
        report_row = {
            "ImportDoc": import_doc.name,
            "Items": item_names,
            "LC No.": import_doc.lc_no,
            "Margin": None,
            "Misc Import Charges": misc_charges,
            "Service Invoice Charges": service_charges,
            "Duties and Taxes": duties_and_taxes,
            "Total Outstanding Expenses": total_outstanding,
            "LC Amount": lc_amount,
            "Currency": currency,
        }

        report_data.append(report_row)

    return report_data


def has_clearing_purchase_invoice(import_doc):
    """
    Returns True if any linked Purchase Invoice satisfies:
    - custom_purchase_invoice_type == 'Import'
    - docstatus == 1
    - update_stock == 1
    """
    for pi_ref in import_doc.get("linked_purchase_invoices") or []:
        try:
            pi = frappe.get_doc("Purchase Invoice", pi_ref.purchase_invoice)
            if (
                pi.get("custom_purchase_invoice_type") == "Import"
                and pi.docstatus == 1
                and pi.update_stock == 1
            ):
                return True
        except Exception as e:
            frappe.log_error(f"Error checking PI {pi_ref.purchase_invoice}: {str(e)}", "LC Report Check")
    return False
