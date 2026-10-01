import json, re
import frappe
from frappe.utils import cint, flt, nowdate

PATIENT_TYPES = ["Cash", "Welfare", "Panel", "Personal Advance"]
FUNDING_SOURCES = ["Zakat", "Donation", "Panel"]

# KPWS_AUDIT_PATCH_D_20260620: structured Patient address fields mirrored to Welfare Approval.
ADDRESS_FIELDS = [
    ("address_line1", "custom_kpws_address_line1", "Address Line 1"),
    ("address_line2", "custom_kpws_address_line2", "Address Line 2"),
    ("area_mohalla", "custom_kpws_area_mohalla", "Area / Mohalla"),
    ("city", "custom_kpws_city", "City"),
    ("district", "custom_kpws_district", "District"),
    ("province", "custom_kpws_province", "Province"),
    ("postal_code", "custom_kpws_postal_code", "Postal Code"),
    ("country", "custom_kpws_country", "Country"),
]


def _address_custom_fields(insert_after="patient_details"):
    out = []
    prev = insert_after
    for _key, fieldname, label in ADDRESS_FIELDS:
        out.append({"fieldname": fieldname, "label": label, "fieldtype": "Data", "insert_after": prev})
        prev = fieldname
    return out


def _address_from_doc(doc):
    return {key: doc.get(fieldname) if doc and doc.meta.has_field(fieldname) else "" for key, fieldname, _label in ADDRESS_FIELDS}


def _address_from_payload(raw):
    values = {}
    for key, fieldname, _label in ADDRESS_FIELDS:
        values[key] = _pick(raw, key, fieldname) or ""
    return values


def _address_text(values):
    order = ["address_line1", "address_line2", "area_mohalla", "city", "district", "province", "postal_code", "country"]
    return "\n".join([str(values.get(k) or "").strip() for k in order if str(values.get(k) or "").strip()])


def _d(v):
    if isinstance(v, dict):
        return frappe._dict(v)
    if isinstance(v, str):
        try:
            return frappe._dict(json.loads(v))
        except Exception:
            return frappe._dict({})
    return frappe._dict({})


def _digits(v):
    return re.sub(r"\D+", "", str(v or ""))


def _has(dt, field):
    try:
        return frappe.get_meta(dt).has_field(field)
    except Exception:
        return False


def _set(doc, field, val, blank=False):
    if (val is None or val == "") and not blank:
        return
    if doc.meta.has_field(field):
        doc.set(field, val)


def _pick(data, *keys):
    lower = {str(k).lower(): v for k, v in (data or {}).items()}
    for k in keys:
        if k in data and data.get(k) not in (None, ""):
            return data.get(k)
        lk = str(k).lower()
        if lk in lower and lower.get(lk) not in (None, ""):
            return lower.get(lk)
    return None


def _patient_cnic(patient):
    for f in ["custom_kpws_cnic", "cnic", "cnic_number", "custom_cnic", "custom_cnic_number"]:
        if _has("Patient", f):
            v = frappe.db.get_value("Patient", patient, f)
            if v:
                return v
    return None


def _duplicate_cnic(cnic, exclude=None):
    n = _digits(cnic)
    if not n:
        return None
    for f in ["custom_kpws_cnic", "cnic", "cnic_number", "custom_cnic", "custom_cnic_number"]:
        if not _has("Patient", f):
            continue
        for r in frappe.get_all("Patient", filters={f: ["is", "set"]}, fields=["name", f], limit=10000):
            if exclude and r.name == exclude:
                continue
            if _digits(r.get(f)) == n:
                return r.name
    return None


def cleanup_contact_primary_phones():
    if not frappe.db.exists("DocType", "Contact Phone"):
        return {"fixed": 0}
    fixed = 0
    for f in ["is_primary_phone", "is_primary_mobile_no"]:
        if not frappe.db.has_column("Contact Phone", f):
            continue
        parents = frappe.db.sql(f"""
            SELECT parent FROM `tabContact Phone`
            WHERE IFNULL(`{f}`,0)=1 GROUP BY parent HAVING COUNT(*)>1
        """, as_dict=True)
        for p in parents:
            rows = frappe.get_all("Contact Phone", filters={"parent": p.parent, f: 1}, fields=["name", "idx"], order_by="idx asc, creation asc")
            keep = rows[0].name if rows else None
            for row in rows:
                if row.name != keep:
                    frappe.db.set_value("Contact Phone", row.name, f, 0, update_modified=False)
                    fixed += 1
    frappe.db.commit()
    return {"fixed": fixed}


