import os
import frappe
from frappe.utils import now

DT = "Sales Invoice"

FINAL_CLIENT_SCRIPT = "KPWS FINAL Sales Invoice Standard Patient Flow"


def first(doc, fields):
    for f in fields:
        if doc.meta.get_field(f):
            value = doc.get(f)
            if value not in (None, ""):
                return value
    return ""


def norm(text):
    return str(text or "").strip().lower()


def billing_type_from_text(text):
    value = norm(text)
    if "panel" in value:
        return "Panel"
    if "welfare" in value:
        return "Welfare"
    return "Cash"


def field_exists(dt, fieldname):
    return bool(frappe.get_meta(dt).get_field(fieldname))


def customer_is_panel(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False

    if field_exists("Customer", "custom_is_panel"):
        return bool(frappe.db.get_value("Customer", customer, "custom_is_panel"))

    return False


def find_patient_by_mr(mr_number):
    if not mr_number:
        return ""

    mr = str(mr_number).strip()

    # In KPWS, Patient name itself is the MR number: KPWS-####
    if frappe.db.exists("Patient", mr):
        return mr

    meta = frappe.get_meta("Patient")
    for fieldname in ["custom_mr_number", "mr_number", "uid", "patient_id"]:
        if meta.get_field(fieldname):
            patient = frappe.db.get_value("Patient", {fieldname: mr}, "name")
            if patient:
                return patient

    return ""


def find_cash_customer():
    for customer in ["Walk-in Customer", "Walk In Customer", "Cash Customer"]:
        if frappe.db.exists("Customer", customer):
            return customer

    rows = frappe.get_all(
        "Customer",
        filters={"customer_group": ["like", "%Cash%"]},
        fields=["name"],
        limit=1,
    )
    return rows[0].name if rows else ""


def find_pos_profile(patient_type):
    candidates = {
        "Cash": ["Cash", "KPWS Cash", "Cash - KPWS"],
        "Welfare": ["Welfare", "KPWS Welfare", "Welfare - KPWS"],
        "Panel": ["Panel", "KPWS Panel", "Panel - KPWS"],
    }.get(patient_type, ["Cash"])

    for name in candidates:
        if frappe.db.exists("POS Profile", name):
            return name

    rows = frappe.get_all("POS Profile", fields=["name"], limit=100)
    for row in rows:
        if norm(patient_type) in norm(row.name):
            return row.name

    return rows[0].name if rows else ""


def find_mode(names):
    for name in names:
        if frappe.db.exists("Mode of Payment", name):
            return name

    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=100)
    for row in rows:
        row_name = norm(row.name)
        for name in names:
            if norm(name) in row_name:
                return row.name

    return names[0] if names else "Cash"


def price_list_for_type(patient_type):
    if patient_type == "Cash":
        for price_list in ["SPC - Selling Price Cash", "SPC", "SPW - Selling Price Welfare"]:
            if frappe.db.exists("Price List", price_list):
                return price_list

    if patient_type == "Welfare":
        for price_list in ["SPW - Selling Price Welfare", "SPW"]:
            if frappe.db.exists("Price List", price_list):
                return price_list

    if patient_type == "Panel":
        for price_list in ["SPP - Selling Price Panel", "SPP"]:
            if frappe.db.exists("Price List", price_list):
                return price_list

    return ""


def get_patient_type(patient_doc, linked_customer=None):
    patient_type = first(patient_doc, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])

    if not patient_type and linked_customer and frappe.db.exists("Customer", linked_customer):
        patient_type = frappe.db.get_value("Customer", linked_customer, "customer_group")

    return billing_type_from_text(patient_type)


