import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Unified Sales Invoice Flow"
WAREHOUSE = "Pharmacy - KPWS"


def _exists(doctype, names):
    for name in names:
        if name and frappe.db.exists(doctype, name):
            return name
    return ""


def _field_exists(doctype, fieldname):
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _first(doc, fields):
    for fieldname in fields:
        if doc.meta.get_field(fieldname):
            value = doc.get(fieldname)
            if value not in (None, ""):
                return value
    return ""


def _type_from_text(value):
    text = str(value or "").lower()
    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"


def _customer_is_panel(customer):
    if customer and frappe.db.exists("Customer", customer) and _field_exists("Customer", "custom_is_panel"):
        return bool(frappe.db.get_value("Customer", customer, "custom_is_panel"))
    return False


def _find_patient_by_mr(mr_number):
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


def _cash_customer():
    customer = _exists("Customer", ["Walk-in Customer", "Walk In Customer", "Cash Customer"])
    if customer:
        return customer

    rows = frappe.get_all("Customer", filters={"customer_group": ["like", "%Cash%"]}, fields=["name"], limit=1)
    return rows[0].name if rows else ""


def _pos_profile(patient_type):
    if patient_type == "Panel":
        return _exists("POS Profile", ["Panel", "KPWS Panel", "Panel - KPWS"])
    if patient_type == "Welfare":
        return _exists("POS Profile", ["Welfare", "KPWS Welfare", "Welfare - KPWS"])
    return _exists("POS Profile", ["Cash", "KPWS Cash", "Cash - KPWS"])


def _price_list(patient_type):
    if patient_type == "Panel":
        return _exists("Price List", ["SPP - Selling Price Panel", "SPP", "Selling Price Panel"])

    # Cash and Welfare both use SPW
    return _exists("Price List", ["SPW - Selling Price Welfare", "SPW", "Selling Price Welfare"])


def _mode(names):
    mode = _exists("Mode of Payment", names)
    if mode:
        return mode

    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=200)
    for row in rows:
        text = row.name.lower()
        for name in names:
            if name.lower() in text:
                return row.name

    return names[0] if names else ""


def _latest_welfare(patient):
    if not frappe.db.exists("DocType", "Patient Registration Form"):
        return {}

    meta = frappe.get_meta("Patient Registration Form")
    fields = ["name", "modified"]

    for f in [
        "custom_patient",
        "patient",
        "purpose",
        "discount_value",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ]:
        if meta.get_field(f):
            fields.append(f)

    filters_list = []

    if meta.get_field("custom_patient"):
        filters_list.append({"custom_patient": patient, "docstatus": ["<", 2]})

    if meta.get_field("patient"):
        filters_list.append({"patient": patient, "docstatus": ["<", 2]})

    for filters in filters_list:
        rows = frappe.get_all(
            "Patient Registration Form",
            filters=filters,
            fields=list(set(fields)),
            order_by="modified desc",
            limit=1,
        )

        if rows:
            row = rows[0]
            percentage = row.get("discount_value")
            if percentage in (None, ""):
                percentage = row.get("custom_kpws_welfare_percentage") or 0

            return {
                "name": row.name,
                "type": row.get("purpose") or row.get("custom_kpws_welfare_type") or "",
                "percentage": float(percentage or 0),
                "panel": row.get("custom_panel_customer") or row.get("custom_kpws_assigned_panel_customer") or "",
            }

    return {}