def _safe_save(doc):
    try:
        doc.save(ignore_permissions=True)
    except Exception as e:
        msg = str(e)
        if "Only one" in msg and "Phone" in msg and "primary" in msg:
            cleanup_contact_primary_phones()
            doc.save(ignore_permissions=True)
        else:
            raise


def _display(doc):
    return doc.get("patient_name") or " ".join([str(doc.get("first_name") or ""), str(doc.get("last_name") or "")]).strip() or doc.name


def _ensure_page():
    name = "kpws-patient-intake"
    page = frappe.get_doc("Page", name) if frappe.db.exists("Page", name) else frappe.new_doc("Page")
    if not page.get("page_name"):
        page.page_name = name
    page.title = "KPWS Patient Intake"
    page.module = "Kpws Customization"
    page.standard = "Yes"
    page.system_page = 0
    page.roles = []
    for role in ["System Manager", "Administrator", "Receptionist", "Healthcare User", "Accounts User"]:
        if frappe.db.exists("Role", role):
            page.append("roles", {"role": role})
    page.save(ignore_permissions=True)


def _ensure_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({
        "Patient": [
            {"fieldname": "custom_kpws_cnic", "label": "CNIC", "fieldtype": "Data", "insert_after": "custom_reference_number"},
            {"fieldname": "custom_kpws_mobile_no", "label": "Mobile No", "fieldtype": "Data", "insert_after": "custom_kpws_cnic"},
            {"fieldname": "custom_kpws_funding_source", "label": "Funding Source", "fieldtype": "Select", "options": "\nSelf Paid\nZakat\nDonation\nPanel\nPersonal Advance", "insert_after": "customer_group"},
        ] + _address_custom_fields("patient_details"),
        "Patient Registration Form": [
            {"fieldname": "custom_kpws_funding_source", "label": "Funding Source", "fieldtype": "Select", "options": "\nZakat\nDonation\nPanel", "insert_after": "custom_billing_type"},
        ] + _address_custom_fields("address"),
    }, update=True)
    for f in ["purpose", "custom_kpws_welfare_type"]:
        if _has("Patient Registration Form", f):
            frappe.db.set_value("DocField", {"parent": "Patient Registration Form", "fieldname": f}, "options", "\nZakat\nDonation\nPanel")
            cf = frappe.db.get_value("Custom Field", {"dt": "Patient Registration Form", "fieldname": f}, "name")
            if cf:
                frappe.db.set_value("Custom Field", cf, "options", "\nZakat\nDonation\nPanel")
    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache(doctype="Patient Registration Form")
    frappe.db.updatedb("Patient")
    frappe.db.updatedb("Patient Registration Form")


@frappe.whitelist()
def install():
    _ensure_fields()
    _ensure_page()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_panel_customers():
    filters = {"custom_is_panel": 1} if frappe.db.has_column("Customer", "custom_is_panel") else {"customer_group": "Panel"}
    return [{"value": r.name, "label": r.customer_name or r.name} for r in frappe.get_all("Customer", filters=filters, fields=["name", "customer_name"], order_by="customer_name asc", limit=500)]


@frappe.whitelist()
def get_boot():
    return {"patient_types": PATIENT_TYPES, "funding_sources": FUNDING_SOURCES, "panel_customers": get_panel_customers()}


def _latest_prf(patient):
    if not patient or not frappe.db.exists("DocType", "Patient Registration Form"):
        return None
    for f in ["custom_patient", "patient", "custom_kpws_patient", "patient_id", "custom_patient_id"]:
        if not _has("Patient Registration Form", f):
            continue
        rows = frappe.get_all("Patient Registration Form", filters={f: patient}, fields=["name", "docstatus", "workflow_state", "modified"], order_by="modified desc", limit=1)
        if rows:
            return rows[0]
    return None


