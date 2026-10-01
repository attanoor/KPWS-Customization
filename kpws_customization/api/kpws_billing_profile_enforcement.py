import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Billing Profile Enforcement"


def _first_existing(doctype, names):
    for name in names:
        if name and frappe.db.exists(doctype, name):
            return name
    return ""


def _txt(value):
    return str(value or "").strip().lower()


def _billing_type_from_text(value):
    text = _txt(value)
    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"


def _get_patient_by_mr(mr_number):
    if not mr_number:
        return ""

    mr_number = str(mr_number).strip()

    if frappe.db.exists("Patient", mr_number):
        return mr_number

    meta = frappe.get_meta("Patient")
    for fieldname in ["custom_mr_number", "mr_number", "uid", "patient_id"]:
        if meta.get_field(fieldname):
            patient = frappe.db.get_value("Patient", {fieldname: mr_number}, "name")
            if patient:
                return patient

    return ""


def _customer_is_panel(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False

    if frappe.get_meta("Customer").get_field("custom_is_panel"):
        return bool(frappe.db.get_value("Customer", customer, "custom_is_panel"))

    return False


def _linked_customer_from_patient(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return ""

    p = frappe.get_doc("Patient", patient)

    for fieldname in ["customer", "custom_patient_customer"]:
        if p.meta.get_field(fieldname) and p.get(fieldname):
            return p.get(fieldname)

    return ""


def _patient_group(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return ""

    p = frappe.get_doc("Patient", patient)

    for fieldname in ["customer_group", "custom_patient_billing_type", "custom_billing_type"]:
        if p.meta.get_field(fieldname) and p.get(fieldname):
            return p.get(fieldname)

    customer = _linked_customer_from_patient(patient)

    if customer and frappe.db.exists("Customer", customer):
        return frappe.db.get_value("Customer", customer, "customer_group") or ""

    return ""


def _customer_group(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return ""

    if _customer_is_panel(customer):
        return "Panel"

    return frappe.db.get_value("Customer", customer, "customer_group") or ""


def _panel_customer_from_patient(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return ""

    p = frappe.get_doc("Patient", patient)

    for fieldname in ["custom_panel_customer", "panel_name", "panel_customer"]:
        if p.meta.get_field(fieldname) and p.get(fieldname):
            return p.get(fieldname)

    return ""


def _pos_profile_for_type(patient_type):
    if patient_type == "Panel":
        return _first_existing("POS Profile", ["Panel", "KPWS Panel", "Panel - KPWS"])

    if patient_type == "Welfare":
        return _first_existing("POS Profile", ["Welfare", "KPWS Welfare", "Welfare - KPWS"])

    return _first_existing("POS Profile", ["Cash", "KPWS Cash", "Cash - KPWS"])


def _price_list_for_type(patient_type):
    if patient_type == "Panel":
        return _first_existing("Price List", ["SPP - Selling Price Panel", "SPP", "Selling Price Panel"])

    # Cash and Welfare both use SPW
    return _first_existing("Price List", ["SPW - Selling Price Welfare", "SPW", "Selling Price Welfare"])


def _cash_customer():
    return _first_existing("Customer", ["Walk-in Customer", "Walk In Customer", "Cash Customer"])


@frappe.whitelist()
def get_billing_profile(patient=None, customer=None, mr_number=None, is_walkin=0):
    is_walkin = int(is_walkin or 0)

    if is_walkin:
        patient_type = "Cash"
        return {
            "patient": "",
            "customer": customer or _cash_customer(),
            "patient_type": patient_type,
            "panel_customer": "",
            "pos_profile": _pos_profile_for_type(patient_type),
            "selling_price_list": _price_list_for_type(patient_type),
            "is_pos": 1,
        }

    if not patient and mr_number:
        patient = _get_patient_by_mr(mr_number)

    linked_customer = ""

    if patient:
        linked_customer = _linked_customer_from_patient(patient)
        patient_type = _billing_type_from_text(_patient_group(patient))
    elif customer:
        linked_customer = customer
        patient_type = _billing_type_from_text(_customer_group(customer))
    else:
        patient_type = "Cash"

    invoice_customer = linked_customer
    panel_customer = ""

    if patient_type == "Panel" and patient:
        panel_customer = _panel_customer_from_patient(patient)
        if panel_customer:
            invoice_customer = panel_customer

    return {
        "patient": patient or "",
        "customer": invoice_customer or customer or "",
        "patient_customer": linked_customer,
        "patient_type": patient_type,
        "panel_customer": panel_customer,
        "pos_profile": _pos_profile_for_type(patient_type),
        "selling_price_list": _price_list_for_type(patient_type),
        "is_pos": 0 if patient_type == "Panel" else 1,
    }


def enforce_on_sales_invoice(doc, method=None):
    profile = get_billing_profile(
        patient=doc.get("patient"),
        customer=doc.get("customer"),
        mr_number=doc.get("custom_kpws_mr_number"),
        is_walkin=doc.get("custom_is_walkin"),
    )

    if profile.get("patient_type"):
        doc.custom_kpws_billing_type = profile.get("patient_type")

    if profile.get("pos_profile"):
        doc.pos_profile = profile.get("pos_profile")

    if profile.get("selling_price_list"):
        doc.selling_price_list = profile.get("selling_price_list")

    if profile.get("panel_customer") and doc.meta.get_field("custom_panel"):
        doc.custom_panel = profile.get("panel_customer")


def update_pos_profile_masters():
    spw = _price_list_for_type("Cash")
    spp = _price_list_for_type("Panel")

    if not spw:
        frappe.throw("SPW - Selling Price Welfare price list not found.")

    if not spp:
        frappe.throw("SPP - Selling Price Panel price list not found.")

    if not frappe.db.exists("DocType", "POS Profile"):
        return

    meta = frappe.get_meta("POS Profile")
    if not meta.get_field("selling_price_list"):
        print("POS Profile has no selling_price_list field.")
        return

    for row in frappe.get_all("POS Profile", fields=["name"], limit=200):
        name_l = row.name.lower()

        if "panel" in name_l:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spp, update_modified=False)
            print("POS Profile:", row.name, "=>", spp)

        elif "cash" in name_l or "welfare" in name_l:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spw, update_modified=False)
            print("POS Profile:", row.name, "=>", spw)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_billing_profile_setup(frm);
    },
    onload(frm) {
        kpws_billing_profile_apply_later(frm);
    },
    refresh(frm) {
        kpws_billing_profile_apply_later(frm);
    },
    patient(frm) {
        kpws_billing_profile_apply_now(frm, true);
    },
    customer(frm) {
        kpws_billing_profile_apply_now(frm, true);
    },
    custom_kpws_mr_number(frm) {
        kpws_billing_profile_apply_now(frm, true);
    },
    custom_is_walkin(frm) {
        kpws_billing_profile_apply_now(frm, true);
    },
    walkin_customer_name(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_billing_profile_apply_later(frm);
        }
    },
    walkin_mr_number(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_billing_profile_apply_later(frm);
        }
    },
    before_save(frm) {
        return kpws_billing_profile_apply_now(frm, false);
    },
    validate(frm) {
        return kpws_billing_profile_apply_now(frm, false);
    }
});