@frappe.whitelist()
def get_context(patient=None, mr_number=None, customer=None, is_walkin=0, walkin_name=None, walkin_mr=None):
    is_walkin = int(is_walkin or 0)

    if is_walkin:
        patient_type = "Cash"
        return {
            "patient": "",
            "patient_name": walkin_name or "",
            "mr_number": walkin_mr or "",
            "customer": customer or _cash_customer(),
            "patient_type": patient_type,
            "panel_customer": "",
            "welfare_registration": "",
            "welfare_type": "",
            "welfare_percentage": 0,
            "pos_profile": _pos_profile(patient_type),
            "selling_price_list": _price_list(patient_type),
            "is_pos": 1,
            "warehouse": WAREHOUSE,
            "cash_mode": _mode(["Cash"]),
            "card_mode": _mode(["Credit Card", "Card"]),
            "zakat_mode": _mode(["Zakat"]),
            "donation_mode": _mode(["Donation"]),
            "panel_mode": _mode(["Panel"]),
        }

    if not patient and mr_number:
        patient = _find_patient_by_mr(mr_number)

    linked_customer = ""
    patient_name = ""

    if patient and frappe.db.exists("Patient", patient):
        p = frappe.get_doc("Patient", patient)
        linked_customer = _first(p, ["customer", "custom_patient_customer"])
        patient_name = _first(p, ["patient_name", "first_name"]) or patient

        patient_group = _first(p, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])
        if not patient_group and linked_customer:
            patient_group = frappe.db.get_value("Customer", linked_customer, "customer_group") or ""

        patient_type = _type_from_text(patient_group)

        panel_customer = ""
        if patient_type == "Panel":
            # Only Customer records marked custom_is_panel are valid panel customers.
            # Do NOT use old Patient.panel_name if it points to KPWS Panel doctype.
            for panel_field in ["custom_panel_customer", "panel_customer", "panel_name"]:
                if p.meta.get_field(panel_field):
                    candidate = p.get(panel_field)
                    if candidate and frappe.db.exists("Customer", candidate) and _customer_is_panel(candidate):
                        panel_customer = candidate
                        break

            if not panel_customer:
                frappe.throw("Panel patient has no valid Customer Panel assigned. Open Patient form and select Panel Name from Customer records where Is Panel is checked.")

            invoice_customer = panel_customer
        else:
            invoice_customer = linked_customer

        welfare = _latest_welfare(patient) if patient_type == "Welfare" else {}

    else:
        invoice_customer = customer or ""
        patient_type = "Cash"
        panel_customer = ""
        welfare = {}

        if invoice_customer:
            if _customer_is_panel(invoice_customer):
                patient_type = "Panel"
                panel_customer = invoice_customer
            else:
                patient_type = _type_from_text(frappe.db.get_value("Customer", invoice_customer, "customer_group") or "")

    return {
        "patient": patient or "",
        "patient_name": patient_name,
        "mr_number": patient or mr_number or "",
        "patient_customer": linked_customer,
        "customer": invoice_customer,
        "patient_type": patient_type,
        "panel_customer": panel_customer,
        "welfare_registration": welfare.get("name") or "",
        "welfare_type": welfare.get("type") or "",
        "welfare_percentage": float(welfare.get("percentage") or 0),
        "pos_profile": _pos_profile(patient_type),
        "selling_price_list": _price_list(patient_type),
        "is_pos": 1,
        "warehouse": WAREHOUSE,
        "cash_mode": _mode(["Cash"]),
        "card_mode": _mode(["Credit Card", "Card"]),
        "zakat_mode": _mode(["Zakat"]),
        "donation_mode": _mode(["Donation"]),
        "panel_mode": _mode(["Panel"]),
    }


def enforce_on_validate(doc, method=None):
    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse not found: {WAREHOUSE}")

    if doc.meta.get_field("is_pos"):
        doc.is_pos = 1

    if doc.meta.get_field("set_warehouse"):
        doc.set_warehouse = WAREHOUSE

    # Do not throw if invoice is still incomplete.
    if doc.get("patient") or doc.get("custom_kpws_mr_number") or doc.get("customer") or doc.get("custom_is_walkin"):
        ctx = get_context(
            patient=doc.get("patient"),
            mr_number=doc.get("custom_kpws_mr_number"),
            customer=doc.get("customer"),
            is_walkin=doc.get("custom_is_walkin"),
            walkin_name=doc.get("walkin_customer_name"),
            walkin_mr=doc.get("walkin_mr_number"),
        )

        if ctx.get("customer"):
            doc.customer = ctx.get("customer")

        if doc.meta.get_field("custom_kpws_billing_type"):
            doc.custom_kpws_billing_type = ctx.get("patient_type")

        if doc.meta.get_field("custom_panel"):
            doc.custom_panel = ctx.get("panel_customer")

        if doc.meta.get_field("custom_kpws_panel_customer"):
            doc.custom_kpws_panel_customer = ctx.get("panel_customer")

        if doc.meta.get_field("custom_kpws_welfare_registration"):
            doc.custom_kpws_welfare_registration = ctx.get("welfare_registration")

        if doc.meta.get_field("custom_kpws_welfare_type"):
            doc.custom_kpws_welfare_type = ctx.get("welfare_type")

        if doc.meta.get_field("custom_kpws_welfare_percentage"):
            doc.custom_kpws_welfare_percentage = ctx.get("welfare_percentage")

        if ctx.get("pos_profile"):
            doc.pos_profile = ctx.get("pos_profile")

        if ctx.get("selling_price_list"):
            doc.selling_price_list = ctx.get("selling_price_list")

    for row in doc.get("items") or []:
        if row.meta.get_field("warehouse"):
            row.warehouse = WAREHOUSE