def get_latest_welfare_registration(patient):
    if not frappe.db.exists("DocType", "Patient Registration Form"):
        return {}

    meta = frappe.get_meta("Patient Registration Form")

    fields = ["name", "modified"]

    for fieldname in [
        "custom_patient",
        "patient",
        "purpose",
        "discount_value",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ]:
        if meta.get_field(fieldname):
            fields.append(fieldname)

    query_filters = []

    if meta.get_field("custom_patient"):
        query_filters.append({"custom_patient": patient, "docstatus": ["<", 2]})

    if meta.get_field("patient"):
        query_filters.append({"patient": patient, "docstatus": ["<", 2]})

    for filters in query_filters:
        rows = frappe.get_all(
            "Patient Registration Form",
            filters=filters,
            fields=list(set(fields)),
            order_by="modified desc",
            limit=1,
        )

        if not rows:
            continue

        row = rows[0]

        welfare_type = row.get("purpose") or row.get("custom_kpws_welfare_type") or ""
        welfare_percentage = row.get("discount_value")
        if welfare_percentage in (None, ""):
            welfare_percentage = row.get("custom_kpws_welfare_percentage") or 0

        panel = row.get("custom_panel_customer") or row.get("custom_kpws_assigned_panel_customer") or ""

        return {
            "name": row.name,
            "welfare_type": welfare_type,
            "welfare_percentage": float(welfare_percentage or 0),
            "panel_customer": panel,
        }

    return {}


def set_field_props(fieldname, **props):
    # Update DocField if field exists in meta table.
    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT, "fieldname": fieldname},
        fields=["name"],
        limit=10,
    )
    for row in rows:
        clean = {}
        for k, v in props.items():
            if k in ["hidden", "reqd", "read_only", "print_hide"]:
                clean[k] = int(v)
            else:
                clean[k] = v
        frappe.db.set_value("DocField", row.name, clean, update_modified=False)

    # Update Custom Field record if it exists.
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": DT, "fieldname": fieldname},
        fields=["name"],
        limit=10,
    )
    valid_custom_field_cols = {df.fieldname for df in frappe.get_meta("Custom Field").fields}

    for row in rows:
        clean = {}
        for k, v in props.items():
            if k in valid_custom_field_cols:
                if k in ["hidden", "reqd", "read_only", "print_hide"]:
                    clean[k] = int(v)
                else:
                    clean[k] = v
        if clean:
            frappe.db.set_value("Custom Field", row.name, clean, update_modified=False)

    # Add property setters so Customize Form cache does not override.
    for prop, value in props.items():
        if prop in ["hidden", "reqd", "read_only", "print_hide"]:
            ptype = "Check"
            value = str(int(value))
        else:
            ptype = "Data"
            value = "" if value is None else str(value)

        name = frappe.db.exists("Property Setter", {
            "doc_type": DT,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": prop,
        })

        if name:
            frappe.db.set_value("Property Setter", name, {
                "value": value,
                "property_type": ptype,
            }, update_modified=False)
        else:
            frappe.get_doc({
                "doctype": "Property Setter",
                "doc_type": DT,
                "doctype_or_field": "DocField",
                "field_name": fieldname,
                "property": prop,
                "property_type": ptype,
                "value": value,
            }).insert(ignore_permissions=True)