function kpws_billing_profile_setup(frm) {
    ["custom_kpws_billing_type", "custom_panel", "selling_price_list"].forEach(function(fieldname) {
        if (frm.fields_dict[fieldname]) {
            frm.set_df_property(fieldname, "read_only", 1);
        }
    });
}

function kpws_billing_profile_apply_later(frm) {
    setTimeout(function() { kpws_billing_profile_apply_now(frm, false); }, 300);
    setTimeout(function() { kpws_billing_profile_apply_now(frm, false); }, 1200);
    setTimeout(function() { kpws_billing_profile_apply_now(frm, false); }, 2500);
}

function kpws_billing_profile_apply_now(frm, show_loader) {
    if (frm.__kpws_billing_profile_running) {
        return Promise.resolve();
    }

    frm.__kpws_billing_profile_running = true;

    if (show_loader) {
        frappe.dom.freeze(__("Loading patient billing profile..."));
    }

    return new Promise(function(resolve) {
        frappe.call({
            method: "kpws_customization.api.kpws_billing_profile_enforcement.get_billing_profile",
            args: {
                patient: frm.doc.patient || "",
                customer: frm.doc.customer || "",
                mr_number: frm.doc.custom_kpws_mr_number || "",
                is_walkin: frm.doc.custom_is_walkin ? 1 : 0
            },
            freeze: false,
            callback: function(r) {
                let d = r.message || {};
                let updates = {};

                if (d.patient && frm.fields_dict.patient && frm.doc.patient !== d.patient) {
                    updates.patient = d.patient;
                }

                if (d.customer && frm.doc.customer !== d.customer) {
                    updates.customer = d.customer;
                }

                if (frm.fields_dict.custom_kpws_billing_type) {
                    updates.custom_kpws_billing_type = d.patient_type || "";
                }

                if (frm.fields_dict.custom_panel) {
                    updates.custom_panel = d.panel_customer || "";
                }

                if (frm.fields_dict.custom_kpws_panel_customer) {
                    updates.custom_kpws_panel_customer = d.panel_customer || "";
                }

                if (frm.fields_dict.is_pos) {
                    updates.is_pos = d.is_pos ? 1 : 0;
                }

                if (frm.fields_dict.pos_profile && d.pos_profile) {
                    updates.pos_profile = d.pos_profile;
                }

                if (frm.fields_dict.selling_price_list && d.selling_price_list) {
                    updates.selling_price_list = d.selling_price_list;
                }

                frm.set_value(updates).then(function() {
                    frm.refresh_fields();

                    if (typeof kpws_si_apply_payment_split === "function") {
                        setTimeout(function() { kpws_si_apply_payment_split(frm); }, 500);
                    }

                    frm.__kpws_billing_profile_running = false;

                    if (show_loader) {
                        frappe.dom.unfreeze();
                    }

                    resolve();
                });
            },
            error: function() {
                frm.__kpws_billing_profile_running = false;

                if (show_loader) {
                    frappe.dom.unfreeze();
                }

                resolve();
            }
        });
    });
}
'''

    # Disable only scripts that directly set POS Profile from customer group / price list.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if (
            "sales invoice customer pos flow" in text
            or "pos profile price list" in text
            or "strict price list" in text
            or "si price list mapping" in text
        ):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled conflicting POS/price script:", row.name)

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Sales Invoice"
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Client Script:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", CLIENT_SCRIPT_NAME)


def install():
    update_pos_profile_masters()
    install_client_script()
    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("Verification:")
    for patient_type in ["Cash", "Welfare", "Panel"]:
        print(patient_type, "=> POS:", _pos_profile_for_type(patient_type), "| Price List:", _price_list_for_type(patient_type))

    print("")
    print("DONE: POS Profile and Price List now follow Patient/Customer Group.")