def _prf_details(name):
    if not name:
        return {}
    d = frappe.get_doc("Patient Registration Form", name)
    return {
        "name": d.name,
        "docstatus": d.docstatus,
        "workflow_state": d.get("workflow_state"),
        "purpose": d.get("custom_kpws_welfare_type") or d.get("purpose") or d.get("custom_kpws_funding_source"),
        "percentage": d.get("custom_kpws_welfare_percentage") or d.get("discount_value"),
        "panel_customer": d.get("custom_panel_customer") or d.get("custom_kpws_assigned_panel_customer"),
    }


def _advance(customer):
    if not customer:
        return 0
    rows = frappe.db.sql("""
        SELECT SUM(IFNULL(unallocated_amount,0)) amount
        FROM `tabPayment Entry`
        WHERE docstatus=1 AND party_type='Customer' AND party=%s AND IFNULL(unallocated_amount,0)>0
    """, (customer,), as_dict=True)
    return flt(rows[0].amount if rows else 0, 2)


def _decision(p=None, prf=None):
    typ = (p.get("customer_group") if p else None) or "Cash"
    src = (p.get("custom_kpws_funding_source") if p else None) or ""
    panel = (p.get("custom_panel_customer") if p else None) or ""
    pct = 0
    if prf:
        src = prf.get("purpose") or src
        panel = prf.get("panel_customer") or panel
        pct = flt(prf.get("percentage") or 0)
    d = {"patient_type": typ, "funding_source": src, "panel_customer": panel, "percentage": pct, "billing_type": "Cash", "invoice_mode": "POS", "message": "Cash: collect Cash/Card.", "requires_prf": False}
    if typ == "Cash":
        d.update({"funding_source": "", "billing_type": "Cash", "invoice_mode": "POS", "message": "Cash patient: no funding source required."})
    elif typ == "Welfare":
        d["requires_prf"] = True
        if src == "Panel":
            d.update({"billing_type": "Welfare Panel", "invoice_mode": "Non-POS", "message": "Bill the selected panel customer. No Zakat/Donation JV."})
        elif src == "Donation":
            d.update({"billing_type": "Welfare Donation", "invoice_mode": "Non-POS", "message": "Donation JV plus patient share if below 100%."})
        elif src == "Zakat":
            d.update({"billing_type": "Welfare Zakat", "invoice_mode": "Non-POS", "message": "Zakat JV plus patient share if below 100%."})
        else:
            d.update({"billing_type": "Welfare Pending", "invoice_mode": "Blocked", "message": "Select Funding Source and send for approval."})
    elif typ == "Panel":
        d.update({"funding_source": "", "billing_type": "Panel", "invoice_mode": "Non-POS", "message": "Bill selected panel; invoice remains unpaid until panel pays."})
    elif typ == "Personal Advance":
        d.update({"funding_source": "Personal Advance", "billing_type": "Personal Advance", "invoice_mode": "Non-POS", "message": "Use patient advance first, then collect remaining cash/card."})
    return d


@frappe.whitelist()
def get_context(patient=None):
    pdata, prfdata = {}, {}
    if patient and frappe.db.exists("Patient", patient):
        d = frappe.get_doc("Patient", patient)
        pdata = {"name": d.name, "patient_name": _display(d), "first_name": d.get("first_name"), "last_name": d.get("last_name"), "age": d.get("age_") or d.get("age"), "sex": d.get("sex") or d.get("gender"), "patient_status": d.get("patient_status"), "mr_number": d.get("custom_reference_number"), "old_kpws_number": d.get("custom_old_kpws_number"), "cnic": _patient_cnic(d.name), "mobile": d.get("mobile") or d.get("mobile_no") or d.get("custom_kpws_mobile_no") or d.get("phone"), "customer_group": d.get("customer_group"), "customer": d.get("customer"), "funding_source": d.get("custom_kpws_funding_source"), "panel_customer": d.get("custom_panel_customer"), "patient_details": d.get("patient_details")}
        pdata.update(_address_from_doc(d))
        prf = _latest_prf(d.name)
        if prf:
            prfdata = _prf_details(prf.name)
        return {"patient": pdata, "prf": prfdata, "decision": _decision(d, prfdata), "advance_balance": _advance(pdata.get("customer")), "panel_customers": get_panel_customers()}
    return {"patient": pdata, "prf": prfdata, "decision": _decision(), "advance_balance": 0, "panel_customers": get_panel_customers()}


