frappe.listview_settings["Patient"] = frappe.listview_settings["Patient"] || {};

frappe.listview_settings["Patient"].onload = function (listview) {
    listview.page.add_actions_menu_item(__("Create/Open Welfare Registration Forms"), function () {
        const selected = listview.get_checked_items().map(row => row.name);

        if (!selected.length) {
            frappe.msgprint("Please select at least one Patient.");
            return;
        }

        const d = new frappe.ui.Dialog({
            title: "Bulk Welfare Registration Forms",
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
                    label: "Approve / Submit after creation",
                    fieldtype: "Check",
                    default: 1
                }
            ],
            primary_action_label: "Create / Open Forms",
            primary_action(values) {
                const percentage = Number(values.percentage || 0);

                if (percentage < 0 || percentage > 100) {
                    frappe.msgprint("Percentage must be between 0 and 100.");
                    return;
                }

                d.hide();

                frappe.call({
                    method: "kpws_customization.api.kpws_bulk_welfare_prf_v36.bulk_create_or_open_welfare_prf",
                    args: {
                        patients: JSON.stringify(selected),
                        purpose: values.purpose,
                        percentage: percentage,
                        approve: values.approve ? 1 : 0
                    },
                    freeze: true,
                    freeze_message: "Creating welfare registration forms...",
                    callback(r) {
                        const data = r.message || {};
                        const forms = data.forms || [];

                        let html = `
                            <div>
                                <b>Created:</b> ${data.created_count || 0}<br>
                                <b>Already Existing:</b> ${data.existing_count || 0}<br>
                                <b>Errors:</b> ${data.error_count || 0}
                            </div>
                        `;

                        if (forms.length) {
                            html += `<hr><div style="max-height:220px;overflow:auto;">`;
                            forms.slice(0, 50).forEach(name => {
                                html += `<div><a href="/app/patient-registration-form/${encodeURIComponent(name)}" target="_blank">${frappe.utils.escape_html(name)}</a></div>`;
                            });
                            html += `</div>`;
                        }

                        if (data.errors && data.errors.length) {
                            html += `<hr><b>Errors:</b><br>`;
                            data.errors.slice(0, 10).forEach(row => {
                                html += `<div>${frappe.utils.escape_html(row.patient)}: ${frappe.utils.escape_html(row.error)}</div>`;
                            });
                        }

                        frappe.msgprint({
                            title: "Bulk Welfare Registration Result",
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
