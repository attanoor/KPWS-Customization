import json
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, escape_html


def _to_list(value):
    if not value:
        return []

    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []

    return value


def _html_box(title, indicator, lines):
    color = {
        "green": "#16a34a",
        "orange": "#f97316",
        "red": "#dc2626",
        "blue": "#2563eb",
        "gray": "#64748b",
    }.get(indicator, "#64748b")

    line_html = "".join(
        f"<div style='margin-top:4px'>{escape_html(str(line))}</div>"
        for line in lines
        if line
    )

    return f"""
    <div style="
        border: 1px solid {color};
        border-left: 5px solid {color};
        border-radius: 8px;
        padding: 10px 12px;
        margin: 8px 0;
        background: #fff;
    ">
        <div style="font-weight: 700; color: {color}; margin-bottom: 4px;">
            {escape_html(title)}
        </div>
        {line_html}
    </div>
    """


def _item_price_exists(item_code, price_list, posting_date=None, uom=None):
    if not item_code or not price_list:
        return False

    posting_date = getdate(posting_date or nowdate())

    filters = {
        "item_code": item_code,
        "price_list": price_list,
        "selling": 1,
    }

    if frappe.get_meta("Item Price").has_field("disabled"):
        filters["disabled"] = 0

    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=[
            "name",
            "price_list_rate",
            "uom",
            "valid_from",
            "valid_upto",
        ],
        order_by="valid_from desc, modified desc",
        limit_page_length=50,
    )

    for row in rows:
        if flt(row.price_list_rate) <= 0:
            continue

        if row.valid_from and getdate(row.valid_from) > posting_date:
            continue

        if row.valid_upto and getdate(row.valid_upto) < posting_date:
            continue

        if row.uom and uom and row.uom != uom:
            continue

        return True

    return False


@frappe.whitelist()
def check_sales_invoice_item_pricing(items=None, selling_price_list=None, posting_date=None):
    items = _to_list(items)
    missing = []

    for row in items:
        item_code = row.get("item_code")
        if not item_code:
            continue

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

    if not items:
        return {
            "blocked": False,
            "indicator": "gray",
            "title": "No Items",
            "message": "",
            "html": "",
            "missing": [],
        }

    if not missing:
        return {
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


def validate_sales_invoice_item_pricing(doc, method=None):
    items = []

    for row in doc.get("items") or []:
        items.append({
            "idx": row.idx,
            "item_code": row.item_code,
            "item_name": row.item_name,
            "uom": row.uom,
            "rate": row.rate,
            "price_list_rate": row.price_list_rate,
            "is_free_item": row.get("is_free_item"),
        })

    status = check_sales_invoice_item_pricing(
        items=items,
        selling_price_list=doc.get("selling_price_list"),
        posting_date=doc.get("posting_date"),
    )

    if status.get("blocked"):
        frappe.throw(
            status.get("message"),
            title=_("KPWS Item Pricing Control")
        )


CLIENT_SCRIPT = r"""
function kpws_si_pricing_items(frm) {
    return (frm.doc.items || []).map(function(row) {
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

function kpws_si_render_pricing_status(frm, data) {
    const html_field = "custom_kpws_item_pricing_status";

    if (frm.fields_dict[html_field] && frm.fields_dict[html_field].$wrapper) {
        frm.fields_dict[html_field].$wrapper.html(data && data.html ? data.html : "");
    }

    if (data && data.blocked) {
        frm.set_intro(data.message, "red");
    }
}

function kpws_si_check_pricing(frm, show_popup) {
    if (!frm.doc.items || !frm.doc.items.length) {
        const html_field = "custom_kpws_item_pricing_status";
        if (frm.fields_dict[html_field] && frm.fields_dict[html_field].$wrapper) {
            frm.fields_dict[html_field].$wrapper.html("");
        }
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
        callback: function(r) {
            const data = r.message || {};
            kpws_si_render_pricing_status(frm, data);

            if (data.blocked && show_popup) {
                frappe.msgprint({
                    title: __("KPWS Item Pricing Control"),
                    indicator: data.indicator || "red",
                    message: data.html || data.message
                });
            }
        }
    });
}

frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        kpws_si_check_pricing(frm, false);

        frm.add_custom_button(__("Recheck Item Pricing"), function() {
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
        setTimeout(function() {
            kpws_si_check_pricing(frm, true);
        }, 800);
    },

    qty(frm, cdt, cdn) {
        setTimeout(function() {
            kpws_si_check_pricing(frm, false);
        }, 500);
    },

    rate(frm, cdt, cdn) {
        setTimeout(function() {
            kpws_si_check_pricing(frm, false);
        }, 300);
    },

    price_list_rate(frm, cdt, cdn) {
        setTimeout(function() {
            kpws_si_check_pricing(frm, false);
        }, 300);
    },

    items_remove(frm) {
        kpws_si_check_pricing(frm, false);
    }
});
"""


def install_custom_field():
    fieldname = "custom_kpws_item_pricing_status"

    if frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": fieldname}):
        return

    insert_after = "custom_kpws_patient_billing_status"

    if not frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": insert_after}):
        insert_after = "items"

    doc = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Sales Invoice",
        "label": "KPWS Item Pricing Status",
        "fieldname": fieldname,
        "fieldtype": "HTML",
        "insert_after": insert_after,
        "read_only": 1,
        "no_copy": 1,
    })
    doc.insert(ignore_permissions=True)


def install_client_script():
    name = "KPWS Sales Invoice Item Pricing Control"

    existing = frappe.db.exists("Client Script", name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name
        doc.dt = "Sales Invoice"

    doc.dt = "Sales Invoice"
    doc.script = CLIENT_SCRIPT

    if doc.meta.has_field("view"):
        doc.view = "Form"

    if doc.meta.has_field("enabled"):
        doc.enabled = 1

    doc.save(ignore_permissions=True)


@frappe.whitelist()
def install():
    install_custom_field()
    install_client_script()
    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.commit()

    return "KPWS Sales Invoice Item Pricing Control installed."



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
