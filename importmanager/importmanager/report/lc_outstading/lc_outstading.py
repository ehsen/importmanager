# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

import frappe



def generate_outstanding_payments_report():
    # Fetch all ImportDoc documents where status is not "Locked"
    import_docs = frappe.get_list("ImportDoc", filters={"status": ["!=", "Locked"]}, fields=["name"])

    report_data = []  # Initialize a list to hold all report rows
    currency = "N/A"
    for doc in import_docs:
        import_doc = frappe.get_doc("ImportDoc", doc.name)
        if import_doc.linked_purchase_order:
            try:
                purchase_order = frappe.get_doc("Purchase Order", import_doc.linked_purchase_order)
                currency = purchase_order.currency  # Get the currency from the Purchase Order
            except frappe.DoesNotExistError:
                frappe.log_error(f"Purchase Order {import_doc.linked_purchase_order} does not exist.", "Purchase Order Retrieval Error")
                # Optionally, you can set currency to a default or log a message
            except Exception as e:
                frappe.log_error(f"Error fetching Purchase Order: {str(e)}", "Purchase Order Retrieval Error")
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
            "LC Total": lc_total,
             "Currency": currency,
        }

        report_data.append(report_row)  # Add the report row to the list

    return report_data  # Return the complete report data


def execute(filters=None):
    # Define the columns for the report
    columns = [
        {"label": "ImportDoc", "fieldname": "ImportDoc", "fieldtype": "Data", "width": 150},
        {"label": "Items", "fieldname": "Items", "fieldtype": "Data", "width": 300},
        {"label": "LC No.", "fieldname": "LC No.", "fieldtype": "Data", "width": 100},
        {"label": "Margin", "fieldname": "Margin", "fieldtype": "Data", "width": 100},
        {"label": "Open Exps", "fieldname": "Open Exps", "fieldtype": "Currency", "width": 100},
        {"label": "L/CFORM", "fieldname": "L/CFORM", "fieldtype": "Data", "width": 100},
        {"label": "AMD", "fieldname": "AMD", "fieldtype": "Data", "width": 100},
        {"label": "Other Exp", "fieldname": "Other Exp", "fieldtype": "Currency", "width": 100},
        {"label": "B.BILL", "fieldname": "B.BILL", "fieldtype": "Data", "width": 100},
        {"label": "Shipment", "fieldname": "Shipment", "fieldtype": "Data", "width": 100},
        {"label": "Expiry", "fieldname": "Expiry", "fieldtype": "Data", "width": 100},
        {"label": "LC Total", "fieldname": "LC Total", "fieldtype": "Float", "width": 100},
        {"label": "Currency", "fieldname": "Currency", "fieldtype": "Data", "width": 100},  # Add currency column

    ]

    # Generate the report data
    data = generate_outstanding_payments_report()

    return columns, data