def clean_sales_invoice_fields():
    # Use these existing fields:
    # patient = standard Healthcare Patient
    # custom_kpws_mr_number = MR Number entry
    # custom_is_walkin = walk-in checkbox
    # walkin_customer_name / walkin_mr_number = old existing walk-in fields, likely used by print formats
    # custom_panel = visible panel display field
    # custom_kpws_billing_type = single visible Patient Type field
    # custom_kpws_welfare_* = welfare info

    set_field_props("custom_patient", hidden=1, reqd=0, read_only=1, label="Duplicate Patient - Hidden")
    set_field_props("custom_mr_number", hidden=1, reqd=0, read_only=1)
    set_field_props("custom_kpws_patient_type", hidden=1, reqd=0, read_only=1)

    set_field_props("custom_walkin_patient_name", hidden=1, reqd=0)
    set_field_props("custom_walkin_mr_number", hidden=1, reqd=0)

    set_field_props("custom_kpws_simple_billing_section", hidden=0, label="KPWS Patient Billing")
    set_field_props("kpws_patient_billing_section", hidden=1)

    set_field_props("custom_is_walkin", hidden=0, reqd=0, label="Walk-in Patient")
    set_field_props("walkin_customer_name", hidden=0, reqd=0, label="Walk-in Patient Name", depends_on="eval:doc.custom_is_walkin")
    set_field_props("walkin_mr_number", hidden=0, reqd=0, label="Walk-in MR Number", depends_on="eval:doc.custom_is_walkin")

    set_field_props("custom_kpws_mr_number", hidden=0, reqd=0, label="MR Number", depends_on="eval:!doc.custom_is_walkin")
    set_field_props("patient", hidden=0, reqd=0, label="Patient", depends_on="eval:!doc.custom_is_walkin")
    set_field_props("patient_name", hidden=0, read_only=1, label="Patient Name")

    set_field_props("custom_kpws_billing_type", hidden=0, read_only=1, label="Patient Type")

    set_field_props(
        "custom_panel",
        hidden=0,
        read_only=1,
        label="Panel",
        depends_on="eval:doc.custom_kpws_billing_type=='Panel'",
    )

    set_field_props("custom_kpws_panel_customer", hidden=1, read_only=1, reqd=0)

    set_field_props(
        "custom_kpws_welfare_registration",
        hidden=0,
        read_only=1,
        label="Welfare Registration",
        depends_on="eval:doc.custom_kpws_billing_type=='Welfare'",
    )
    set_field_props(
        "custom_kpws_welfare_type",
        hidden=0,
        read_only=1,
        label="Purpose",
        depends_on="eval:doc.custom_kpws_billing_type=='Welfare'",
    )
    set_field_props(
        "custom_kpws_welfare_percentage",
        hidden=0,
        read_only=1,
        label="Percentage",
        depends_on="eval:doc.custom_kpws_billing_type=='Welfare'",
    )


@frappe.whitelist()
def get_sales_invoice_context(patient=None, mr_number=None, is_walkin=0, walkin_name=None, walkin_mr_number=None):
    is_walkin = int(is_walkin or 0)

    if is_walkin:
        customer = find_cash_customer()
        if not customer:
            frappe.throw("No Cash / Walk-in Customer found. Please create a Cash Customer first.")

        return {
            "is_walkin": 1,
            "patient": "",
            "mr_number": walkin_mr_number or "",
            "patient_name": walkin_name or "",
            "customer": customer,
            "patient_type": "Cash",
            "panel_customer": "",
            "welfare_registration": "",
            "welfare_type": "",
            "welfare_percentage": 0,
            "is_pos": 1,
            "pos_profile": find_pos_profile("Cash"),
            "selling_price_list": price_list_for_type("Cash"),
            "cash_mode": find_mode(["Cash"]),
            "card_mode": find_mode(["Credit Card", "Card"]),
            "zakat_mode": find_mode(["Zakat"]),
            "donation_mode": find_mode(["Donation"]),
        }

    if not patient and mr_number:
        patient = find_patient_by_mr(mr_number)

    if not patient or not frappe.db.exists("Patient", patient):
        frappe.throw("Patient not found. Please select Patient or enter valid MR Number like KPWS-####.")

    p = frappe.get_doc("Patient", patient)
    linked_customer = first(p, ["customer", "custom_patient_customer"])

    if not linked_customer:
        frappe.throw("Selected Patient has no linked Customer.")

    patient_type = get_patient_type(p, linked_customer)

    welfare = {}
    panel_customer = ""

    if patient_type == "Welfare":
        welfare = get_latest_welfare_registration(patient)

    if patient_type == "Panel":
        panel_customer = first(p, ["custom_panel_customer", "panel_name", "panel_customer"])

        if not panel_customer:
            frappe.throw("Panel patient has no Panel assigned on Patient form.")

        if not customer_is_panel(panel_customer):
            frappe.throw(f"Selected Panel {panel_customer} is not marked as Is Panel in Customer.")

        invoice_customer = panel_customer
    else:
        invoice_customer = linked_customer

    return {
        "is_walkin": 0,
        "patient": patient,
        "mr_number": patient,
        "patient_name": first(p, ["patient_name", "first_name"]) or patient,
        "patient_customer": linked_customer,
        "customer": invoice_customer,
        "patient_type": patient_type,
        "panel_customer": panel_customer,
        "welfare_registration": welfare.get("name") or "",
        "welfare_type": welfare.get("welfare_type") or "",
        "welfare_percentage": float(welfare.get("welfare_percentage") or 0),
        "is_pos": 0 if patient_type == "Panel" else 1,
        "pos_profile": "" if patient_type == "Panel" else find_pos_profile(patient_type),
        "selling_price_list": price_list_for_type(patient_type),
        "cash_mode": find_mode(["Cash"]),
        "card_mode": find_mode(["Credit Card", "Card"]),
        "zakat_mode": find_mode(["Zakat"]),
        "donation_mode": find_mode(["Donation"]),
    }


