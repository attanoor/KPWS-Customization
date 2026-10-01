import frappe
from frappe.utils import now

DT = "Sales Invoice"

FIELD_DEFS = {
    "kpws_patient_billing_section": {
        "label": "KPWS Patient Billing",
        "fieldtype": "Section Break",
        "insert_after": "customer",
        "hidden": 0,
    },
    "custom_is_walkin": {
        "label": "Walk-in Patient",
        "fieldtype": "Check",
        "insert_after": "kpws_patient_billing_section",
        "hidden": 0,
        "reqd": 0,
    },
    "custom_walkin_patient_name": {
        "label": "Walk-in Patient Name",
        "fieldtype": "Data",
        "insert_after": "custom_is_walkin",
        "hidden": 0,
        "reqd": 0,
        "depends_on": "eval:doc.custom_is_walkin",
    },
    "custom_walkin_mr_number": {
        "label": "Walk-in MR Number",
        "fieldtype": "Data",
        "insert_after": "custom_walkin_patient_name",
        "hidden": 0,
        "reqd": 0,
        "depends_on": "eval:doc.custom_is_walkin",
    },
    "custom_mr_number": {
        "label": "MR Number",
        "fieldtype": "Data",
        "insert_after": "custom_walkin_mr_number",
        "hidden": 0,
        "reqd": 0,
        "depends_on": "eval:!doc.custom_is_walkin",
    },
    "custom_kpws_patient_type": {
        "label": "Patient Type",
        "fieldtype": "Data",
        "insert_after": "custom_mr_number",
        "hidden": 0,
        "read_only": 1,
    },
    "custom_kpws_panel_customer": {
        "label": "Panel",
        "fieldtype": "Link",
        "options": "Customer",
        "insert_after": "custom_kpws_patient_type",
        "hidden": 0,
        "read_only": 1,
    },
    "custom_kpws_welfare_registration": {
        "label": "Welfare Registration",
        "fieldtype": "Link",
        "options": "Patient Registration Form",
        "insert_after": "custom_kpws_panel_customer",
        "hidden": 0,
        "read_only": 1,
    },
    "custom_kpws_welfare_type": {
        "label": "Welfare Type",
        "fieldtype": "Data",
        "insert_after": "custom_kpws_welfare_registration",
        "hidden": 0,
        "read_only": 1,
    },
    "custom_kpws_welfare_percentage": {
        "label": "Welfare Percentage",
        "fieldtype": "Percent",
        "insert_after": "custom_kpws_welfare_type",
        "hidden": 0,
        "read_only": 1,
    },
}

ORDER = [
    "kpws_patient_billing_section",
    "custom_is_walkin",
    "custom_walkin_patient_name",
    "custom_walkin_mr_number",
    "custom_mr_number",
    "patient",
    "custom_kpws_patient_type",
    "custom_kpws_panel_customer",
    "custom_kpws_welfare_registration",
    "custom_kpws_welfare_type",
    "custom_kpws_welfare_percentage",
]

def get_df(fieldname):
    return frappe.db.get_value(
        "DocField",
        {"parent": DT, "fieldname": fieldname},
        ["name", "idx", "fieldname", "label", "fieldtype", "hidden"],
        as_dict=True,
    )

def max_idx():
    return int(frappe.db.sql(
        "select coalesce(max(idx),0) from `tabDocField` where parent=%s",
        DT,
    )[0][0] or 0)

def ensure_df(fieldname, d):
    row = get_df(fieldname)
    values = {
        "label": d.get("label"),
        "fieldtype": d.get("fieldtype"),
        "options": d.get("options"),
        "insert_after": d.get("insert_after"),
        "hidden": int(d.get("hidden", 0)),
        "read_only": int(d.get("read_only", 0)),
        "reqd": int(d.get("reqd", 0)),
        "depends_on": d.get("depends_on"),
        "print_hide": int(d.get("print_hide", 0)),
    }

    if row:
        frappe.db.set_value("DocField", row.name, values, update_modified=False)
        print("Updated DocField:", fieldname)
    else:
        frappe.get_doc({
            "doctype": "DocField",
            "parent": DT,
            "parenttype": "DocType",
            "parentfield": "fields",
            "idx": max_idx() + 1,
            "fieldname": fieldname,
            **values,
        }).insert(ignore_permissions=True)
        print("Inserted DocField:", fieldname)

