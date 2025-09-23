import frappe

# Functions in this will run when app will first install

def create_party_types():
    """
    This will create new party types in ERPNext for Import Manager purposes
    using direct SQL query.
    """
    try:
        # Define the party types to create
        party_types_to_create = [
            {
                "party_type": "Letter Of Credit",
                "account_type": "Payable"
            }
        ]
        
        for party_type_data in party_types_to_create:
            party_type = party_type_data["party_type"]
            account_type = party_type_data["account_type"]
            
            # Check if party type exists
            existing_party = frappe.get_list("Party Type", filters={"party_type": party_type})
            
            if len(existing_party) > 0:
                frappe.msgprint(f"Party Type '{party_type}' already exists.", alert=True)
                continue
                
            # If party type doesn't exist, create it using SQL
            creation_time = frappe.utils.now()
            query = """
                INSERT INTO `tabParty Type` 
                    (name, creation, modified, modified_by, owner, docstatus, 
                    idx, party_type, account_type, _user_tags, _comments, 
                    _assign, _liked_by)
                VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                party_type,          # name
                creation_time,       # creation
                creation_time,       # modified
                'Administrator',     # modified_by
                'Administrator',     # owner
                0,                  # docstatus
                0,                  # idx
                party_type,         # party_type
                account_type,       # account_type
                None,              # _user_tags
                None,              # _comments
                None,              # _assign
                None               # _liked_by
            )
            
            frappe.db.sql(query, values)
            frappe.msgprint(f"Party Type '{party_type}' created successfully.")
        
        frappe.db.commit()
        frappe.msgprint("All party types created successfully for Import Manager app.")
        
    except Exception as e:
        frappe.log_error(f"Error creating Party Types for Import Manager: {str(e)}", "Import Manager Party Type Creation Error")
        frappe.msgprint(f"Error creating party types: {str(e)}", alert=True)