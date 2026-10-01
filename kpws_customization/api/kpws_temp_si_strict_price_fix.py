import frappe

MODULE_PATH = frappe.get_app_path("kpws_customization", "api", "kpws_sales_invoice_final.py")
HOOKS_PATH = frappe.get_app_path("kpws_customization", "hooks.py")
CLIENT_SCRIPT_NAME = "KPWS FINAL Strict Price List Enforcement"


SERVER_APPEND = r'''

# --- KPWS STRICT price list enforcement ---
def kpws_strict_find_price_list(kind):
    kind = str(kind or "").lower()

    if kind == "panel":
        candidates = ["SPP - Selling Price Panel", "SPP", "Selling Price Panel"]
    else:
        candidates = ["SPW - Selling Price Welfare", "SPW", "Selling Price Welfare"]

    for price_list in candidates:
        if frappe.db.exists("Price List", price_list):
            return price_list

    return ""

def kpws_strict_patient_type_from_doc_or_profile(doc=None, pos_profile=None, patient_type=None):
    text = " ".join([
        str(patient_type or ""),
        str(pos_profile or ""),
        str(doc.get("custom_kpws_billing_type") if doc else ""),
        str(doc.get("pos_profile") if doc else ""),
        str(doc.get("customer_group") if doc else ""),
    ]).lower()

    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"

@frappe.whitelist()
def get_strict_price_list(pos_profile=None, patient_type=None):
    patient_type = kpws_strict_patient_type_from_doc_or_profile(
        pos_profile=pos_profile,
        patient_type=patient_type,
    )

    if patient_type == "Panel":
        return kpws_strict_find_price_list("panel")

    # Cash and Welfare always SPW
    return kpws_strict_find_price_list("cash")

@frappe.whitelist()
def get_price_list_for_pos_profile(pos_profile=None, patient_type=None):
    return get_strict_price_list(pos_profile=pos_profile, patient_type=patient_type)

def price_list_for_type(patient_type):
    return get_strict_price_list(patient_type=patient_type)

def enforce_strict_price_list_on_sales_invoice(doc, method=None):
    patient_type = kpws_strict_patient_type_from_doc_or_profile(doc=doc)

    if patient_type == "Panel":
        target = kpws_strict_find_price_list("panel")
    else:
        target = kpws_strict_find_price_list("cash")

    if target and doc.get("selling_price_list") != target:
        doc.selling_price_list = target
'''


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_strict_price_apply_later(frm);
    },
    onload(frm) {
        kpws_strict_price_apply_later(frm);
    },
    refresh(frm) {
        kpws_strict_price_apply_later(frm);
    },
    pos_profile(frm) {
        kpws_strict_price_apply_now(frm, true);
    },
    custom_kpws_billing_type(frm) {
        kpws_strict_price_apply_now(frm, true);
    },
    patient(frm) {
        kpws_strict_price_apply_later(frm);
    },
    customer(frm) {
        kpws_strict_price_apply_later(frm);
    },
    custom_kpws_mr_number(frm) {
        kpws_strict_price_apply_later(frm);
    },
    before_save(frm) {
        return kpws_strict_price_apply_now(frm, false);
    },
    validate(frm) {
        return kpws_strict_price_apply_now(frm, false);
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        kpws_strict_price_apply_later(frm);
    },
    items_add(frm, cdt, cdn) {
        kpws_strict_price_apply_later(frm);
    }
});

function kpws_strict_price_patient_type(frm) {
    let txt = [
        frm.doc.custom_kpws_billing_type || "",
        frm.doc.pos_profile || "",
        frm.doc.customer_group || ""
    ].join(" ").toLowerCase();

    if (txt.includes("panel")) return "Panel";
    if (txt.includes("welfare")) return "Welfare";
    return "Cash";
}

function kpws_strict_price_apply_later(frm) {
    setTimeout(function() { kpws_strict_price_apply_now(frm, false); }, 300);
    setTimeout(function() { kpws_strict_price_apply_now(frm, false); }, 1200);
    setTimeout(function() { kpws_strict_price_apply_now(frm, false); }, 2500);
}