@frappe.whitelist()
def search_patients(query=None):
    q = (query or "").strip().lower()
    qd = _digits(query)
    if not q:
        return []
    fields = ["name"] + [f for f in ["patient_name", "first_name", "last_name", "custom_reference_number", "customer_group", "custom_panel_customer"] if _has("Patient", f)]
    out = []
    for r in frappe.get_all("Patient", fields=list(dict.fromkeys(fields)), order_by="modified desc", limit=1000):
        cnic = _patient_cnic(r.name)
        hay = " ".join([str(r.get(f) or "") for f in fields] + [str(cnic or "")]).lower()
        if q in hay or (qd and qd in _digits(hay)):
            out.append({"name": r.name, "label": r.get("patient_name") or " ".join([str(r.get("first_name") or ""), str(r.get("last_name") or "")]).strip() or r.name, "mr_number": r.get("custom_reference_number"), "cnic": cnic, "patient_type": r.get("customer_group"), "panel_customer": r.get("custom_panel_customer")})
        if len(out) >= 30:
            break
    return out


@frappe.whitelist()
def save_patient(payload=None, data=None, **kwargs):
    raw = {}
    raw.update(_d(payload)); raw.update(_d(data)); raw.update(_d(kwargs))
    for k, v in dict(frappe.form_dict).items():
        if k == "cmd": continue
        if k in ("payload", "data") and isinstance(v, str): raw.update(_d(v))
        else: raw[k] = v
    if isinstance(raw.get("patient"), dict): raw.update(raw.get("patient"))

    patient_id = _pick(raw, "patient", "name", "patient_docname")
    doc = frappe.get_doc("Patient", patient_id) if patient_id and frappe.db.exists("Patient", patient_id) else frappe.new_doc("Patient")

    full = _pick(raw, "patient_name", "full_name")
    first = _pick(raw, "first_name")
    last = _pick(raw, "last_name")
    if not first and full:
        parts = str(full).strip().split()
        first = parts[0] if parts else None
        last = " ".join(parts[1:]) if len(parts) > 1 else last
    age = _pick(raw, "age", "age_")
    sex = _pick(raw, "sex", "gender")
    cnic = _pick(raw, "cnic", "custom_kpws_cnic")
    mobile = _pick(raw, "mobile", "mobile_no")
    ptype = _pick(raw, "patient_type", "customer_group") or "Cash"
    source = _pick(raw, "funding_source", "custom_kpws_funding_source")
    panel = _pick(raw, "panel_customer", "custom_panel_customer")

    if not cnic: frappe.throw("CNIC is mandatory.")
    dup = _duplicate_cnic(cnic, exclude=doc.name if doc.name else None)
    if dup: frappe.throw("Patient already exists with this CNIC. Existing Patient: {0}".format(dup))
    if not first: frappe.throw("Patient Name is mandatory.")
    if not age: frappe.throw("Age is mandatory.")
    if not sex: frappe.throw("Gender is mandatory.")
    if ptype not in PATIENT_TYPES: frappe.throw("Invalid Patient Type: {0}".format(ptype))
    if ptype == "Cash": source, panel = "", ""
    elif ptype == "Welfare":
        if source not in FUNDING_SOURCES: frappe.throw("Funding Source is required for Welfare: Zakat, Donation, or Panel.")
        if source == "Panel" and not panel: frappe.throw("Panel Name is mandatory for Welfare Panel.")
    elif ptype == "Panel":
        source = ""
        if not panel: frappe.throw("Panel Name is mandatory for Panel patient.")
    elif ptype == "Personal Advance": source = "Personal Advance"

    _set(doc, "first_name", first); _set(doc, "last_name", last)
    _set(doc, "age_", age); _set(doc, "age", age)
    _set(doc, "sex", sex); _set(doc, "gender", sex)
    _set(doc, "patient_status", _pick(raw, "patient_status") or "SE")
    if _has("Patient", "status") and not doc.get("status"): doc.status = "Active"
    for f in ["custom_kpws_cnic", "cnic", "cnic_number"]: _set(doc, f, cnic)
    for f in ["mobile", "mobile_no", "phone", "custom_kpws_mobile_no"]: _set(doc, f, mobile)
    _set(doc, "custom_reference_number", _pick(raw, "mr_number", "custom_reference_number"))
    _set(doc, "custom_old_kpws_number", _pick(raw, "old_kpws_number", "custom_old_kpws_number"))
    _set(doc, "customer_group", ptype)
    _set(doc, "custom_kpws_funding_source", source, True)
    _set(doc, "custom_panel_customer", panel, True)
    _set(doc, "patient_details", _pick(raw, "patient_details", "notes"))
    for key, fieldname, _label in ADDRESS_FIELDS:
        _set(doc, fieldname, _pick(raw, key, fieldname), True)

    missing = [(df.label or df.fieldname) for df in doc.meta.fields if cint(df.reqd) and doc.get(df.fieldname) in (None, "", [])]
    if missing: frappe.throw("Please fill mandatory Patient fields: " + ", ".join(missing))
    _safe_save(doc)
    frappe.db.commit()
    return get_context(doc.name)