def ps(fieldname, prop, value, ptype="Check"):
    name = frappe.db.exists("Property Setter", {
        "doc_type": DT,
        "doctype_or_field": "DocField",
        "field_name": fieldname,
        "property": prop,
    })

    if name:
        frappe.db.set_value("Property Setter", name, {
            "value": str(value),
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
            "value": str(value),
        }).insert(ignore_permissions=True)

def reindex():
    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=["name", "fieldname"],
        order_by="idx asc",
    )

    by_field = {r.fieldname: r for r in rows}
    ordered = []
    used = set()

    # Put custom KPWS fields after customer/patient area without disturbing item/payment sections too much.
    for r in rows:
        if r.fieldname == "customer":
            ordered.append(r)
            used.add(r.name)

            for f in ORDER:
                if f in by_field and by_field[f].name not in used:
                    ordered.append(by_field[f])
                    used.add(by_field[f].name)
            continue

        if r.name not in used and r.fieldname not in ORDER:
            ordered.append(r)
            used.add(r.name)

    for idx, r in enumerate(ordered, start=1):
        frappe.db.set_value("DocField", r.name, "idx", idx, update_modified=False)

def first(doc, fields):
    for f in fields:
        if doc.meta.get_field(f):
            v = doc.get(f)
            if v not in (None, ""):
                return v
    return ""

def customer_is_panel(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False
    if frappe.get_meta("Customer").get_field("custom_is_panel"):
        return bool(frappe.db.get_value("Customer", customer, "custom_is_panel"))
    return False

def billing_type_from_text(text):
    t = str(text or "").lower()
    if "panel" in t:
        return "Panel"
    if "welfare" in t:
        return "Welfare"
    return "Cash"

def get_patient_customer(patient_doc):
    return first(patient_doc, ["customer", "custom_patient_customer"])

def get_patient_type(patient_doc, customer=None):
    patient_group = first(patient_doc, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])

    customer_group = ""
    if customer and frappe.db.exists("Customer", customer):
        customer_group = frappe.db.get_value("Customer", customer, "customer_group") or ""

    return billing_type_from_text(patient_group or customer_group)

def find_patient_by_mr(mr_number):
    if not mr_number:
        return None

    mr = str(mr_number).strip()

    if frappe.db.exists("Patient", mr):
        return mr

    candidates = [
        "custom_mr_number",
        "mr_number",
        "uid",
        "patient_id",
    ]

    meta = frappe.get_meta("Patient")
    for f in candidates:
        if meta.get_field(f):
            name = frappe.db.get_value("Patient", {f: mr}, "name")
            if name:
                return name

    return None

def get_latest_welfare_registration(patient):
    if not frappe.db.exists("DocType", "Patient Registration Form"):
        return {}

    fields = ["name", "purpose", "discount_value"]

    meta = frappe.get_meta("Patient Registration Form")
    for f in [
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ]:
        if meta.get_field(f):
            fields.append(f)

    filters = []
    if meta.get_field("custom_patient"):
        filters.append({"custom_patient": patient})
    if meta.get_field("patient"):
        filters.append({"patient": patient})

    for flt in filters:
        rows = frappe.get_all(
            "Patient Registration Form",
            filters=flt,
            fields=fields,
            order_by="modified desc",
            limit=1,
        )
        if rows:
            row = rows[0]
            welfare_type = row.get("custom_kpws_welfare_type") or row.get("purpose") or ""
            welfare_percentage = row.get("custom_kpws_welfare_percentage")
            if welfare_percentage in (None, ""):
                welfare_percentage = row.get("discount_value") or 0

            panel = row.get("custom_panel_customer") or row.get("custom_kpws_assigned_panel_customer") or ""

            return {
                "name": row.name,
                "welfare_type": welfare_type,
                "welfare_percentage": float(welfare_percentage or 0),
                "panel_customer": panel,
            }

    return {}

def find_panel_for_patient(patient_doc, welfare_registration=None):
    for f in ["custom_panel_customer", "panel_name", "panel_customer"]:
        if patient_doc.meta.get_field(f):
            val = patient_doc.get(f)
            if val:
                return val

    if welfare_registration:
        val = welfare_registration.get("panel_customer")
        if val:
            return val

    return ""

def find_pos_profile(patient_type):
    if not frappe.db.exists("DocType", "POS Profile"):
        return ""

    candidates = {
        "Cash": ["KPWS Cash", "Cash", "Cash - KPWS"],
        "Welfare": ["KPWS Welfare", "Welfare", "Welfare - KPWS"],
        "Panel": ["KPWS Panel", "Panel", "Panel - KPWS"],
    }.get(patient_type, ["Cash"])

    for c in candidates:
        if frappe.db.exists("POS Profile", c):
            return c

    # fallback by name contains
    rows = frappe.get_all("POS Profile", fields=["name"], limit=100)
    for r in rows:
        n = r.name.lower()
        if patient_type.lower() in n:
            return r.name

    if patient_type == "Cash":
        for r in rows:
            if "cash" in r.name.lower():
                return r.name

    return rows[0].name if rows else ""