function kpws_strict_price_apply_now(frm, show_loader) {
    if (!frm.doc.pos_profile && !frm.doc.custom_kpws_billing_type) {
        return Promise.resolve();
    }

    if (frm.__kpws_strict_price_running) {
        return Promise.resolve();
    }

    frm.__kpws_strict_price_running = true;

    if (show_loader) {
        frappe.dom.freeze(__("Applying KPWS price list..."));
    }

    return new Promise(function(resolve) {
        frappe.call({
            method: "kpws_customization.api.kpws_sales_invoice_final.get_strict_price_list",
            args: {
                pos_profile: frm.doc.pos_profile || "",
                patient_type: kpws_strict_price_patient_type(frm)
            },
            freeze: false,
            callback: function(r) {
                let target = r.message || "";

                if (!target) {
                    frm.__kpws_strict_price_running = false;
                    if (show_loader) frappe.dom.unfreeze();
                    resolve();
                    return;
                }

                if (frm.doc.selling_price_list !== target) {
                    frm.set_value("selling_price_list", target).then(function() {
                        frm.refresh_field("selling_price_list");

                        if (frm.doc.items && frm.doc.items.length) {
                            frm.doc.items.forEach(function(row) {
                                if (row.item_code) {
                                    frappe.model.set_value(row.doctype, row.name, "price_list_rate", 0);
                                    frappe.model.set_value(row.doctype, row.name, "rate", 0);
                                }
                            });
                            frm.refresh_field("items");
                        }

                        frm.__kpws_strict_price_running = false;
                        if (show_loader) frappe.dom.unfreeze();
                        resolve();
                    });
                } else {
                    frm.__kpws_strict_price_running = false;
                    if (show_loader) frappe.dom.unfreeze();
                    resolve();
                }
            },
            error: function() {
                frm.__kpws_strict_price_running = false;
                if (show_loader) frappe.dom.unfreeze();
                resolve();
            }
        });
    });
}
'''


def price_list_exists(*names):
    for name in names:
        if frappe.db.exists("Price List", name):
            return name
    return ""


def update_pos_profiles():
    spw = price_list_exists("SPW - Selling Price Welfare", "SPW", "Selling Price Welfare")
    spp = price_list_exists("SPP - Selling Price Panel", "SPP", "Selling Price Panel")

    if not spw:
        frappe.throw("Price List not found: SPW - Selling Price Welfare / SPW")

    if not spp:
        frappe.throw("Price List not found: SPP - Selling Price Panel / SPP")

    if not frappe.db.exists("DocType", "POS Profile"):
        return

    meta = frappe.get_meta("POS Profile")
    if not meta.get_field("selling_price_list"):
        print("POS Profile has no selling_price_list field. Skipping POS Profile master update.")
        return

    for row in frappe.get_all("POS Profile", fields=["name"], limit=200):
        name_l = row.name.lower()

        if "panel" in name_l:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spp, update_modified=False)
            print("POS Profile:", row.name, "=>", spp)

        elif "welfare" in name_l or "cash" in name_l:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spw, update_modified=False)
            print("POS Profile:", row.name, "=>", spw)


def patch_server_module():
    text = open(MODULE_PATH).read()

    marker = "# --- KPWS STRICT price list enforcement ---"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n\n" + SERVER_APPEND
        print("Replaced strict price enforcement block")
    else:
        text = text.rstrip() + "\n\n" + SERVER_APPEND
        print("Added strict price enforcement block")

    open(MODULE_PATH, "w").write(text)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable all older Sales Invoice price list scripts.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        txt = ((row.name or "") + "\n" + (row.script or "")).lower()
        if "price list" in txt or "selling_price_list" in txt:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled older price script:", row.name)

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Sales Invoice"
        doc.view = "Form"
        doc.script = CLIENT_SCRIPT
        doc.save(ignore_permissions=True)
        print("Updated:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
        print("Created:", CLIENT_SCRIPT_NAME)


def patch_hooks():
    text = open(HOOKS_PATH).read()
    method = "kpws_customization.api.kpws_sales_invoice_final.enforce_strict_price_list_on_sales_invoice"

    if method not in text:
        text += f"""

# KPWS strict Sales Invoice price list enforcement
doc_events = globals().get("doc_events", {{}})
doc_events.setdefault("Sales Invoice", {{}})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "{method}" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("{method}")
"""
        open(HOOKS_PATH, "w").write(text)
        print("Added validate hook:", method)
    else:
        print("Validate hook already exists")


def run():
    update_pos_profiles()
    patch_server_module()
    install_client_script()
    patch_hooks()

    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("Verification from server helper:")
    mod = frappe.get_attr("kpws_customization.api.kpws_sales_invoice_final")
    for pos_profile, patient_type in [
        ("Cash", "Cash"),
        ("Welfare", "Welfare"),
        ("Panel", "Panel"),
    ]:
        print(pos_profile, patient_type, "=>", mod.get_strict_price_list(pos_profile, patient_type))

    print("")
    print("DONE: Strict price list applied.")
    print("Cash/Welfare => SPW - Selling Price Welfare")
    print("Panel => SPP - Selling Price Panel")