def validate_sales_invoice(doc, method=None):
    patient_type = doc.get("custom_kpws_billing_type")

    if doc.get("custom_is_walkin"):
        if not (doc.get("walkin_customer_name") or doc.get("custom_walkin_patient_name")):
            frappe.throw("Walk-in Patient Name is required.")
        if not doc.get("customer"):
            frappe.throw("Walk-in invoice requires Cash Customer.")
        return

    if doc.get("patient") and not doc.get("customer"):
        frappe.throw("Sales Invoice with Patient requires Customer.")

    if patient_type == "Panel":
        panel = doc.get("custom_panel") or doc.get("custom_kpws_panel_customer")
        if not panel:
            frappe.throw("Panel patient invoice requires Panel.")
        if not customer_is_panel(panel):
            frappe.throw("Selected Panel Customer is not marked as Is Panel.")

    if patient_type == "Welfare":
        percentage = float(doc.get("custom_kpws_welfare_percentage") or 0)
        purpose = doc.get("custom_kpws_welfare_type")
        if percentage > 0 and not purpose:
            frappe.throw("Welfare invoice requires Purpose: Zakat or Donation.")


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable all old KPWS Sales Invoice scripts, including the earlier temp final one.
    for row in frappe.get_all("Client Script", filters={"dt": DT}, fields=["name", "script"]):
        if row.name == FINAL_CLIENT_SCRIPT:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if any(k in text for k in ["kpws", "welfare", "panel", "walkin", "walk-in", "patient type", "custom_patient"]):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old Sales Invoice Client Script:", row.name)

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_si_setup(frm);
    },
    onload(frm) {
        kpws_si_setup(frm);
        kpws_si_toggle(frm);
    },
    refresh(frm) {
        kpws_si_setup(frm);
        kpws_si_toggle(frm);
    },
    patient(frm) {
        if (!frm.doc.custom_is_walkin && frm.doc.patient) {
            kpws_si_load_context(frm);
        }
    },
    custom_kpws_mr_number(frm) {
        if (!frm.doc.custom_is_walkin && frm.doc.custom_kpws_mr_number) {
            kpws_si_load_context(frm);
        }
    },
    custom_is_walkin(frm) {
        kpws_si_toggle(frm);
        kpws_si_load_context(frm);
    },
    walkin_customer_name(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_si_load_context(frm);
        }
    },
    walkin_mr_number(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_si_load_context(frm);
        }
    },
    validate(frm) {
        kpws_si_apply_payment_split(frm);
    },
    grand_total(frm) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 300);
    },
    rounded_total(frm) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 300);
    },
    net_total(frm) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 300);
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 600);
    },
    qty(frm, cdt, cdn) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 600);
    },
    rate(frm, cdt, cdn) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 600);
    },
    amount(frm, cdt, cdn) {
        setTimeout(() => kpws_si_apply_payment_split(frm), 600);
    }
});

function kpws_si_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_si_setup(frm) {
    if (kpws_si_has(frm, "custom_panel")) {
        frm.set_query("custom_panel", function() {
            return { filters: { custom_is_panel: 1 } };
        });
    }

    ["custom_kpws_billing_type", "custom_panel", "custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage"].forEach(function(fieldname) {
        if (kpws_si_has(frm, fieldname)) {
            frm.set_df_property(fieldname, "read_only", 1);
        }
    });

    kpws_si_toggle(frm);
}

