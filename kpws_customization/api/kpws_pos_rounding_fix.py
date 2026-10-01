import frappe
from frappe.utils import flt


def snap_pos_rounding(doc, method=None):
    """
    Final safeguard, runs on before_submit after core total/rounding calculation.

    POS payment amounts (paid_amount / payments table) can be entered or
    calculated against grand_total before ERPNext applies its rounding
    adjustment to produce rounded_total. That leaves a sub-currency-unit
    gap between paid_amount and rounded_total, which shows up as a small
    non-zero outstanding_amount on an invoice that was actually fully paid.

    This only snaps genuine rounding drift (less than one currency unit)
    on POS invoices that already have a payment recorded. It never touches
    invoices with no payment, and never masks a real shortfall.
    """
    if doc.doctype != "Sales Invoice":
        return

    if not doc.get("is_pos"):
        return

    precision = doc.precision("outstanding_amount")
    total = flt(doc.rounded_total or doc.grand_total, precision)
    paid = flt(doc.paid_amount, precision)
    diff = flt(total - paid, precision)

    if paid != 0 and 0 < abs(diff) <= 1:
        doc.paid_amount = total
        doc.base_paid_amount = flt(total * flt(doc.get("conversion_rate") or 1), doc.precision("base_paid_amount"))
        doc.outstanding_amount = 0
