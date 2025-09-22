['Landed Cost Voucher','Purchase Invoice','Sales Invoice','Journal Entry'].forEach(function(dt){
    frappe.ui.form.on(dt, {
        onload: function(frm) {
            if (frm.fields_dict && frm.fields_dict.custom_import_document) {
                console.log('apply set_query on', dt);
                frm.set_query('custom_import_document', function() {
                    return { filters: { workflow_state: 'Pending' } };
                });
            }
        }
    });
});