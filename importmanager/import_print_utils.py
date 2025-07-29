import frappe
import base64

@frappe.whitelist()
def fetch_jpg_from_charge_allocation(item_code):
    # Step 1: Fetch the latest Charge Allocation Ledger entry
    charge_allocation = frappe.get_all(
        'Charge Allocation Ledger',
        filters={
            'charge_type': 'Import Charges',
            'item_code': item_code,
            'reference_doc': 'ImportDoc'
        },
        order_by='modified desc',
        limit=1,
        fields=['reference_doc_name']
    )
    
    if not charge_allocation:
        return None  # No entry found

    reference_doc_name = charge_allocation[0].reference_doc_name

    # Step 2: Fetch the JPG file
    file = frappe.get_all(
        'File',
        filters={
            'attached_to_doctype':'ImportDoc',
            'attached_to_name': reference_doc_name,
            'custom_document_content_type': 'GD',
            'file_type': 'JPG'
        },
        fields=['name', 'file_url'],
        limit=1
    )

    if not file:
        return None  # No PDF found

    # Step 3: Return the base64 representation of the PDF
    pdf_file = file[0]
    pdf_doc = frappe.get_doc('File', pdf_file.name)  # Fetch the file document
    pdf_url = pdf_doc.file_url
    #pdf_content = pdf_doc.get_content()  # Get the content of the file

    
    #return base64.b64encode(pdf_content).decode('utf-8')
    return pdf_url

@frappe.whitelist()
def fetch_jpg_from_import_doc(item_code):
    # Step 1: Fetch the latest Charge Allocation Ledger entry
    import_docs = frappe.get_all(
        'Import Items',
        filters={
            
            'item_code': item_code,
            
        },
        order_by='modified desc',
        
        fields=['parent']
    )
    
    if not import_docs:
        return None  # No entry found
    
    import_docs_list = [d['parent' ] for d in import_docs ]

    

    # Step 2: Fetch the JPG file
    file = frappe.get_all(
        'File',
        filters={
            'attached_to_doctype':'ImportDoc',
            'attached_to_name': ["in",import_docs_list],
            'custom_document_content_type': 'GD',
            'file_type': 'JPG'
        },
        fields=['name', 'file_url'],
        limit=1,
        order_by='modified desc'
    )
    
    if not file:
        return None  # No PDF found

    # Step 3: Return the base64 representation of the PDF
    pdf_file = file[0]
    pdf_doc = frappe.get_doc('File', pdf_file.name)  # Fetch the file document
    pdf_url = pdf_doc.file_url
    #pdf_content = pdf_doc.get_content()  # Get the content of the file

    
    #return base64.b64encode(pdf_content).decode('utf-8')
    return pdf_url
