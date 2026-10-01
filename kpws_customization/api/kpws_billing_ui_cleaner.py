import frappe


PATIENT_CLIENT_SCRIPT = r"""
(function () {
    window.KPWSBillingUI = {
        inject_css() {
            if (document.getElementById("kpws-billing-ui-css")) return;

            const css = `
                .kpws-billing-card {
                    border: 1px solid #e5e7eb;
                    border-radius: 12px;
                    background: #ffffff;
                    margin: 10px 0 14px 0;
                    padding: 14px 16px;
                    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
                    font-size: 13px;
                }

                .kpws-billing-card.green {
                    border-left: 5px solid #16a34a;
                }

                .kpws-billing-card.red {
                    border-left: 5px solid #dc2626;
                }

                .kpws-billing-card.orange {
                    border-left: 5px solid #f97316;
                }

                .kpws-billing-card.gray {
                    border-left: 5px solid #64748b;
                }

                .kpws-billing-top {
                    display: flex;
                    justify-content: space-between;
                    gap: 12px;
                    align-items: flex-start;
                }

                .kpws-billing-kicker {
                    font-size: 11px;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    color: #64748b;
                    font-weight: 700;
                    margin-bottom: 3px;
                }

                .kpws-billing-title {
                    font-size: 15px;
                    color: #0f172a;
                    font-weight: 700;
                    line-height: 1.3;
                }

                .kpws-billing-message {
                    color: #334155;
                    margin-top: 8px;
                    line-height: 1.45;
                }

                .kpws-billing-badge {
                    border-radius: 999px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    white-space: nowrap;
                }

                .kpws-billing-badge.green {
                    background: #dcfce7;
                    color: #166534;
                }

                .kpws-billing-badge.red {
                    background: #fee2e2;
                    color: #991b1b;
                }

                .kpws-billing-badge.orange {
                    background: #ffedd5;
                    color: #9a3412;
                }

                .kpws-billing-badge.gray {
                    background: #f1f5f9;
                    color: #334155;
                }

                .kpws-billing-details {
                    margin-top: 10px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }

                .kpws-billing-chip {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    color: #334155;
                    border-radius: 999px;
                    padding: 5px 9px;
                    font-size: 12px;
                }

                .kpws-billing-action {
                    margin-top: 10px;
                    padding: 9px 10px;
                    border-radius: 9px;
                    background: #f8fafc;
                    border: 1px dashed #cbd5e1;
                    color: #334155;
                    line-height: 1.45;
                }

                .kpws-missing-list {
                    margin-top: 10px;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    overflow: hidden;
                }

                .kpws-missing-row {
                    display: grid;
                    grid-template-columns: 60px 1fr;
                    gap: 8px;
                    padding: 8px 10px;
                    border-bottom: 1px solid #f1f5f9;
                    background: #fff;
                }

                .kpws-missing-row:last-child {
                    border-bottom: 0;
                }

                .kpws-missing-row-label {
                    color: #64748b;
                    font-weight: 700;
                    font-size: 12px;
                }

                .kpws-missing-row-value {
                    color: #0f172a;
                    font-size: 12px;
                }
            `;

            const style = document.createElement("style");
            style.id = "kpws-billing-ui-css";
            style.innerHTML = css;
            document.head.appendChild(style);
        },

        esc(value) {
            return String(value || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        },

        indicator(data) {
            if (!data) return "gray";
            return data.indicator || (data.blocked ? "red" : "green");
        },

        badge_text(data) {
            if (!data) return "Not Checked";
            return data.blocked ? "Action Required" : "Ready";
        },

        card_html(kicker, data, details_html, action_text) {
            const indicator = this.indicator(data);
            const title = data && data.title ? data.title : "Status";
            const message = data && data.message ? data.message : "";

            return `
                <div class="kpws-billing-card ${indicator}">
                    <div class="kpws-billing-top">
                        <div>
                            <div class="kpws-billing-kicker">${this.esc(kicker)}</div>
                            <div class="kpws-billing-title">${this.esc(title)}</div>
                        </div>
                        <span class="kpws-billing-badge ${indicator}">
                            ${this.esc(this.badge_text(data))}
                        </span>
                    </div>

                    ${message ? `<div class="kpws-billing-message">${this.esc(message)}</div>` : ""}

                    ${details_html || ""}

                    ${action_text ? `
                        <div class="kpws-billing-action">
                            ${this.esc(action_text)}
                        </div>
                    ` : ""}
                </div>
            `;
        },

        render(frm, fieldname, html) {
            this.inject_css();

            if (frm.fields_dict[fieldname] && frm.fields_dict[fieldname].$wrapper) {
                frm.fields_dict[fieldname].$wrapper.html(html || "");
            }
        }
    };
})();

const KPWS_SI_PATIENT_FIELDS = [
    "patient",
    "custom_patient",
    "healthcare_patient",
    "custom_healthcare_patient",
    "patient_id",
    "custom_patient_id"
];

function kpws_si_find_patient_field(frm) {
    for (const fieldname of KPWS_SI_PATIENT_FIELDS) {
        if (frm.fields_dict[fieldname]) {
            return fieldname;
        }
    }
    return null;
}

function kpws_patient_details_html(data) {
    const ui = window.KPWSBillingUI;
    const chips = [];

    if (data.patient) chips.push(`Patient: ${ui.esc(data.patient)}`);
    if (data.group) chips.push(`Billing Type: ${ui.esc(data.group)}`);
    if (data.welfare_status) chips.push(`Welfare Status: ${ui.esc(data.welfare_status)}`);
    if (data.welfare_record) chips.push(`Form: ${ui.esc(data.welfare_record)}`);
    if (data.panel_customer) chips.push(`Panel: ${ui.esc(data.panel_customer)}`);

    if (!chips.length) return "";

    return `
        <div class="kpws-billing-details">
            ${chips.map(chip => `<span class="kpws-billing-chip">${chip}</span>`).join("")}
        </div>
    `;
}

function kpws_patient_action_text(data) {
    if (!data || !data.blocked) return "";

    if (data.group === "Welfare") {
        return "Ask Welfare / Reception department to complete and submit the welfare registration before billing.";
    }

    if (data.group === "Panel") {
        return "Ask Reception / Administrator to assign the correct panel on the Patient first.";
    }

    return "Ask Reception / Administrator to correct the patient billing setup first.";
}

function kpws_si_render_patient_status(frm, data) {
    const html = window.KPWSBillingUI.card_html(
        "Patient Billing Status",
        data,
        kpws_patient_details_html(data || {}),
        kpws_patient_action_text(data || {})
    );

    window.KPWSBillingUI.render(
        frm,
        "custom_kpws_patient_billing_status",
        html
    );
}

function kpws_si_check_patient_status(frm, show_popup) {
    const patient_field = kpws_si_find_patient_field(frm);

    if (!patient_field || !frm.doc[patient_field]) {
        window.KPWSBillingUI.render(frm, "custom_kpws_patient_billing_status", "");
        return;
    }

    frappe.call({
        method: "kpws_customization.api.kpws_patient_invoice_control.get_sales_invoice_patient_billing_status",
        args: {
            patient: frm.doc[patient_field],
            invoice_customer: frm.doc.customer || ""
        },
        freeze: false,
        callback: function (r) {
            const data = r.message || {};
            kpws_si_render_patient_status(frm, data);

            if (data.blocked) {
                frm.set_intro(data.message, "red");

                if (show_popup) {
                    frappe.show_alert({
                        message: data.title || data.message,
                        indicator: data.indicator || "red"
                    }, 8);
                }
            }

            if (!data.blocked && data.group === "Panel" && data.panel_customer && frm.doc.customer !== data.panel_customer) {
                frm.add_custom_button(__("Set Assigned Panel Customer"), function () {
                    frm.set_value("customer", data.panel_customer);
                }, __("KPWS"));
            }
        }
    });
}

frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        kpws_si_check_patient_status(frm, false);

        frm.add_custom_button(__("Check Patient Billing"), function () {
            kpws_si_check_patient_status(frm, true);
        }, __("KPWS"));
    },

    patient(frm) {
        kpws_si_check_patient_status(frm, true);
    },

    custom_patient(frm) {
        kpws_si_check_patient_status(frm, true);
    },

    healthcare_patient(frm) {
        kpws_si_check_patient_status(frm, true);
    },

    custom_healthcare_patient(frm) {
        kpws_si_check_patient_status(frm, true);
    },

    patient_id(frm) {
        kpws_si_check_patient_status(frm, true);
    },

    custom_patient_id(frm) {
        kpws_si_check_patient_status(frm, true);
    },

    customer(frm) {
        kpws_si_check_patient_status(frm, false);
    }
});
"""


