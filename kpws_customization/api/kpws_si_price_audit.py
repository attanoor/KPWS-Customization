import csv
import frappe
from frappe.utils import flt

WAREHOUSE = "Pharmacy - KPWS"
OUT = "/tmp/kpws_pharmacy_missing_item_prices.csv"


def _price_list(names):
    for name in names:
        if frappe.db.exists("Price List", name):
            return name
    return ""


def _rate(item_code, price_list):
    if not item_code or not price_list:
        return None

    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": price_list,
            "selling": 1,
        },
        fields=["name", "price_list_rate", "uom", "valid_from", "valid_upto"],
        order_by="valid_from desc, modified desc",
        limit=1,
    )

    if rows:
        return flt(rows[0].price_list_rate)

    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": price_list,
        },
        fields=["name", "price_list_rate", "uom", "valid_from", "valid_upto"],
        order_by="valid_from desc, modified desc",
        limit=1,
    )

    if rows:
        return flt(rows[0].price_list_rate)

    return None


def audit():
    spw = _price_list(["SPW - Selling Price Welfare", "SPW", "Selling Price Welfare"])
    spp = _price_list(["SPP - Selling Price Panel", "SPP", "Selling Price Panel"])

    if not spw:
        frappe.throw("SPW price list not found.")
    if not spp:
        frappe.throw("SPP price list not found.")

    rows = frappe.db.sql("""
        SELECT
            i.name AS item_code,
            i.item_name,
            i.stock_uom,
            b.actual_qty
        FROM `tabItem` i
        INNER JOIN `tabBin` b
            ON b.item_code = i.name
            AND b.warehouse = %(warehouse)s
        WHERE
            IFNULL(i.disabled, 0) = 0
            AND IFNULL(i.is_stock_item, 0) = 1
            AND IFNULL(b.actual_qty, 0) > 0
        ORDER BY i.item_name, i.name
    """, {"warehouse": WAREHOUSE}, as_dict=True)

    missing = []
    ok = 0

    for r in rows:
        spw_rate = _rate(r.item_code, spw)
        spp_rate = _rate(r.item_code, spp)

        issue = []

        if spw_rate is None or spw_rate <= 0:
            issue.append("Missing SPW")

        if spp_rate is None or spp_rate <= 0:
            issue.append("Missing SPP")

        if issue:
            missing.append({
                "item_code": r.item_code,
                "item_name": r.item_name,
                "stock_uom": r.stock_uom,
                "available_qty": r.actual_qty,
                "spw_price_list": spw,
                "spw_rate": spw_rate,
                "spp_price_list": spp,
                "spp_rate": spp_rate,
                "issue": ", ".join(issue),
            })
        else:
            ok += 1

    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "item_code",
            "item_name",
            "stock_uom",
            "available_qty",
            "spw_price_list",
            "spw_rate",
            "spp_price_list",
            "spp_rate",
            "issue",
        ])
        writer.writeheader()
        writer.writerows(missing)

    print("Warehouse:", WAREHOUSE)
    print("Cash/Welfare Price List:", spw)
    print("Panel Price List:", spp)
    print("Items with stock:", len(rows))
    print("Items with both prices:", ok)
    print("Items missing price:", len(missing))
    print("Report:", OUT)

    print("")
    print("First 30 missing price items:")
    for r in missing[:30]:
        print(r["item_code"], "|", r["item_name"], "| Qty:", r["available_qty"], "|", r["issue"])


@frappe.whitelist()
def get_item_price(item_code=None, price_list=None):
    if not item_code or not price_list:
        return {}

    rate = _rate(item_code, price_list)

    return {
        "item_code": item_code,
        "price_list": price_list,
        "rate": rate or 0,
        "found": bool(rate and rate > 0),
    }
