import frappe

MODULE_PATH = frappe.get_app_path("kpws_customization", "api", "kpws_sales_invoice_final.py")

APPEND_CODE = r'''

# --- KPWS forced price list mapping override ---
def _kpws_existing_price_list(candidates):
    for price_list in candidates:
        if frappe.db.exists("Price List", price_list):
            return price_list
    return ""

def _kpws_patient_type_from_profile_or_type(pos_profile=None, patient_type=None):
    text = (str(patient_type or "") + " " + str(pos_profile or "")).lower()

    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"

@frappe.whitelist()
def get_price_list_for_pos_profile(pos_profile=None, patient_type=None):
    patient_type = _kpws_patient_type_from_profile_or_type(pos_profile, patient_type)

    if patient_type == "Panel":
        return _kpws_existing_price_list([
            "SPP",
            "SPP - Selling Price Panel",
            "Selling Price Panel",
        ])

    if patient_type == "Welfare":
        return _kpws_existing_price_list([
            "SPW",
            "SPW - Selling Price Welfare",
            "Selling Price Welfare",
        ])

    # Cash: first try SPC, then fallback to SPW
    return _kpws_existing_price_list([
        "SPC",
        "SPC - Selling Price Cash",
        "Selling Price Cash",
        "SPW",
        "SPW - Selling Price Welfare",
        "Selling Price Welfare",
    ])

def price_list_for_type(patient_type):
    patient_type = _kpws_patient_type_from_profile_or_type(None, patient_type)

    if patient_type == "Panel":
        return _kpws_existing_price_list([
            "SPP",
            "SPP - Selling Price Panel",
            "Selling Price Panel",
        ])

    if patient_type == "Welfare":
        return _kpws_existing_price_list([
            "SPW",
            "SPW - Selling Price Welfare",
            "Selling Price Welfare",
        ])

    return _kpws_existing_price_list([
        "SPC",
        "SPC - Selling Price Cash",
        "Selling Price Cash",
        "SPW",
        "SPW - Selling Price Welfare",
        "Selling Price Welfare",
    ])
'''

def run():
    text = open(MODULE_PATH).read()

    marker = "# --- KPWS forced price list mapping override ---"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n\n" + APPEND_CODE
        print("Replaced previous forced price list override")
    else:
        text = text.rstrip() + "\n\n" + APPEND_CODE
        print("Added forced price list override")

    open(MODULE_PATH, "w").write(text)

    print("")
    print("Testing mapping now:")
    mod = frappe.get_attr("kpws_customization.api.kpws_sales_invoice_final")

    for patient_type in ["Cash", "Welfare", "Panel"]:
        print(patient_type, "=>", mod.price_list_for_type(patient_type))

    print("")
    print("DONE: Price list mapping forced.")