def price_list_for_type(patient_type):
    if patient_type == "Panel":
        for p in ["SPP - Selling Price Panel", "SPP"]:
            if frappe.db.exists("Price List", p):
                return p

    if patient_type in ["Cash", "Welfare"]:
        for p in ["SPW - Selling Price Welfare", "SPW"]:
            if frappe.db.exists("Price List", p):
                return p

    return ""

def mode_exists(mode):
    return bool(mode and frappe.db.exists("Mode of Payment", mode))

def find_mode(names):
    for n in names:
        if mode_exists(n):
            return n
    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=100)
    lower_names = [x.lower() for x in names]
    for r in rows:
        rn = r.name.lower()
        if any(x in rn for x in lower_names):
            return r.name
    return names[0] if names else "Cash"

@frappe.whitelist()
def get_sales_invoice_context(patient=None, mr_number=None, is_walkin=0, walkin_name=None, walkin_mr_number=None):
    is_walkin = int(is_walkin or 0)

    if is_walkin:
        cash_customer = ""
        for c in ["Walk In Customer", "Walk-in Customer", "Cash Customer"]:
            if frappe.db.exists("Customer", c):
                cash_customer = c
                break

        if not cash_customer:
            rows = frappe.get_all("Customer", filters={"customer_group": ["like", "%Cash%"]}, fields=["name"], limit=1)
            cash_customer = rows[0].name if rows else ""

        return {
            "is_walkin": 1,
            "patient": "",
            "mr_number": walkin_mr_number or "",
            "patient_name": walkin_name or "",
            "patient_type": "Cash",
            "customer": cash_customer,
            "panel_customer": "",
            "welfare_registration": "",
            "welfare_type": "",
            "welfare_percentage": 0,
            "pos_profile": find_pos_profile("Cash"),
            "selling_price_list": price_list_for_type("Cash"),
            "payment_mode": find_mode(["Cash"]),
            "card_mode": find_mode(["Credit Card", "Card"]),
        }

    if not patient and mr_number:
        patient = find_patient_by_mr(mr_number)

    if not patient or not frappe.db.exists("Patient", patient):
        frappe.throw("Patient not found for selected MR Number / Patient.")

    p = frappe.get_doc("Patient", patient)
    customer = get_patient_customer(p)
    patient_type = get_patient_type(p, customer)

    welfare = {}
    panel_customer = ""

    if patient_type == "Welfare":
        welfare = get_latest_welfare_registration(patient)

    if patient_type == "Panel":
        panel_customer = find_panel_for_patient(p, welfare)
        if not panel_customer:
            frappe.throw("Panel patient has no panel assigned on Patient.")
        if not customer_is_panel(panel_customer):
            frappe.throw(f"Selected Panel Customer {panel_customer} is not marked as Is Panel.")

    if patient_type == "Panel":
        invoice_customer = panel_customer
    else:
        invoice_customer = customer

    if not invoice_customer:
        frappe.throw("Patient has no linked Customer.")

    return {
        "is_walkin": 0,
        "patient": patient,
        "mr_number": first(p, ["custom_mr_number", "mr_number", "uid", "patient_id"]) or patient,
        "patient_name": first(p, ["patient_name", "first_name"]),
        "patient_type": patient_type,
        "customer": invoice_customer,
        "patient_customer": customer,
        "panel_customer": panel_customer,
        "welfare_registration": welfare.get("name") or "",
        "welfare_type": welfare.get("welfare_type") or "",
        "welfare_percentage": float(welfare.get("welfare_percentage") or 0),
        "pos_profile": find_pos_profile(patient_type),
        "selling_price_list": price_list_for_type(patient_type),
        "payment_mode": find_mode(["Cash"]),
        "card_mode": find_mode(["Credit Card", "Card"]),
        "zakat_mode": find_mode(["Zakat"]),
        "donation_mode": find_mode(["Donation"]),
    }