function kpws_si_toggle(frm) {
    let walkin = !!frm.doc.custom_is_walkin;

    ["walkin_customer_name", "walkin_mr_number"].forEach(function(fieldname) {
        if (kpws_si_has(frm, fieldname)) {
            frm.toggle_display(fieldname, walkin);
            frm.toggle_reqd(fieldname, walkin);
        }
    });

    ["custom_kpws_mr_number", "patient"].forEach(function(fieldname) {
        if (kpws_si_has(frm, fieldname)) {
            frm.toggle_display(fieldname, !walkin);
            frm.toggle_reqd(fieldname, false);
        }
    });

    ["custom_walkin_patient_name", "custom_walkin_mr_number", "custom_patient", "custom_mr_number", "custom_kpws_patient_type", "custom_kpws_panel_customer"].forEach(function(fieldname) {
        if (kpws_si_has(frm, fieldname)) {
            frm.toggle_display(fieldname, false);
            frm.toggle_reqd(fieldname, false);
        }
    });
}

function kpws_si_load_context(frm) {
    if (frm.__kpws_loading_context) return;

    frm.__kpws_loading_context = true;

    frappe.call({
        method: "kpws_customization.api.kpws_sales_invoice_final.get_sales_invoice_context",
        args: {
            patient: frm.doc.patient || "",
            mr_number: frm.doc.custom_kpws_mr_number || "",
            is_walkin: frm.doc.custom_is_walkin ? 1 : 0,
            walkin_name: frm.doc.walkin_customer_name || "",
            walkin_mr_number: frm.doc.walkin_mr_number || ""
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            frm.__kpws_context = d;

            let updates = {};

            if (!frm.doc.custom_is_walkin && d.patient && kpws_si_has(frm, "patient") && frm.doc.patient !== d.patient) {
                updates.patient = d.patient;
            }

            if (!frm.doc.custom_is_walkin && d.mr_number && kpws_si_has(frm, "custom_kpws_mr_number") && frm.doc.custom_kpws_mr_number !== d.mr_number) {
                updates.custom_kpws_mr_number = d.mr_number;
            }

            if (d.customer && frm.doc.customer !== d.customer) {
                updates.customer = d.customer;
            }

            if (kpws_si_has(frm, "patient_name")) {
                updates.patient_name = d.patient_name || "";
            }

            if (kpws_si_has(frm, "custom_kpws_billing_type")) {
                updates.custom_kpws_billing_type = d.patient_type || "";
            }

            if (kpws_si_has(frm, "custom_panel")) {
                updates.custom_panel = d.panel_customer || "";
            }

            if (kpws_si_has(frm, "custom_kpws_panel_customer")) {
                updates.custom_kpws_panel_customer = d.panel_customer || "";
            }

            if (kpws_si_has(frm, "custom_kpws_welfare_registration")) {
                updates.custom_kpws_welfare_registration = d.welfare_registration || "";
            }

            if (kpws_si_has(frm, "custom_kpws_welfare_type")) {
                updates.custom_kpws_welfare_type = d.welfare_type || "";
            }

            if (kpws_si_has(frm, "custom_kpws_welfare_percentage")) {
                updates.custom_kpws_welfare_percentage = d.welfare_percentage || 0;
            }

            if (kpws_si_has(frm, "is_pos")) {
                updates.is_pos = d.is_pos ? 1 : 0;
            }

            if (kpws_si_has(frm, "pos_profile")) {
                updates.pos_profile = d.pos_profile || "";
            }

            if (kpws_si_has(frm, "selling_price_list") && d.selling_price_list) {
                updates.selling_price_list = d.selling_price_list;
            }

            frm.set_value(updates).then(function() {
                kpws_si_toggle(frm);
                kpws_si_apply_payment_split(frm);
                frm.refresh_fields();
            });
        },
        always: function() {
            frm.__kpws_loading_context = false;
        }
    });
}

function kpws_si_total(frm) {
    return flt(frm.doc.rounded_total || frm.doc.grand_total || frm.doc.net_total || 0);
}