PRICING_CLIENT_SCRIPT = r"""
(function () {
    window.KPWSBillingUI = {
        inject_css() {
            if (document.getElementById("kpws-billing-ui-css")) return;

            const css = `
                .kpws-billing-card {
                    border: 1px solid #e5e7eb;
                    border-radius: 12px;
                    background: #ffffff;
                    margin: 10px 0 14px 0;
                    padding: 14px 16px;
                    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
                    font-size: 13px;
                }

                .kpws-billing-card.green {
                    border-left: 5px solid #16a34a;
                }

                .kpws-billing-card.red {
                    border-left: 5px solid #dc2626;
                }

                .kpws-billing-card.orange {
                    border-left: 5px solid #f97316;
                }

                .kpws-billing-card.gray {
                    border-left: 5px solid #64748b;
                }

                .kpws-billing-top {
                    display: flex;
                    justify-content: space-between;
                    gap: 12px;
                    align-items: flex-start;
                }

                .kpws-billing-kicker {
                    font-size: 11px;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    color: #64748b;
                    font-weight: 700;
                    margin-bottom: 3px;
                }

                .kpws-billing-title {
                    font-size: 15px;
                    color: #0f172a;
                    font-weight: 700;
                    line-height: 1.3;
                }

                .kpws-billing-message {
                    color: #334155;
                    margin-top: 8px;
                    line-height: 1.45;
                }

                .kpws-billing-badge {
                    border-radius: 999px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    white-space: nowrap;
                }

                .kpws-billing-badge.green {
                    background: #dcfce7;
                    color: #166534;
                }

                .kpws-billing-badge.red {
                    background: #fee2e2;
                    color: #991b1b;
                }

                .kpws-billing-badge.orange {
                    background: #ffedd5;
                    color: #9a3412;
                }

                .kpws-billing-badge.gray {
                    background: #f1f5f9;
                    color: #334155;
                }

                .kpws-billing-details {
                    margin-top: 10px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }

                .kpws-billing-chip {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    color: #334155;
                    border-radius: 999px;
                    padding: 5px 9px;
                    font-size: 12px;
                }

                .kpws-billing-action {
                    margin-top: 10px;
                    padding: 9px 10px;
                    border-radius: 9px;
                    background: #f8fafc;
                    border: 1px dashed #cbd5e1;
                    color: #334155;
                    line-height: 1.45;
                }

                .kpws-missing-list {
                    margin-top: 10px;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    overflow: hidden;
                }

                .kpws-missing-row {
                    display: grid;
                    grid-template-columns: 60px 1fr;
                    gap: 8px;
                    padding: 8px 10px;
                    border-bottom: 1px solid #f1f5f9;
                    background: #fff;
                }

                .kpws-missing-row:last-child {
                    border-bottom: 0;
                }

                .kpws-missing-row-label {
                    color: #64748b;
                    font-weight: 700;
                    font-size: 12px;
                }

                .kpws-missing-row-value {
                    color: #0f172a;
                    font-size: 12px;
                }
            `;

            const style = document.createElement("style");
            style.id = "kpws-billing-ui-css";
            style.innerHTML = css;
            document.head.appendChild(style);
        },

        esc(value) {
            return String(value || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        },

        indicator(data) {
            if (!data) return "gray";
            return data.indicator || (data.blocked ? "red" : "green");
        },

        badge_text(data) {
            if (!data) return "Not Checked";
            return data.blocked ? "Action Required" : "Ready";
        },

        card_html(kicker, data, details_html, action_text) {
            const indicator = this.indicator(data);
            const title = data && data.title ? data.title : "Status";
            const message = data && data.message ? data.message : "";

            return `
                <div class="kpws-billing-card ${indicator}">
                    <div class="kpws-billing-top">
                        <div>
                            <div class="kpws-billing-kicker">${this.esc(kicker)}</div>
                            <div class="kpws-billing-title">${this.esc(title)}</div>
                        </div>
                        <span class="kpws-billing-badge ${indicator}">
                            ${this.esc(this.badge_text(data))}
                        </span>
                    </div>

                    ${message ? `<div class="kpws-billing-message">${this.esc(message)}</div>` : ""}

                    ${details_html || ""}

                    ${action_text ? `
                        <div class="kpws-billing-action">
                            ${this.esc(action_text)}
                        </div>
                    ` : ""}
                </div>
            `;
        },

        render(frm, fieldname, html) {
            this.inject_css();

            if (frm.fields_dict[fieldname] && frm.fields_dict[fieldname].$wrapper) {
                frm.fields_dict[fieldname].$wrapper.html(html || "");
            }
        }
    };
})();

function kpws_si_pricing_items(frm) {
    return (frm.doc.items || []).map(function (row) {
        return {
            idx: row.idx,
            item_code: row.item_code,
            item_name: row.item_name,
            uom: row.uom,
            rate: row.rate,
            price_list_rate: row.price_list_rate,
            is_free_item: row.is_free_item
        };
    });
}

function kpws_pricing_details_html(data) {
    const ui = window.KPWSBillingUI;
    const missing = data && data.missing ? data.missing : [];

    if (!missing.length) {
        return `
            <div class="kpws-billing-details">
                <span class="kpws-billing-chip">All items priced</span>
            </div>
        `;
    }

    return `
        <div class="kpws-billing-details">
            <span class="kpws-billing-chip">${missing.length} item(s) need pricing</span>
        </div>

        <div class="kpws-missing-list">
            ${missing.map(row => `
                <div class="kpws-missing-row">
                    <div class="kpws-missing-row-label">Row ${ui.esc(row.idx)}</div>
                    <div class="kpws-missing-row-value">
                        ${ui.esc(row.item_code)} — ${ui.esc(row.item_name)}
                    </div>
                </div>
            `).join("")}
        </div>
    `;
}

function kpws_si_render_pricing_status(frm, data) {
    const action = data && data.blocked
        ? "Ask Warehouse / Accounts to update the item price before billing."
        : "";

    const html = window.KPWSBillingUI.card_html(
        "Item Pricing Status",
        data,
        kpws_pricing_details_html(data || {}),
        action
    );

    window.KPWSBillingUI.render(
        frm,
        "custom_kpws_item_pricing_status",
        html
    );
}

function kpws_si_check_pricing(frm, show_alert) {
    if (!frm.doc.items || !frm.doc.items.length) {
        window.KPWSBillingUI.render(frm, "custom_kpws_item_pricing_status", "");
        return;
    }

    frappe.call({
        method: "kpws_customization.api.kpws_sales_invoice_pricing_control.check_sales_invoice_item_pricing",
        args: {
            items: JSON.stringify(kpws_si_pricing_items(frm)),
            selling_price_list: frm.doc.selling_price_list || "",
            posting_date: frm.doc.posting_date || frappe.datetime.get_today()
        },
        freeze: false,
        callback: function (r) {
            const data = r.message || {};
            kpws_si_render_pricing_status(frm, data);

            if (data.blocked) {
                frm.set_intro(data.message, "red");

                if (show_alert) {
                    frappe.show_alert({
                        message: "Missing item pricing. Ask Warehouse / Accounts to update pricing.",
                        indicator: "red"
                    }, 8);
                }
            }
        }
    });
}

frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        kpws_si_check_pricing(frm, false);

        frm.add_custom_button(__("Check Item Pricing"), function () {
            kpws_si_check_pricing(frm, true);
        }, __("KPWS"));
    },

    selling_price_list(frm) {
        kpws_si_check_pricing(frm, true);
    },

    posting_date(frm) {
        kpws_si_check_pricing(frm, false);
    },

    validate(frm) {
        kpws_si_check_pricing(frm, false);
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, true);
        }, 900);
    },

    qty(frm, cdt, cdn) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, false);
        }, 500);
    },

    rate(frm, cdt, cdn) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, false);
        }, 400);
    },

    price_list_rate(frm, cdt, cdn) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, false);
        }, 400);
    },

    items_remove(frm) {
        kpws_si_check_pricing(frm, false);
    }
});
"""


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _ensure_html_field(fieldname, label, insert_after):
    existing = frappe.db.exists(
        "Custom Field",
        {
            "dt": "Sales Invoice",
            "fieldname": fieldname,
        },
    )

    if existing:
        doc = frappe.get_doc("Custom Field", existing)
        doc.label = label
        doc.fieldtype = "HTML"
        doc.read_only = 1
        doc.no_copy = 1
        doc.save(ignore_permissions=True)
        return

    doc = frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": "Sales Invoice",
            "label": label,
            "fieldname": fieldname,
            "fieldtype": "HTML",
            "insert_after": insert_after,
            "read_only": 1,
            "no_copy": 1,
        }
    )
    doc.insert(ignore_permissions=True)