def validate_sales_invoice(doc, method=None):
    patient_type = doc.get("custom_kpws_patient_type")

    if patient_type == "Panel":
        panel = doc.get("custom_kpws_panel_customer")
        if not panel:
            frappe.throw("Panel invoice requires Panel.")
        if not customer_is_panel(panel):
            frappe.throw("Selected Panel is not marked as Is Panel.")

    if patient_type == "Welfare":
        percentage = float(doc.get("custom_kpws_welfare_percentage") or 0)
        welfare_type = doc.get("custom_kpws_welfare_type")
        if percentage > 0 and not welfare_type:
            frappe.throw("Welfare invoice requires Zakat or Donation type.")

def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    for row in frappe.get_all("Client Script", filters={"dt": DT}, fields=["name", "script"]):
        if row.name == "KPWS FINAL Sales Invoice Clean Flow":
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if any(k in text for k in ["kpws", "welfare", "panel", "walkin", "walk-in", "pos profile", "patient type"]):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old Sales Invoice script:", row.name)

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_si_setup(frm);
    },
    onload(frm) {
        kpws_si_setup(frm);
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
    custom_mr_number(frm) {
        if (!frm.doc.custom_is_walkin && frm.doc.custom_mr_number) {
            kpws_si_load_context(frm);
        }
    },
    custom_is_walkin(frm) {
        kpws_si_toggle(frm);
        kpws_si_load_context(frm);
    },
    custom_walkin_patient_name(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_si_load_context(frm);
        }
    },
    custom_walkin_mr_number(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_si_load_context(frm);
        }
    },
    grand_total(frm) {
        kpws_si_apply_payment_split(frm);
    },
    rounded_total(frm) {
        kpws_si_apply_payment_split(frm);
    },
    net_total(frm) {
        kpws_si_apply_payment_split(frm);
    }
});

function kpws_si_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_si_setup(frm) {
    if (kpws_si_has(frm, "custom_kpws_panel_customer")) {
        frm.set_query("custom_kpws_panel_customer", function() {
            return { filters: { custom_is_panel: 1 } };
        });
    }

    ["custom_kpws_patient_type", "custom_kpws_panel_customer", "custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage"].forEach(function(f) {
        if (kpws_si_has(frm, f)) {
            frm.set_df_property(f, "read_only", 1);
        }
    });
}

function kpws_si_toggle(frm) {
    let walkin = !!frm.doc.custom_is_walkin;

    ["custom_walkin_patient_name", "custom_walkin_mr_number"].forEach(function(f) {
        if (kpws_si_has(frm, f)) {
            frm.toggle_display(f, walkin);
            frm.toggle_reqd(f, walkin);
        }
    });

    ["custom_mr_number", "patient"].forEach(function(f) {
        if (kpws_si_has(frm, f)) {
            frm.toggle_display(f, !walkin);
            frm.toggle_reqd(f, false);
        }
    });
}

function kpws_si_load_context(frm) {
    frappe.call({
        method: "kpws_customization.api.kpws_temp_sales_invoice_clean_flow.get_sales_invoice_context",
        args: {
            patient: frm.doc.patient,
            mr_number: frm.doc.custom_mr_number,
            is_walkin: frm.doc.custom_is_walkin ? 1 : 0,
            walkin_name: frm.doc.custom_walkin_patient_name,
            walkin_mr_number: frm.doc.custom_walkin_mr_number
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            if (!d) return;

            let updates = {};

            if (kpws_si_has(frm, "patient") && d.patient && frm.doc.patient !== d.patient) updates.patient = d.patient;
            if (kpws_si_has(frm, "custom_mr_number") && d.mr_number && frm.doc.custom_mr_number !== d.mr_number && !frm.doc.custom_is_walkin) updates.custom_mr_number = d.mr_number;
            if (d.customer && frm.doc.customer !== d.customer) updates.customer = d.customer;

            if (kpws_si_has(frm, "custom_kpws_patient_type")) updates.custom_kpws_patient_type = d.patient_type || "";
            if (kpws_si_has(frm, "custom_kpws_panel_customer")) updates.custom_kpws_panel_customer = d.panel_customer || "";
            if (kpws_si_has(frm, "custom_kpws_welfare_registration")) updates.custom_kpws_welfare_registration = d.welfare_registration || "";
            if (kpws_si_has(frm, "custom_kpws_welfare_type")) updates.custom_kpws_welfare_type = d.welfare_type || "";
            if (kpws_si_has(frm, "custom_kpws_welfare_percentage")) updates.custom_kpws_welfare_percentage = d.welfare_percentage || 0;

            if (d.pos_profile && kpws_si_has(frm, "pos_profile")) updates.pos_profile = d.pos_profile;
            if (d.selling_price_list && kpws_si_has(frm, "selling_price_list")) updates.selling_price_list = d.selling_price_list;

            if (kpws_si_has(frm, "is_pos")) updates.is_pos = d.patient_type === "Panel" ? 0 : 1;
            if (kpws_si_has(frm, "include_payment")) updates.include_payment = d.patient_type === "Panel" ? 0 : 1;

            frm.set_value(updates).then(function() {
                kpws_si_apply_payment_split(frm, d);
                frm.refresh_fields();
            });
        }
    });
}