def update_pos_profile_masters():
    spw = _price_list("Cash")
    spp = _price_list("Panel")

    if not spw:
        frappe.throw("SPW - Selling Price Welfare price list not found.")
    if not spp:
        frappe.throw("SPP - Selling Price Panel price list not found.")

    if not frappe.db.exists("DocType", "POS Profile"):
        return

    if not frappe.get_meta("POS Profile").get_field("selling_price_list"):
        return

    for row in frappe.get_all("POS Profile", fields=["name"], limit=200):
        low = row.name.lower()

        if "panel" in low:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spp, update_modified=False)
            print("POS Profile:", row.name, "=>", spp)
        elif "cash" in low or "welfare" in low:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spw, update_modified=False)
            print("POS Profile:", row.name, "=>", spw)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable every Sales Invoice Client Script except this one.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name"]):
        if row.name != CLIENT_SCRIPT_NAME:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled Sales Invoice Client Script:", row.name)

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_unified_setup(frm);
    },
    onload(frm) {
        kpws_unified_apply_later(frm);
    },
    refresh(frm) {
        kpws_unified_setup(frm);
        kpws_unified_apply_later(frm);
    },
    patient(frm) {
        kpws_unified_apply_now(frm, true);
    },
    custom_kpws_mr_number(frm) {
        kpws_unified_apply_now(frm, true);
    },
    customer(frm) {
        kpws_unified_apply_now(frm, true);
    },
    custom_is_walkin(frm) {
        kpws_unified_toggle(frm);
        kpws_unified_apply_now(frm, true);
    },
    walkin_customer_name(frm) {
        if (frm.doc.custom_is_walkin) kpws_unified_apply_later(frm);
    },
    walkin_mr_number(frm) {
        if (frm.doc.custom_is_walkin) kpws_unified_apply_later(frm);
    },
    grand_total(frm) {
        kpws_unified_payment_later(frm);
    },
    rounded_total(frm) {
        kpws_unified_payment_later(frm);
    },
    net_total(frm) {
        kpws_unified_payment_later(frm);
    },
    validate(frm) {
        return kpws_unified_apply_now(frm, false);
    },
    before_save(frm) {
        return kpws_unified_apply_now(frm, false);
    }
});

function kpws_unified_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_unified_setup(frm) {
    ["custom_kpws_billing_type", "custom_panel", "custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage", "selling_price_list"].forEach(function(f) {
        if (kpws_unified_has(frm, f)) frm.set_df_property(f, "read_only", 1);
    });

    kpws_unified_toggle(frm);
}

function kpws_unified_toggle(frm) {
    let walkin = !!frm.doc.custom_is_walkin;

    ["walkin_customer_name", "walkin_mr_number"].forEach(function(f) {
        if (kpws_unified_has(frm, f)) {
            frm.toggle_display(f, walkin);
            frm.toggle_reqd(f, walkin);
        }
    });

    ["custom_kpws_mr_number", "patient"].forEach(function(f) {
        if (kpws_unified_has(frm, f)) {
            frm.toggle_display(f, !walkin);
        }
    });
}

function kpws_unified_apply_later(frm) {
    clearTimeout(frm.__kpws_unified_timer);
    frm.__kpws_unified_timer = setTimeout(function() {
        kpws_unified_apply_now(frm, false);
    }, 500);
}

function kpws_unified_payment_later(frm) {
    clearTimeout(frm.__kpws_unified_payment_timer);
    frm.__kpws_unified_payment_timer = setTimeout(function() {
        kpws_unified_apply_payments(frm);
    }, 500);
}

function kpws_unified_total(frm) {
    return flt(frm.doc.rounded_total || frm.doc.grand_total || frm.doc.net_total || 0);
}

