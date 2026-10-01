import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Sales Invoice Standard Patient Flow"
MODULE_PATH = frappe.get_app_path("kpws_customization", "api", "kpws_sales_invoice_final.py")


SERVER_APPEND = r'''

# --- KPWS POS Profile price list helper ---
@frappe.whitelist()
def get_price_list_for_pos_profile(pos_profile=None, patient_type=None):
    pos_profile = pos_profile or ""
    patient_type = patient_type or ""

    if pos_profile and frappe.db.exists("POS Profile", pos_profile):
        meta = frappe.get_meta("POS Profile")

        # ERPNext POS Profile normally has selling_price_list.
        for fieldname in ["selling_price_list", "price_list"]:
            if meta.get_field(fieldname):
                value = frappe.db.get_value("POS Profile", pos_profile, fieldname)
                if value:
                    return value

    text = (str(pos_profile or "") + " " + str(patient_type or "")).lower()

    if "panel" in text:
        for price_list in ["SPP - Selling Price Panel", "SPP"]:
            if frappe.db.exists("Price List", price_list):
                return price_list

    if "welfare" in text:
        for price_list in ["SPW - Selling Price Welfare", "SPW"]:
            if frappe.db.exists("Price List", price_list):
                return price_list

    if "cash" in text:
        for price_list in ["SPC - Selling Price Cash", "SPC", "SPW - Selling Price Welfare"]:
            if frappe.db.exists("Price List", price_list):
                return price_list

    # Last fallback to existing helper if available.
    try:
        return price_list_for_type(patient_type)
    except Exception:
        return ""
'''


HELPER_JS = r'''
function kpws_si_apply_pos_profile_price_list(frm) {
    if (!kpws_si_has(frm, "pos_profile") || !frm.doc.pos_profile) {
        return Promise.resolve();
    }

    return new Promise(function(resolve) {
        frappe.call({
            method: "kpws_customization.api.kpws_sales_invoice_final.get_price_list_for_pos_profile",
            args: {
                pos_profile: frm.doc.pos_profile,
                patient_type: frm.doc.custom_kpws_billing_type || ""
            },
            freeze: false,
            callback: function(r) {
                let price_list = r.message || "";

                if (price_list && kpws_si_has(frm, "selling_price_list") && frm.doc.selling_price_list !== price_list) {
                    frm.set_value("selling_price_list", price_list).then(function() {
                        frm.refresh_field("selling_price_list");

                        // Refresh item rates only after price list changes.
                        if (frm.doc.items && frm.doc.items.length) {
                            frm.doc.items.forEach(function(row) {
                                if (row.item_code) {
                                    frappe.model.set_value(row.doctype, row.name, "price_list_rate", 0);
                                    frappe.model.set_value(row.doctype, row.name, "rate", 0);
                                }
                            });
                            frm.refresh_field("items");
                        }

                        resolve();
                    });
                } else {
                    resolve();
                }
            },
            error: function() {
                resolve();
            }
        });
    });
}
'''


def patch_server_module():
    text = open(MODULE_PATH).read()

    if "def get_price_list_for_pos_profile" not in text:
        with open(MODULE_PATH, "a") as f:
            f.write(SERVER_APPEND)
        print("Added server helper: get_price_list_for_pos_profile")
    else:
        print("Server helper already exists")


def patch_client_script():
    if not frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        raise Exception(f"Client Script not found: {CLIENT_SCRIPT_NAME}")

    doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
    script = doc.script or ""

    # Add helper function if missing.
    if "function kpws_si_apply_pos_profile_price_list(frm)" not in script:
        insert_before = "function kpws_si_load_context(frm)"
        if insert_before in script:
            script = script.replace(insert_before, HELPER_JS + "\n\n" + insert_before)
        else:
            script += "\n\n" + HELPER_JS + "\n"
        print("Added JS helper: kpws_si_apply_pos_profile_price_list")
    else:
        print("JS helper already exists")

    # Make patient/MR context fetch use loading overlay.
    script = script.replace(
        "freeze: false,\n        callback: function(r) {",
        "freeze: true,\n        freeze_message: __('Loading patient billing details...'),\n        callback: function(r) {",
    )

    # Ensure POS Profile change applies price list.
    if "kpws_si_apply_pos_profile_price_list(frm)" not in script.split("function kpws_si_apply_pos_profile_price_list(frm)")[0]:
        # If pos_profile event already exists, strengthen it.
        if "pos_profile(frm)" in script:
            script = script.replace(
                "pos_profile(frm) {\n        setTimeout(() => kpws_si_apply_payment_split(frm), 700);\n    },",
                """pos_profile(frm) {
        frappe.dom.freeze(__('Loading price list from POS Profile...'));
        kpws_si_apply_pos_profile_price_list(frm).then(function() {
            kpws_si_apply_payment_split(frm);
            frappe.dom.unfreeze();
        });
    },""",
            )
        else:
            # Insert before validate event if available, otherwise before patient.
            if "validate(frm)" in script:
                script = script.replace(
                    "validate(frm) {",
                    """pos_profile(frm) {
        frappe.dom.freeze(__('Loading price list from POS Profile...'));
        kpws_si_apply_pos_profile_price_list(frm).then(function() {
            kpws_si_apply_payment_split(frm);
            frappe.dom.unfreeze();
        });
    },
    validate(frm) {""",
                )
            else:
                script = script.replace(
                    "patient(frm) {",
                    """pos_profile(frm) {
        frappe.dom.freeze(__('Loading price list from POS Profile...'));
        kpws_si_apply_pos_profile_price_list(frm).then(function() {
            kpws_si_apply_payment_split(frm);
            frappe.dom.unfreeze();
        });
    },
    patient(frm) {""",
                )

        print("POS Profile event patched")

    # After patient context updates POS Profile, apply POS price list before payments.
    old_block = """frm.set_value(updates).then(function() {
                kpws_si_toggle(frm);
                kpws_si_apply_payment_split(frm);
                frm.refresh_fields();
            });"""

    new_block = """frm.set_value(updates).then(function() {
                kpws_si_toggle(frm);
                frappe.dom.freeze(__('Applying POS Profile and Price List...'));
                kpws_si_apply_pos_profile_price_list(frm).then(function() {
                    kpws_si_apply_payment_split(frm);
                    frm.refresh_fields();
                    frappe.dom.unfreeze();
                });
            });"""

    if old_block in script:
        script = script.replace(old_block, new_block)
        print("Patient context callback patched to apply POS Profile price list")
    elif "Applying POS Profile and Price List" not in script:
        print("Warning: exact context callback block not found. Helper and pos_profile event still patched.")

    doc.script = script
    doc.enabled = 1
    doc.save(ignore_permissions=True)

    print("Updated Client Script:", CLIENT_SCRIPT_NAME)


def run():
    patch_server_module()
    patch_client_script()

    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("DONE")
    print("Sales Invoice now shows loading during patient/MR fetch and applies price list from selected POS Profile.")