function kpws_si_apply_payment_split(frm) {
    if (!frm.fields_dict.payments) return;

    let patient_type = frm.doc.custom_kpws_billing_type || "";
    let total = kpws_si_total(frm);
    let ctx = frm.__kpws_context || {};

    if (!total || total <= 0) return;

    if (patient_type === "Panel") {
        frm.clear_table("payments");
        frm.refresh_field("payments");
        return;
    }

    if (patient_type === "Welfare") {
        let pct = flt(frm.doc.custom_kpws_welfare_percentage || 0);
        let purpose = (frm.doc.custom_kpws_welfare_type || "").toLowerCase();

        let sponsor_mode = "";
        if (purpose.includes("zakat")) {
            sponsor_mode = ctx.zakat_mode || "Zakat";
        } else if (purpose.includes("donation")) {
            sponsor_mode = ctx.donation_mode || "Donation";
        }

        let sponsor_amount = flt(total * pct / 100);
        let cash_amount = flt(total - sponsor_amount);

        frm.clear_table("payments");

        if (sponsor_amount > 0 && sponsor_mode) {
            let sponsor = frm.add_child("payments");
            sponsor.mode_of_payment = sponsor_mode;
            sponsor.amount = sponsor_amount;
        }

        if (cash_amount > 0) {
            let cash = frm.add_child("payments");
            cash.mode_of_payment = ctx.cash_mode || "Cash";
            cash.amount = cash_amount;
        }

        frm.refresh_field("payments");
        return;
    }

    if (patient_type === "Cash" || frm.doc.custom_is_walkin) {
        if (!frm.doc.payments || frm.doc.payments.length === 0) {
            let row = frm.add_child("payments");
            row.mode_of_payment = ctx.cash_mode || "Cash";
            row.amount = total;
            frm.refresh_field("payments");
        }
    }
}
'''

    if frappe.db.exists("Client Script", FINAL_CLIENT_SCRIPT):
        doc = frappe.get_doc("Client Script", FINAL_CLIENT_SCRIPT)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated:", FINAL_CLIENT_SCRIPT)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": FINAL_CLIENT_SCRIPT,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created:", FINAL_CLIENT_SCRIPT)


def patch_hooks():
    hooks_path = frappe.get_app_path("kpws_customization", "hooks.py")

    if not os.path.exists(hooks_path):
        print("hooks.py not found:", hooks_path)
        return

    with open(hooks_path, "r") as f:
        lines = f.read().splitlines()

    new_lines = []

    for line in lines:
        if '"Sales Invoice"' in line and "kpws_sales_invoice" in line:
            if not line.strip().startswith("#"):
                new_lines.append("# disabled by final standard patient sales flow: " + line)
                print("Disabled doctype_js line:", line.strip())
            else:
                new_lines.append(line)
            continue

        # Replace previous temporary validation method with stable final method.
        if "kpws_temp_sales_invoice_clean_flow.validate_sales_invoice" in line:
            line = line.replace(
                "kpws_customization.api.kpws_temp_sales_invoice_clean_flow.validate_sales_invoice",
                "kpws_customization.api.kpws_sales_invoice_final.validate_sales_invoice",
            )

        new_lines.append(line)

    text = "\n".join(new_lines) + "\n"

    method = "kpws_customization.api.kpws_sales_invoice_final.validate_sales_invoice"

    if method not in text:
        text += f"""

# KPWS final Sales Invoice standard patient validation
doc_events = globals().get("doc_events", {{}})
doc_events.setdefault("Sales Invoice", {{}})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "{method}" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("{method}")
"""

    with open(hooks_path, "w") as f:
        f.write(text)

    print("hooks.py patched:", hooks_path)


def install():
    clean_sales_invoice_fields()
    install_client_script()
    patch_hooks()

    frappe.db.set_value("DocType", DT, "modified", now(), update_modified=False)
    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print("")
    print("DONE: Sales Invoice final standard-patient flow installed.")
    print("Uses Sales Invoice.patient. Keeps custom_patient hidden. No duplicate fields created.")
