from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_WALKIN_SETTINGS_FIX_V18_PATCH"


SERVER_PATCH = r'''

# KPWS_WALKIN_SETTINGS_FIX_V18_PATCH

def _ensure_settings_doc():
    """
    Safe read-only settings loader.

    Previous version saved the Single Settings doc during normal API calls.
    That caused TimestampMismatchError when POS screen called patient/walk-in APIs quickly.
    Defaults are now fixed by installer/settings save, not during every read.
    """
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        frappe.throw(_("Settings DocType is not installed."))

    return frappe.get_single(SETTINGS_DOCTYPE)


def _kpws_get_or_create_walkin_cash_customer():
    customer_name = "Walk-in Cash Customer - KPWS"

    # Use existing configured customer if set.
    try:
        settings = frappe.get_single(SETTINGS_DOCTYPE)
        if settings.get("default_cash_customer") and frappe.db.exists("Customer", settings.default_cash_customer):
            return settings.default_cash_customer
    except Exception:
        pass

    # Prefer existing Cash customer if available.
    for name in [
        "Cash",
        "Cash Customer",
        "Walk-in Cash Customer - KPWS",
        "Walk In Customer - KPWS",
    ]:
        if frappe.db.exists("Customer", name):
            return name

    if not frappe.db.exists("Customer Group", "Cash"):
        try:
            parent = frappe.db.get_value("Customer Group", {"is_group": 1}, "name")
            frappe.get_doc({
                "doctype": "Customer Group",
                "customer_group_name": "Cash",
                "parent_customer_group": parent,
                "is_group": 0,
            }).insert(ignore_permissions=True)
        except Exception:
            pass

    if not frappe.db.exists("Territory", "Pakistan"):
        try:
            parent = frappe.db.get_value("Territory", {"is_group": 1}, "name")
            frappe.get_doc({
                "doctype": "Territory",
                "territory_name": "Pakistan",
                "parent_territory": parent,
                "is_group": 0,
            }).insert(ignore_permissions=True)
        except Exception:
            pass

    doc = frappe.new_doc("Customer")
    doc.customer_name = customer_name
    doc.customer_type = "Individual"

    if frappe.db.exists("Customer Group", "Cash"):
        doc.customer_group = "Cash"
    else:
        doc.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")

    if frappe.db.exists("Territory", "Pakistan"):
        doc.territory = "Pakistan"
    else:
        doc.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return doc.name


@frappe.whitelist()
def repair_walkin_settings():
    _require_role()

    # Only managers should repair settings from UI/API.
    roles = set(frappe.get_roles())
    if not roles.intersection({"System Manager", "Accounts Manager"}):
        frappe.throw(_("Only System Manager or Accounts Manager can repair Pharmacy Billing Settings."), frappe.PermissionError)

    settings = frappe.get_single(SETTINGS_DOCTYPE)

    values = {}

    if not settings.get("company"):
        company = _first_company()
        if company:
            values["company"] = company

    if not settings.get("pharmacy_warehouse"):
        for wh in ["Pharmacy - KPWS"]:
            if frappe.db.exists("Warehouse", wh):
                values["pharmacy_warehouse"] = wh
                break

    if not settings.get("cash_price_list"):
        for pl in ["SPW – Selling Price Welfare", "SPW - Selling Price Welfare", "Standard Selling"]:
            if frappe.db.exists("Price List", pl):
                values["cash_price_list"] = pl
                break

    if not settings.get("welfare_price_list"):
        for pl in ["SPW – Selling Price Welfare", "SPW - Selling Price Welfare", "Standard Selling"]:
            if frappe.db.exists("Price List", pl):
                values["welfare_price_list"] = pl
                break

    if not settings.get("panel_price_list"):
        for pl in ["SPP – Selling Price Panel", "SPP - Selling Price Panel", "Standard Selling"]:
            if frappe.db.exists("Price List", pl):
                values["panel_price_list"] = pl
                break

    if not settings.get("cash_mode_of_payment"):
        for mop in ["Cash", "CASH"]:
            if frappe.db.exists("Mode of Payment", mop):
                values["cash_mode_of_payment"] = mop
                break

    if not settings.get("default_mode_of_payment"):
        if values.get("cash_mode_of_payment"):
            values["default_mode_of_payment"] = values["cash_mode_of_payment"]
        else:
            mop = frappe.db.get_value("Mode of Payment", {"enabled": 1}, "name") or frappe.db.get_value("Mode of Payment", {}, "name")
            if mop:
                values["default_mode_of_payment"] = mop

    if not settings.get("card_mode_of_payment"):
        for mop in ["Card", "Credit Card", "Debit Card", "Bank Card"]:
            if frappe.db.exists("Mode of Payment", mop):
                values["card_mode_of_payment"] = mop
                break

    if not settings.get("default_cash_customer"):
        values["default_cash_customer"] = _kpws_get_or_create_walkin_cash_customer()

    if values:
        for key, value in values.items():
            frappe.db.set_single_value(SETTINGS_DOCTYPE, key, value)

    frappe.db.commit()
    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)

    return {
        "ok": True,
        "updated_values": values,
        "settings": _settings_dict(frappe.get_single(SETTINGS_DOCTYPE)),
    }
'''


def _append_once(path, patch, marker):
    p = Path(path)
    text = p.read_text()

    if marker in text:
        return False

    p.write_text(text + "\n\n" + patch)
    return True


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"

    changed = _append_once(api_file, SERVER_PATCH, PATCH_MARKER)

    frappe.clear_cache()
    frappe.db.commit()

    # Run repair as Administrator/system context from bench.
    from kpws_customization.api.kpws_pharmacy_billing_desk import repair_walkin_settings
    result = repair_walkin_settings()

    return {
        "ok": True,
        "server_changed": changed,
        "repair_result": result,
        "message": "Walk-in settings fixed and settings loader made safe."
    }