function kpws_unified_apply_now(frm, show_loader) {
    if (frm.__kpws_unified_running) {
        return Promise.resolve();
    }

    if (!frm.doc.patient && !frm.doc.customer && !frm.doc.custom_kpws_mr_number && !frm.doc.custom_is_walkin) {
        kpws_unified_set_warehouse_and_pos(frm);
        return Promise.resolve();
    }

    frm.__kpws_unified_running = true;

    if (show_loader) {
        frappe.dom.freeze(__("Loading KPWS billing profile..."));
    }

    return new Promise(function(resolve) {
        frappe.call({
            method: "kpws_customization.api.kpws_si_unified_flow.get_context",
            args: {
                patient: frm.doc.patient || "",
                mr_number: frm.doc.custom_kpws_mr_number || "",
                customer: frm.doc.customer || "",
                is_walkin: frm.doc.custom_is_walkin ? 1 : 0,
                walkin_name: frm.doc.walkin_customer_name || "",
                walkin_mr: frm.doc.walkin_mr_number || ""
            },
            freeze: false,
            callback: function(r) {
                let d = r.message || {};
                frm.__kpws_unified_context = d;

                let updates = {};

                if (kpws_unified_has(frm, "is_pos")) updates.is_pos = 1;
                if (kpws_unified_has(frm, "set_warehouse")) updates.set_warehouse = d.warehouse || "Pharmacy - KPWS";

                if (d.patient && kpws_unified_has(frm, "patient") && frm.doc.patient !== d.patient) updates.patient = d.patient;
                if (d.mr_number && kpws_unified_has(frm, "custom_kpws_mr_number") && !frm.doc.custom_is_walkin) updates.custom_kpws_mr_number = d.mr_number;
                if (d.customer && frm.doc.customer !== d.customer) updates.customer = d.customer;

                if (kpws_unified_has(frm, "patient_name")) updates.patient_name = d.patient_name || "";
                if (kpws_unified_has(frm, "custom_kpws_billing_type")) updates.custom_kpws_billing_type = d.patient_type || "";
                if (kpws_unified_has(frm, "custom_panel")) updates.custom_panel = d.panel_customer || "";
                if (kpws_unified_has(frm, "custom_kpws_panel_customer")) updates.custom_kpws_panel_customer = d.panel_customer || "";
                if (kpws_unified_has(frm, "custom_kpws_welfare_registration")) updates.custom_kpws_welfare_registration = d.welfare_registration || "";
                if (kpws_unified_has(frm, "custom_kpws_welfare_type")) updates.custom_kpws_welfare_type = d.welfare_type || "";
                if (kpws_unified_has(frm, "custom_kpws_welfare_percentage")) updates.custom_kpws_welfare_percentage = d.welfare_percentage || 0;
                if (kpws_unified_has(frm, "pos_profile") && d.pos_profile) updates.pos_profile = d.pos_profile;
                if (kpws_unified_has(frm, "selling_price_list") && d.selling_price_list) updates.selling_price_list = d.selling_price_list;

                frm.set_value(updates).then(function() {
                    kpws_unified_toggle(frm);
                    kpws_unified_set_warehouse_and_pos(frm);
                    kpws_unified_apply_payments(frm);
                    frm.refresh_fields();
                    frm.__kpws_unified_running = false;
                    if (show_loader) frappe.dom.unfreeze();
                    resolve();
                });
            },
            error: function() {
                frm.__kpws_unified_running = false;
                if (show_loader) frappe.dom.unfreeze();
                resolve();
            }
        });
    });
}

function kpws_unified_set_warehouse_and_pos(frm) {
    const WH = "Pharmacy - KPWS";

    if (kpws_unified_has(frm, "is_pos") && frm.doc.is_pos != 1) {
        frm.set_value("is_pos", 1);
    }

    if (kpws_unified_has(frm, "set_warehouse") && frm.doc.set_warehouse !== WH) {
        frm.set_value("set_warehouse", WH);
    }
}

function kpws_unified_mode_is(mode, words) {
    mode = (mode || "").toLowerCase();
    return words.some(function(w) { return mode.includes(w); });
}

