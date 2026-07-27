frappe.ui.form.on("ImportDoc", {
    refresh: function(frm) {
        // Add Update Import Data button only for saved documents
        if (!frm.is_new()) {
            let updateBtn = frm.add_custom_button(__("Update Import Data"), function() {
                updateBtn.prop('disabled', true);
                frappe.call({
                    method: "importmanager.import_utils.queue_import_doc_refresh",
                    args: {
                        import_doc_name: frm.doc.name
                    }
                }).then(() => {
                    frappe.show_alert({
                        message: __("Import data update queued. Reload this document in a minute to see the changes."),
                        indicator: 'blue'
                    });
                }).always(() => {
                    updateBtn.prop('disabled', false);
                });
            }).addClass('btn-primary');
        }
        // Add custom button if document is not locked
        if (frm.doc.status !== "Locked") {
            frm.add_custom_button(__("Finalize and Generate Allocation Ledger Entries"), function() {
                frappe.confirm(
                    'This will lock the document and create allocation ledger entries. Continue?',
                    function() {
                        // On 'Yes' - Lock document and create allocations
                        frappe.call({
                            method: "importmanager.importmanager.doctype.importdoc.importdoc.lock_and_allocate_charges",
                            args: {
                                doc_name: frm.doc.name
                            },
                            callback: function(r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __("Document locked and charges allocated successfully"),
                                        indicator: 'green'
                                    });
                                }
                            }
                        });
                    }
                );
            }).addClass('btn-primary');
        }
    }
});