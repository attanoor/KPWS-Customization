from pathlib import Path
import frappe


SERVER_PATCH = r'''


# KPWS PATCH: hide pricing status on blank Sales Invoice / empty item rows
@frappe.whitelist()
def check_sales_invoice_item_pricing(items=None, selling_price_list=None, posting_date=None):
    items = _to_list(items)

    # Only consider real item rows. Ignore empty default child table rows.
    valid_items = []
    for row in items:
        if row and row.get("item_code"):
            valid_items.append(row)

    if not valid_items:
        return {
            "show": False,
            "blocked": False,
            "indicator": "gray",
            "title": "",
            "message": "",
            "html": "",
            "missing": [],
        }

    missing = []

    for row in valid_items:
        item_code = row.get("item_code")
        is_free_item = cint(row.get("is_free_item"))

        if is_free_item:
            continue

        rate = flt(row.get("rate"))
        price_list_rate = flt(row.get("price_list_rate"))
        item_name = row.get("item_name") or frappe.db.get_value("Item", item_code, "item_name") or item_code
        uom = row.get("uom")

        if rate > 0:
            continue

        has_item_price = _item_price_exists(
            item_code=item_code,
            price_list=selling_price_list,
            posting_date=posting_date,
            uom=uom,
        )

        missing.append({
            "idx": row.get("idx"),
            "item_code": item_code,
            "item_name": item_name,
            "uom": uom,
            "rate": rate,
            "price_list_rate": price_list_rate,
            "price_list": selling_price_list,
            "has_item_price": has_item_price,
        })

    if not missing:
        return {
            "show": True,
            "blocked": False,
            "indicator": "green",
            "title": "Item Pricing OK",
            "message": "All selected items have valid pricing.",
            "html": _html_box(
                "Item Pricing OK",
                "green",
                ["All selected items have valid pricing."]
            ),
            "missing": [],
        }

    lines = [
        "The following item(s) have missing or zero pricing:",
    ]

    for row in missing:
        price_list_text = row.get("price_list") or "Selected Price List is missing"
        lines.append(
            f"Row {row.get('idx')}: {row.get('item_code')} - {row.get('item_name')} | Price List: {price_list_text}"
        )

    lines.append("Please ask Warehouse/Accounts to update item pricing before billing.")

    return {
        "show": True,
        "blocked": True,
        "indicator": "red",
        "title": "Missing Item Pricing",
        "message": "Some invoice items have missing or zero pricing. Please ask Warehouse/Accounts to update pricing first.",
        "html": _html_box(
            "Missing Item Pricing",
            "red",
            lines,
        ),
        "missing": missing,
    }
'''


CLIENT_SCRIPT = r"""
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
                .kpws-billing-card.green { border-left: 5px solid #16a34a; }
                .kpws-billing-card.red { border-left: 5px solid #dc2626; }
                .kpws-billing-card.orange { border-left: 5px solid #f97316; }
                .kpws-billing-card.gray { border-left: 5px solid #64748b; }

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

        card_html(kicker, data, details_html, action_text) {
            const indicator = data.indicator || (data.blocked ? "red" : "green");
            const badge = data.blocked ? "Action Required" : "Ready";

            return `
                <div class="kpws-billing-card ${indicator}">
                    <div class="kpws-billing-top">
                        <div>
                            <div class="kpws-billing-kicker">${this.esc(kicker)}</div>
                            <div class="kpws-billing-title">${this.esc(data.title || "Status")}</div>
                        </div>
                        <span class="kpws-billing-badge ${indicator}">
                            ${this.esc(badge)}
                        </span>
                    </div>

                    ${data.message ? `<div class="kpws-billing-message">${this.esc(data.message)}</div>` : ""}
                    ${details_html || ""}
                    ${action_text ? `<div class="kpws-billing-action">${this.esc(action_text)}</div>` : ""}
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
    return (frm.doc.items || [])
        .filter(function (row) {
            return row && row.item_code;
        })
        .map(function (row) {
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
                <span class="kpws-billing-chip">All selected items priced</span>
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
    if (!data || data.show === false) {
        window.KPWSBillingUI.render(frm, "custom_kpws_item_pricing_status", "");
        return;
    }

    const action = data.blocked
        ? "Ask Warehouse / Accounts to update the item price before billing."
        : "";

    const html = window.KPWSBillingUI.card_html(
        "Item Pricing Status",
        data,
        kpws_pricing_details_html(data),
        action
    );

    window.KPWSBillingUI.render(
        frm,
        "custom_kpws_item_pricing_status",
        html
    );
}

function kpws_si_check_pricing(frm, show_alert) {
    const real_items = kpws_si_pricing_items(frm);

    if (!real_items.length) {
        window.KPWSBillingUI.render(frm, "custom_kpws_item_pricing_status", "");
        return;
    }

    frappe.call({
        method: "kpws_customization.api.kpws_sales_invoice_pricing_control.check_sales_invoice_item_pricing",
        args: {
            items: JSON.stringify(real_items),
            selling_price_list: frm.doc.selling_price_list || "",
            posting_date: frm.doc.posting_date || frappe.datetime.get_today()
        },
        freeze: false,
        callback: function (r) {
            const data = r.message || {};
            kpws_si_render_pricing_status(frm, data);

            if (data.blocked && show_alert) {
                frappe.show_alert({
                    message: "Missing item pricing. Ask Warehouse / Accounts to update pricing.",
                    indicator: "red"
                }, 8);
            }
        }
    });
}

frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        // Do not show pricing card on blank invoice.
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
    item_code(frm) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, true);
        }, 900);
    },

    qty(frm) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, false);
        }, 500);
    },

    rate(frm) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, false);
        }, 400);
    },

    price_list_rate(frm) {
        setTimeout(function () {
            kpws_si_check_pricing(frm, false);
        }, 400);
    },

    items_remove(frm) {
        kpws_si_check_pricing(frm, false);
    }
});
"""


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    pricing_file = app_path / "api" / "kpws_sales_invoice_pricing_control.py"

    text = pricing_file.read_text()

    if "KPWS PATCH: hide pricing status on blank Sales Invoice" not in text:
        pricing_file.write_text(text + SERVER_PATCH)

    script_name = "KPWS Sales Invoice Item Pricing Control"
    existing = frappe.db.exists("Client Script", script_name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = script_name
        doc.dt = "Sales Invoice"

    doc.dt = "Sales Invoice"
    doc.script = CLIENT_SCRIPT

    if doc.meta.has_field("view"):
        doc.view = "Form"

    if doc.meta.has_field("enabled"):
        doc.enabled = 1

    doc.save(ignore_permissions=True)

    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.commit()

    return {
        "ok": True,
        "message": "Pricing card will now stay hidden until at least one item is selected."
    }