function kpws_unified_apply_payments(frm) {
    if (!kpws_unified_has(frm, "payments")) return;

    let total = kpws_unified_total(frm);
    if (!total || total <= 0) return;

    let ctx = frm.__kpws_unified_context || {};
    let patient_type = frm.doc.custom_kpws_billing_type || "";

    if (patient_type === "Welfare") {
        let pct = flt(frm.doc.custom_kpws_welfare_percentage || 0);
        let welfare_type = (frm.doc.custom_kpws_welfare_type || "").toLowerCase();
        let sponsor_mode = welfare_type.includes("zakat") ? (ctx.zakat_mode || "Zakat") : (ctx.donation_mode || "Donation");

        let sponsor_amount = flt(total * pct / 100);
        let cash_amount = flt(total - sponsor_amount);

        frm.clear_table("payments");

        if (sponsor_amount > 0) {
            let s = frm.add_child("payments");
            s.mode_of_payment = sponsor_mode;
            s.amount = sponsor_amount;
        }

        if (cash_amount > 0) {
            let c = frm.add_child("payments");
            c.mode_of_payment = ctx.cash_mode || "Cash";
            c.amount = cash_amount;
        }

        frm.refresh_field("payments");
        return;
    }

    if (patient_type === "Cash" || frm.doc.custom_is_walkin) {
        let card_amount = 0;
        let has_wrong = false;

        (frm.doc.payments || []).forEach(function(row) {
            let mop = row.mode_of_payment || "";
            if (kpws_unified_mode_is(mop, ["card", "credit"])) {
                card_amount += flt(row.amount || 0);
            } else if (!kpws_unified_mode_is(mop, ["cash"])) {
                has_wrong = true;
            }
        });

        if (has_wrong || card_amount > total) {
            card_amount = 0;
        }

        frm.clear_table("payments");

        let cash = frm.add_child("payments");
        cash.mode_of_payment = ctx.cash_mode || "Cash";
        cash.amount = flt(total - card_amount);

        let card = frm.add_child("payments");
        card.mode_of_payment = ctx.card_mode || "Credit Card";
        card.amount = card_amount;

        frm.refresh_field("payments");
        return;
    }

    // Panel: keep POS profile enabled, but do not force medicine-row scripts here.
}
'''

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
        print(patient_type, "=>", _pos_profile(patient_type), "|", _price_list(patient_type))

    print("")
    print("DONE: Unified Sales Invoice Client Script installed.")



# --- KPWS FINAL payment mode enforcement ---
def _kpws_final_payment_mode(names):
    for name in names:
        if frappe.db.exists("Mode of Payment", name):
            return name

    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=200)
    for row in rows:
        low = row.name.lower()
        for name in names:
            if name.lower() in low:
                return row.name

    return names[0] if names else ""


def _kpws_final_invoice_total(doc):
    return float(doc.get("rounded_total") or doc.get("grand_total") or doc.get("net_total") or 0)


def _kpws_final_latest_welfare_for_invoice(doc):
    patient = doc.get("patient")
    if not patient:
        return {}

    try:
        return _latest_welfare(patient) or {}
    except Exception:
        return {}


def enforce_payment_modes_on_validate(doc, method=None):
    patient_type = doc.get("custom_kpws_billing_type") or ""
    total = _kpws_final_invoice_total(doc)

    if total <= 0:
        return

    cash_mode = _kpws_final_payment_mode(["Cash"])
    card_mode = _kpws_final_payment_mode(["Credit Card", "Card"])
    panel_mode = _kpws_final_payment_mode(["Panel"])
    zakat_mode = _kpws_final_payment_mode(["Zakat"])
    donation_mode = _kpws_final_payment_mode(["Donation"])

    # Cash / Walk-in = Cash + optional Credit Card only.
    if patient_type == "Cash" or doc.get("custom_is_walkin"):
        existing_card_amount = 0

        for row in doc.get("payments") or []:
            mode = str(row.mode_of_payment or "").lower()
            if "card" in mode or "credit" in mode:
                existing_card_amount += float(row.amount or 0)

        if existing_card_amount > total:
            existing_card_amount = 0

        cash_amount = total - existing_card_amount

        doc.set("payments", [])
        doc.append("payments", {
            "mode_of_payment": cash_mode,
            "amount": cash_amount,
        })

        if existing_card_amount > 0:
            doc.append("payments", {
                "mode_of_payment": card_mode,
                "amount": existing_card_amount,
            })

        return

    # Panel = Panel mode only.
    if patient_type == "Panel":
        doc.set("payments", [])
        doc.append("payments", {
            "mode_of_payment": panel_mode,
            "amount": total,
        })
        return

    # Welfare = based on latest Patient Registration Form.
    if patient_type == "Welfare":
        welfare = _kpws_final_latest_welfare_for_invoice(doc)

        welfare_type = (
            doc.get("custom_kpws_welfare_type")
            or welfare.get("type")
            or welfare.get("welfare_type")
            or ""
        )

        percentage = doc.get("custom_kpws_welfare_percentage")
        if percentage in (None, ""):
            percentage = welfare.get("percentage") or welfare.get("welfare_percentage") or 0

        percentage = float(percentage or 0)

        if percentage < 0:
            percentage = 0

        if percentage > 100:
            percentage = 100

        sponsor_amount = total * percentage / 100
        cash_amount = total - sponsor_amount

        sponsor_mode = zakat_mode if "zakat" in str(welfare_type).lower() else donation_mode

        doc.set("payments", [])

        if sponsor_amount > 0:
            doc.append("payments", {
                "mode_of_payment": sponsor_mode,
                "amount": sponsor_amount,
            })

        if cash_amount > 0:
            doc.append("payments", {
                "mode_of_payment": cash_mode,
                "amount": cash_amount,
            })

        return