def _upsert_client_script(name, script):
    existing = frappe.db.exists("Client Script", name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name
        doc.dt = "Sales Invoice"

    doc.dt = "Sales Invoice"
    doc.script = script

    if doc.meta.has_field("view"):
        doc.view = "Form"

    if doc.meta.has_field("enabled"):
        doc.enabled = 1

    doc.save(ignore_permissions=True)


@frappe.whitelist()
def install():
    patient_insert_after = "customer"

    for fieldname in (
        "patient",
        "custom_patient",
        "healthcare_patient",
        "custom_healthcare_patient",
        "patient_id",
        "custom_patient_id",
    ):
        if _has_field("Sales Invoice", fieldname):
            patient_insert_after = fieldname
            break

    _ensure_html_field(
        "custom_kpws_patient_billing_status",
        "KPWS Patient Billing Status",
        patient_insert_after,
    )

    _ensure_html_field(
        "custom_kpws_item_pricing_status",
        "KPWS Item Pricing Status",
        "custom_kpws_patient_billing_status",
    )

    _upsert_client_script(
        "KPWS Sales Invoice Patient Billing Control",
        PATIENT_CLIENT_SCRIPT,
    )

    _upsert_client_script(
        "KPWS Sales Invoice Item Pricing Control",
        PRICING_CLIENT_SCRIPT,
    )

    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.commit()

    return "KPWS clean billing UI installed."
