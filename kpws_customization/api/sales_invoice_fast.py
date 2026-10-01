import frappe


@frappe.whitelist()
def get_sales_invoice_context(patient=None, customer=None, company=None):
    out = {
        "customer": customer,
        "customer_group": "",
        "is_panel_customer": 0,
        "group_key": "",
        "pos_profile": "",
        "selling_price_list": "",
        "welfare": None,
    }

    # 1. If Patient has Panel Name / panel customer, use it as invoice customer
    if patient:
        patient_meta = frappe.get_meta("Patient")
        panel_field = None

        for f in ["panel_name", "custom_panel_name", "custom_panel", "panel", "customer"]:
            if patient_meta.get_field(f):
                panel_field = f
                break

        if panel_field:
            panel_customer = frappe.db.get_value("Patient", patient, panel_field)

            if panel_customer and frappe.db.exists("Customer", panel_customer):
                is_panel = frappe.db.get_value("Customer", panel_customer, "custom_is_panel") or 0
                if is_panel:
                    out["customer"] = panel_customer

    # 2. Read customer group
    if out["customer"]:
        customer_group = frappe.db.get_value("Customer", out["customer"], "customer_group") or ""
        is_panel_customer = frappe.db.get_value("Customer", out["customer"], "custom_is_panel") or 0

        out["customer_group"] = customer_group
        out["is_panel_customer"] = int(is_panel_customer or 0)

        text = str(customer_group or "").lower()

        if is_panel_customer or "panel" in text:
            out["group_key"] = "panel"
        elif "welfare" in text:
            out["group_key"] = "welfare"
        elif "cash" in text:
            out["group_key"] = "cash"

    # 3. Price list mapping
    if out["group_key"] == "panel":
        out["selling_price_list"] = "SPP - Selling Price Panel"
    elif out["group_key"] == "welfare":
        out["selling_price_list"] = "SPW - Selling Price Welfare"
    elif out["group_key"] == "cash":
        out["selling_price_list"] = "SPW - Selling Price Welfare"

    # 4. POS Profile mapping
    possible_names = {
        "panel": ["Panel", "KPWS Panel", "Panel - KPWS"],
        "welfare": ["Welfare", "KPWS Welfare", "Welfare - KPWS"],
        "cash": ["Cash", "KPWS Cash", "Cash - KPWS"],
    }.get(out["group_key"], [])

    for profile_name in possible_names:
        if frappe.db.exists("POS Profile", profile_name):
            out["pos_profile"] = profile_name
            break

    if not out["pos_profile"] and out["group_key"]:
        profiles = frappe.get_all(
            "POS Profile",
            filters={"disabled": 0},
            fields=["name"],
            limit=100
        )

        for p in profiles:
            if out["group_key"] in str(p.name or "").lower():
                out["pos_profile"] = p.name
                break

    # 5. Welfare registration percentage
    if patient and out["group_key"] == "welfare":
        regs = frappe.get_all(
            "Patient Registration Form",
            filters={
                "patient_name": patient,
                "workflow_state": "Approved"
            },
            fields=["name", "discount_type", "discount_value", "purpose"],
            order_by="modified desc",
            limit=1
        )

        if regs:
            reg = regs[0]
            out["welfare"] = {
                "registration": reg.name,
                "discount_type": reg.discount_type or "Percentage",
                "discount_value": float(reg.discount_value or 0),
                "purpose": reg.purpose or "Donation",
            }

    return out