def _sp(doc, field, val, blank=False):
    if (val in (None, "")) and not blank: return
    if doc.meta.has_field(field): doc.set(field, val)


@frappe.whitelist()
def send_for_welfare_approval(patient):
    if not patient or not frappe.db.exists("Patient", patient): frappe.throw("Please save/select a Patient first.")
    p = frappe.get_doc("Patient", patient)
    if p.get("customer_group") != "Welfare": frappe.throw("Only Welfare patients can be sent for approval.")
    source, panel = p.get("custom_kpws_funding_source"), p.get("custom_panel_customer")
    if source not in FUNDING_SOURCES: frappe.throw("Select Funding Source: Zakat, Donation, or Panel.")
    if source == "Panel" and not panel: frappe.throw("Panel Name is mandatory for Welfare Panel.")
    latest = _latest_prf(patient)
    prf = frappe.get_doc("Patient Registration Form", latest.name) if latest and cint(latest.docstatus) == 0 else frappe.new_doc("Patient Registration Form")
    _sp(prf, "custom_patient", p.name); _sp(prf, "patient", p.name)
    _sp(prf, "custom_mr_number", p.get("custom_reference_number"))
    _sp(prf, "custom_patient_name", _display(p)); _sp(prf, "custom_patient_customer", p.get("customer"))
    _sp(prf, "custom_billing_type", p.get("customer_group"))
    _sp(prf, "custom_kpws_funding_source", source); _sp(prf, "purpose", source); _sp(prf, "custom_kpws_welfare_type", source)
    _sp(prf, "custom_panel_customer", panel, True); _sp(prf, "custom_kpws_assigned_panel_customer", panel, True)
    address_values = _address_from_doc(p)
    for _key, fieldname, _label in ADDRESS_FIELDS:
        _sp(prf, fieldname, address_values.get(_key), True)
    _sp(prf, "address", _address_text(address_values), True)
    if not prf.get("discount_value"): _sp(prf, "discount_value", 100)
    if not prf.get("custom_kpws_welfare_percentage"): _sp(prf, "custom_kpws_welfare_percentage", 100)
    if prf.meta.has_field("workflow_state") and not prf.get("workflow_state"): prf.workflow_state = "Pending Approval"
    prf.save(ignore_permissions=True); frappe.db.commit()
    return {"ok": True, "registration": prf.name, "message": "Patient sent for welfare approval: {0}".format(prf.name), "context": get_context(patient)}


@frappe.whitelist()
def create_token(patient):
    if not patient or not frappe.db.exists("Patient", patient): frappe.throw("Please save/select a Patient first.")
    if not frappe.db.exists("DocType", "Patient Token"): frappe.throw("Patient Token DocType does not exist.")
    p = frappe.get_doc("Patient", patient)
    token = frappe.new_doc("Patient Token")
    def st(f, v):
        if token.meta.has_field(f) and v not in (None, ""): token.set(f, v)
    st("patient", p.name); st("custom_patient", p.name)
    st("patient_name", _display(p)); st("custom_patient_name", _display(p))
    st("mr_number", p.get("custom_reference_number")); st("custom_mr_number", p.get("custom_reference_number"))
    st("posting_date", nowdate()); st("date", nowdate()); st("token_date", nowdate())
    token.flags.ignore_mandatory = True
    token.insert(ignore_permissions=True); frappe.db.commit()
    return {"ok": True, "token": token.name, "message": "Token created: {0}".format(token.name), "context": get_context(patient)}
