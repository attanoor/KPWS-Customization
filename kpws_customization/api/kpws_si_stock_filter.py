import frappe
from frappe import _
from frappe.utils import flt

WAREHOUSE = "Pharmacy - KPWS"


def _warehouse_exists():
    return frappe.db.exists("Warehouse", WAREHOUSE)


def _is_stock_item(item_code):
    if not item_code or not frappe.db.exists("Item", item_code):
        return False
    return bool(frappe.db.get_value("Item", item_code, "is_stock_item"))


def _actual_qty(item_code, warehouse=WAREHOUSE):
    if not item_code or not warehouse:
        return 0

    return flt(
        frappe.db.get_value(
            "Bin",
            {
                "item_code": item_code,
                "warehouse": warehouse,
            },
            "actual_qty",
        )
        or 0
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(doctype, txt, searchfield, start, page_len, filters):
    warehouse = (filters or {}).get("warehouse") or WAREHOUSE

    if not frappe.db.exists("Warehouse", warehouse):
        return []

    txt = f"%{txt or ''}%"

    return frappe.db.sql(
        """
        SELECT DISTINCT
            i.name,
            i.item_name,
            CONCAT('Available: ', FORMAT(b.actual_qty, 2)) AS available_qty
        FROM `tabItem` i
        INNER JOIN `tabBin` b
            ON b.item_code = i.name
            AND b.warehouse = %(warehouse)s
        LEFT JOIN `tabItem Barcode` ib
            ON ib.parent = i.name
        WHERE
            IFNULL(i.disabled, 0) = 0
            AND IFNULL(i.is_stock_item, 0) = 1
            AND IFNULL(i.is_sales_item, 1) = 1
            AND IFNULL(b.actual_qty, 0) > 0
            AND (
                i.name LIKE %(txt)s
                OR i.item_name LIKE %(txt)s
                OR ib.barcode LIKE %(txt)s
            )
        ORDER BY
            i.item_name ASC,
            i.name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "warehouse": warehouse,
            "txt": txt,
            "start": int(start or 0),
            "page_len": int(page_len or 20),
        },
    )


@frappe.whitelist()
def get_available_qty(item_code, warehouse=WAREHOUSE):
    return {
        "warehouse": warehouse,
        "actual_qty": _actual_qty(item_code, warehouse),
    }


def set_pharmacy_warehouse(doc, method=None):
    if doc.doctype != "Sales Invoice":
        return

    if not _warehouse_exists():
        frappe.throw(_("Warehouse {0} does not exist.").format(WAREHOUSE))

    if doc.meta.get_field("set_warehouse"):
        doc.set_warehouse = WAREHOUSE

    for row in doc.get("items") or []:
        if row.meta.get_field("warehouse"):
            row.warehouse = WAREHOUSE


def validate_pharmacy_stock(doc, method=None):
    if doc.doctype != "Sales Invoice":
        return

    if doc.get("is_return"):
        return

    if not _warehouse_exists():
        frappe.throw(_("Warehouse {0} does not exist.").format(WAREHOUSE))

    for row in doc.get("items") or []:
        if not row.item_code:
            continue

        if not _is_stock_item(row.item_code):
            continue

        # Always force warehouse on item row.
        if row.meta.get_field("warehouse"):
            row.warehouse = WAREHOUSE

        available = _actual_qty(row.item_code, WAREHOUSE)

        # stock_qty is more accurate when UOM conversion is involved.
        required = flt(row.get("stock_qty") or row.get("qty") or 0)

        if available <= 0:
            frappe.throw(
                _(
                    "Item <b>{0}</b> has no stock in <b>{1}</b>. "
                    "Only items with available stock can be selected."
                ).format(row.item_code, WAREHOUSE)
            )

        if required > available:
            frappe.throw(
                _(
                    "Insufficient stock for item <b>{0}</b> in <b>{1}</b>.<br>"
                    "Required: <b>{2}</b><br>"
                    "Available: <b>{3}</b>"
                ).format(row.item_code, WAREHOUSE, required, available)
            )


def install_client_filter():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script_name = "KPWS FINAL Light Sales Invoice Client"

    if frappe.db.exists("Client Script", script_name):
        doc = frappe.get_doc("Client Script", script_name)
        script = doc.script or ""
    else:
        doc = frappe.get_doc({
            "doctype": "Client Script",
            "name": script_name,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": "",
        })
        script = ""

    helper = r'''
// KPWS Pharmacy stock item filter
function kpws_pharmacy_stock_filter_setup(frm) {
    if (!frm || !frm.fields_dict || !frm.fields_dict.items) {
        return;
    }

    frm.set_query("item_code", "items", function(doc, cdt, cdn) {
        return {
            query: "kpws_customization.api.kpws_si_stock_filter.item_query",
            filters: {
                warehouse: "Pharmacy - KPWS"
            }
        };
    });

    if (frm.fields_dict.set_warehouse && frm.doc.set_warehouse !== "Pharmacy - KPWS") {
        frm.set_value("set_warehouse", "Pharmacy - KPWS");
    }
}

function kpws_pharmacy_stock_check_row(frm, cdt, cdn) {
    const WH = "Pharmacy - KPWS";
    let row = locals && locals[cdt] ? locals[cdt][cdn] : null;

    if (!row || !row.item_code) {
        return;
    }

    if (row.warehouse !== WH) {
        frappe.model.set_value(cdt, cdn, "warehouse", WH);
    }

    frappe.call({
        method: "kpws_customization.api.kpws_si_stock_filter.get_available_qty",
        args: {
            item_code: row.item_code,
            warehouse: WH
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            let available = flt(d.actual_qty || 0);

            if (available <= 0) {
                frappe.msgprint({
                    title: __("No Stock"),
                    indicator: "red",
                    message: __("This item has no stock in Pharmacy - KPWS and cannot be selected.")
                });

                frappe.model.set_value(cdt, cdn, "item_code", "");
                return;
            }

            if (flt(row.qty || 0) > available) {
                frappe.msgprint({
                    title: __("Insufficient Stock"),
                    indicator: "orange",
                    message: __("Available stock in Pharmacy - KPWS is ") + available
                });
            }
        }
    });
}
'''

    # Add helper once.
    if "function kpws_pharmacy_stock_filter_setup(frm)" not in script:
        script = script.rstrip() + "\n\n" + helper + "\n"

    # Make setup call inside common setup functions if present.
    for fn in ["kpws_light_setup(frm)", "kpws_si_setup(frm)", "kpws_unified_setup(frm)"]:
        marker = fn + " {"
        if marker in script and "kpws_pharmacy_stock_filter_setup(frm);" not in script.split(marker, 1)[1].split("}", 1)[0]:
            script = script.replace(
                marker,
                marker + "\n    kpws_pharmacy_stock_filter_setup(frm);",
                1,
            )

    # If no known setup function exists, add Sales Invoice events.
    if "kpws_pharmacy_stock_filter_setup(frm);" not in script:
        script = script.rstrip() + r'''

frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_pharmacy_stock_filter_setup(frm);
    },
    refresh(frm) {
        kpws_pharmacy_stock_filter_setup(frm);
    }
});
''' + "\n"

    if "frappe.ui.form.on(\"Sales Invoice Item\"" not in script and "frappe.ui.form.on('Sales Invoice Item'" not in script:
        script = script.rstrip() + r'''

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        kpws_pharmacy_stock_check_row(frm, cdt, cdn);
    },
    qty(frm, cdt, cdn) {
        kpws_pharmacy_stock_check_row(frm, cdt, cdn);
    }
});
''' + "\n"
    else:
        # Existing child table handlers may exist; add a separate safe handler block with unique functions.
        script = script.rstrip() + r'''

// KPWS safe stock check handlers
frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        kpws_pharmacy_stock_check_row(frm, cdt, cdn);
    },
    qty(frm, cdt, cdn) {
        kpws_pharmacy_stock_check_row(frm, cdt, cdn);
    }
});
''' + "\n"

    doc.script = script
    doc.enabled = 1
    doc.dt = "Sales Invoice"
    doc.view = "Form"
    doc.save(ignore_permissions=True)

    print("Updated Client Script:", script_name)


def audit_sample(limit=20):
    print("Items with stock in", WAREHOUSE)
    rows = frappe.db.sql(
        """
        SELECT
            i.name,
            i.item_name,
            b.actual_qty
        FROM `tabItem` i
        INNER JOIN `tabBin` b
            ON b.item_code = i.name
            AND b.warehouse = %s
        WHERE
            IFNULL(i.disabled, 0) = 0
            AND IFNULL(i.is_stock_item, 0) = 1
            AND IFNULL(b.actual_qty, 0) > 0
        ORDER BY b.actual_qty DESC
        LIMIT %s
        """,
        (WAREHOUSE, int(limit)),
        as_dict=True,
    )

    for r in rows:
        print(r.name, "|", r.item_name, "| Available:", r.actual_qty)

    print("Total shown:", len(rows))


def install():
    if not _warehouse_exists():
        frappe.throw(_("Warehouse {0} does not exist.").format(WAREHOUSE))

    install_client_filter()
    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("DONE: Sales Invoice item selector now only shows items with stock in Pharmacy - KPWS.")
