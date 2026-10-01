frappe.listview_settings["Patient Registration Form"] = frappe.listview_settings["Patient Registration Form"] || {};

frappe.listview_settings["Patient Registration Form"].onload = function (listview) {
    listview.page.add_actions_menu_item(__("Bulk Purpose / Percentage / Approve"), function () {
        const selected = listview.get_checked_items().map(row => row.name);

        if (!selected.length) {
            frappe.msgprint("Please select at least one Patient Registration Form.");
            return;
        }

        const d = new frappe.ui.Dialog({
            title: "Bulk Update Welfare Registration Forms",
            fields: [
                {
                    fieldname: "purpose",
                    label: "Purpose",
                    fieldtype: "Select",
                    options: "Zakat\nDonation",
                    default: "Zakat",
                    reqd: 1
                },
                {
                    fieldname: "percentage",
                    label: "Percentage",
                    fieldtype: "Float",
                    default: 100,
                    reqd: 1,
                    description: "Must be between 0 and 100."
                },
                {
                    fieldname: "approve",
                    label: "Approve / Submit selected forms",
                    fieldtype: "Check",
                    default: 1
                }
            ],
            primary_action_label: "Update Selected Forms",
            primary_action(values) {
                const percentage = Number(values.percentage || 0);

                if (percentage < 0 || percentage > 100) {
                    frappe.msgprint("Percentage must be between 0 and 100.");
                    return;
                }

                d.hide();

                frappe.call({
                    method: "kpws_customization.api.kpws_bulk_welfare_prf_v36.bulk_set_purpose_percentage_and_approve",
                    args: {
                        forms: JSON.stringify(selected),
                        purpose: values.purpose,
                        percentage: percentage,
                        approve: values.approve ? 1 : 0
                    },
                    freeze: true,
                    freeze_message: "Updating selected registration forms...",
                    callback(r) {
                        const data = r.message || {};

                        let html = `
                            <div>
                                <b>Updated:</b> ${data.updated_count || 0}<br>
                                <b>Skipped:</b> ${data.skipped_count || 0}<br>
                                <b>Errors:</b> ${data.error_count || 0}
                            </div>
                        `;

                        if (data.skipped && data.skipped.length) {
                            html += `<hr><b>Skipped:</b><br>`;
                            data.skipped.slice(0, 10).forEach(row => {
                                html += `<div>${frappe.utils.escape_html(row.form)}: ${frappe.utils.escape_html(row.reason)}</div>`;
                            });
                        }

                        if (data.errors && data.errors.length) {
                            html += `<hr><b>Errors:</b><br>`;
                            data.errors.slice(0, 10).forEach(row => {
                                html += `<div>${frappe.utils.escape_html(row.form)}: ${frappe.utils.escape_html(row.error)}</div>`;
                            });
                        }

                        frappe.msgprint({
                            title: "Bulk PRF Update Result",
                            message: html,
                            wide: true
                        });

                        listview.refresh();
                    }
                });
            }
        });

        d.show();
    });
};