function kpws_si_total(frm) {
    return flt(frm.doc.rounded_total || frm.doc.grand_total || frm.doc.net_total || 0);
}

function kpws_si_apply_payment_split(frm, context) {
    let patient_type = frm.doc.custom_kpws_patient_type;
    let total = kpws_si_total(frm);

    if (!frm.fields_dict.payments || !frm.doc.payments) {
        return;
    }

    if (!total || total <= 0) {
        return;
    }

    if (patient_type === "Panel") {
        frm.clear_table("payments");
        frm.refresh_field("payments");
        return;
    }

    if (patient_type === "Welfare") {
        let pct = flt(frm.doc.custom_kpws_welfare_percentage || 0);
        let type = frm.doc.custom_kpws_welfare_type || "";
        let mode = "";

        if (type.toLowerCase().includes("zakat")) {
            mode = (context && context.zakat_mode) || "Zakat";
        } else if (type.toLowerCase().includes("donation")) {
            mode = (context && context.donation_mode) || "Donation";
        }

        let welfare_amount = flt(total * pct / 100.0);
        let cash_amount = flt(total - welfare_amount);

        frm.clear_table("payments");

        if (welfare_amount > 0 && mode) {
            let row = frm.add_child("payments");
            row.mode_of_payment = mode;
            row.amount = welfare_amount;
        }

        if (cash_amount > 0) {
            let row = frm.add_child("payments");
            row.mode_of_payment = (context && context.payment_mode) || "Cash";
            row.amount = cash_amount;
        }

        frm.refresh_field("payments");
        return;
    }

    if (patient_type === "Cash" || frm.doc.custom_is_walkin) {
        if (!frm.doc.payments || frm.doc.payments.length === 0) {
            let row = frm.add_child("payments");
            row.mode_of_payment = (context && context.payment_mode) || "Cash";
            row.amount = total;
            frm.refresh_field("payments");
        }
    }
}
'''

    name = "KPWS FINAL Sales Invoice Clean Flow"

    if frappe.db.exists("Client Script", name):
        doc = frappe.get_doc("Client Script", name)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": name,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)

    print("Installed Sales Invoice Client Script")

def patch_hooks():
    hooks_path = frappe.get_app_path("kpws_customization", "hooks.py")
    text = open(hooks_path).read()

    target = '"Sales Invoice": "public/js/kpws_sales_invoice_clean.js"'
    if target in text:
        text = text.replace(target, '# disabled by KPWS clean flow: "Sales Invoice": "public/js/kpws_sales_invoice_clean.js"')
        open(hooks_path, "w").write(text)
        print("Disabled old Sales Invoice doctype_js hook")

    method = "kpws_customization.api.kpws_temp_sales_invoice_clean_flow.validate_sales_invoice"
    if method not in text:
        text += f"""

# KPWS final clean Sales Invoice validation
doc_events = globals().get("doc_events", {{}})
doc_events.setdefault("Sales Invoice", {{}})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "{method}" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("{method}")
"""
        open(hooks_path, "w").write(text)
        print("Added final Sales Invoice validation hook")

def run():
    if not frappe.db.exists("DocType", DT):
        raise Exception(f"{DT} not found")

    for fieldname, d in FIELD_DEFS.items():
        ensure_df(fieldname, d)

    reindex()

    for f in [
        "custom_is_walkin",
        "custom_walkin_patient_name",
        "custom_walkin_mr_number",
        "custom_mr_number",
        "custom_kpws_patient_type",
        "custom_kpws_panel_customer",
        "custom_kpws_welfare_registration",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
    ]:
        if get_df(f):
            ps(f, "hidden", "0")
            ps(f, "reqd", "0")

    install_client_script()
    patch_hooks()

    frappe.db.set_value("DocType", DT, "modified", now(), update_modified=False)
    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print("")
    print("Final Sales Invoice KPWS fields:")
    for f in ORDER:
        df = get_df(f)
        if df:
            print(f, "|", df.label, "|", df.fieldtype, "| hidden=", df.hidden)

    print("")
    print("DONE: Sales Invoice clean flow installed.")

