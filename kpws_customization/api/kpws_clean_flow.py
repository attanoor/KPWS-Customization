import frappe
from frappe.model.naming import make_autoname
from frappe import _
from frappe.utils import cint, flt

ALLOWED_PANEL_ROLES = {"Administrator", "System Manager", "Accounts Manager", "Healthcare Manager"}

PATIENT_MR_FIELDS = [
    "mr_no", "mr_number", "custom_mr_number", "custom_mr_no", "reference_number",
    "custom_reference_number", "uid", "patient_mr_number"
]
PATIENT_PANEL_FIELDS = ["panel_name", "custom_panel_customer", "panel_customer", "custom_panel", "panel"]
PRF_PATIENT_FIELDS = ["patient", "custom_patient", "patient_id", "kpws_patient"]
PRF_MR_FIELDS = ["mr_no", "mr_number", "custom_mr_number", "custom_reference_number", "reference_number"]
PRF_NAME_FIELDS = ["patient_full_name", "patient_name", "custom_patient_name", "full_name"]


def _has_field(doctype, fieldname):
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _get_doc_value(doctype, name, fields):
    for f in fields:
        if _has_field(doctype, f):
            v = frappe.db.get_value(doctype, name, f)
            if v not in (None, ""):
                return v
    return ""


def _set_if_field(doc, fields, value):
    for f in fields:
        if doc.meta.get_field(f):
            doc.set(f, value)
            return f
    return None


def _roles_allowed(allowed):
    roles = set(frappe.get_roles(frappe.session.user)) | {frappe.session.user}
    return bool(roles.intersection(allowed))


def _is_panel_customer(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False
    if _has_field("Customer", "custom_is_panel"):
        return cint(frappe.db.get_value("Customer", customer, "custom_is_panel")) == 1
    return False


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    # Strict rule: panel list comes ONLY from Customer.custom_is_panel = 1.
    txt = txt or ""
    like_txt = f"%{txt}%"
    if not _has_field("Customer", "custom_is_panel"):
        return []
    return frappe.db.sql(
        """
        SELECT name, customer_name, customer_group
        FROM `tabCustomer`
        WHERE disabled = 0
          AND IFNULL(custom_is_panel, 0) = 1
          AND (name LIKE %(txt)s OR customer_name LIKE %(txt)s OR customer_group LIKE %(txt)s)
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {"txt": like_txt, "start": cint(start or 0), "page_len": cint(page_len or 20)},
    )


def _find_customer(value, panel_only=False):
    if not value:
        return None
    if frappe.db.exists("Customer", value):
        customer = value
    else:
        customer = frappe.db.get_value("Customer", {"customer_name": value}, "name")
    if panel_only and customer and not _is_panel_customer(customer):
        return None
    return customer


def _resolve_patient(patient=None, mr_number=None, customer=None):
    patient = (patient or "").strip()
    mr_number = (mr_number or "").strip()
    customer = (customer or "").strip()

    if patient:
        if frappe.db.exists("Patient", patient):
            return patient
        for f in ["patient_name"] + PATIENT_MR_FIELDS:
            if _has_field("Patient", f):
                found = frappe.db.get_value("Patient", {f: patient}, "name")
                if found:
                    return found

    if mr_number:
        if frappe.db.exists("Patient", mr_number):
            return mr_number
        for f in PATIENT_MR_FIELDS:
            if _has_field("Patient", f):
                found = frappe.db.get_value("Patient", {f: mr_number}, "name")
                if found:
                    return found

    if customer and _has_field("Patient", "customer"):
        found = frappe.db.get_value("Patient", {"customer": customer}, "name")
        if found:
            return found
    return None


def _patient_customer(patient):
    if patient and _has_field("Patient", "customer"):
        c = frappe.db.get_value("Patient", patient, "customer")
        if c and frappe.db.exists("Customer", c):
            return c
    return None


def _customer_group(customer):
    return frappe.db.get_value("Customer", customer, "customer_group") if customer else ""


def _billing_type_from_group(value):
    text = str(value or "").strip().lower()
    if "panel" in text:
        return "Panel"
    if "welfare" in text or "zakat" in text or "donation" in text:
        return "Welfare"
    if "cash" in text:
        return "Cash"
    return ""


def _patient_billing_type(patient, patient_customer=None):
    # Preferred source: Patient.customer_group, then linked Customer.customer_group.
    if patient and _has_field("Patient", "customer_group"):
        val = frappe.db.get_value("Patient", patient, "customer_group")
        billing = _billing_type_from_group(val)
        if billing:
            return billing

    # Backward compatibility only: old custom select fields if Patient.customer_group is empty.
    for f in ["custom_patient_billing_type", "patient_billing_type", "billing_type", "custom_billing_type"]:
        if patient and _has_field("Patient", f):
            billing = _billing_type_from_group(frappe.db.get_value("Patient", patient, f))
            if billing:
                return billing

    billing = _billing_type_from_group(_customer_group(patient_customer))
    return billing or "Cash"


def _patient_mr(patient):
    return _get_doc_value("Patient", patient, PATIENT_MR_FIELDS) or patient or ""


def _patient_panel_customer(patient):
    for f in PATIENT_PANEL_FIELDS:
        if _has_field("Patient", f):
            customer = _find_customer(frappe.db.get_value("Patient", patient, f), panel_only=True)
            if customer:
                return customer
    return None


def _get_mode_of_payment(candidates):
    for m in candidates:
        if frappe.db.exists("Mode of Payment", m):
            return m
    return candidates[0] if candidates else ""


def _get_pos_profile(billing_type):
    key = (billing_type or "Cash").lower()
    candidates = {
        "cash": ["Cash", "KPWS Cash", "Cash - KPWS"],
        "welfare": ["Welfare", "KPWS Welfare", "Welfare - KPWS"],
        "panel": ["Panel", "KPWS Panel", "Panel - KPWS"],
    }.get(key, [])
    for name in candidates:
        if frappe.db.exists("POS Profile", name):
            return name
    for row in frappe.get_all("POS Profile", filters={"disabled": 0}, fields=["name"], limit=100):
        if key in (row.name or "").lower():
            return row.name
    return ""


def _get_price_list(billing_type):
    if billing_type == "Panel":
        return "SPP - Selling Price Panel" if frappe.db.exists("Price List", "SPP - Selling Price Panel") else ""
    return "SPW - Selling Price Welfare" if frappe.db.exists("Price List", "SPW - Selling Price Welfare") else ""


def _prf_candidate_fields(meta):
    fields = ["name", "modified", "docstatus"]
    for f in [
        "workflow_state", "status", "review_status", "custom_review_status",
        "custom_kpws_welfare_type", "custom_kpws_welfare_percentage",
        "custom_kpws_assigned_panel_customer", "custom_kpws_admin_notes",
        "custom_assistance_type", "assistance_type", "welfare_type", "purpose",
        "discount_purpose", "custom_coverage_percentage", "coverage_percentage", "discount_value",
        "custom_panel_customer", "panel_customer", "custom_panel", "panel",
    ]:
        if meta.get_field(f) and f not in fields:
            fields.append(f)
    return fields


def _latest_welfare_registration(patient):
    if not patient or not frappe.db.exists("DocType", "Patient Registration Form"):
        return None

    meta = frappe.get_meta("Patient Registration Form")
    patient_name = frappe.db.get_value("Patient", patient, "patient_name") or patient
    mr_number = _patient_mr(patient)

    filters_list = []
    for f in PRF_PATIENT_FIELDS:
        if meta.get_field(f):
            filters_list.append({f: patient})
    for f in PRF_MR_FIELDS:
        if meta.get_field(f) and mr_number:
            filters_list.append({f: mr_number})
    for f in PRF_NAME_FIELDS:
        if meta.get_field(f) and patient_name:
            filters_list.append({f: patient_name})

    if not filters_list:
        return None

    fields = _prf_candidate_fields(meta)
    rows, seen = [], set()
    for flt_dict in filters_list:
        filters = dict(flt_dict)
        try:
            found = frappe.get_all("Patient Registration Form", filters=filters, fields=fields, order_by="modified desc", limit=10)
        except Exception:
            found = []
        for r in found:
            if r.name in seen:
                continue
            seen.add(r.name)
            if cint(r.get("docstatus")) == 2:
                continue
            rows.append(r)

    if not rows:
        return None

    def score(row):
        state = str(row.get("workflow_state") or row.get("status") or row.get("custom_review_status") or "").lower()
        approved = 1 if "approved" in state else 0
        return (approved, str(row.get("modified") or ""))

    rows.sort(key=score, reverse=True)
    r = rows[0]

    assistance = (
        r.get("custom_kpws_welfare_type") or r.get("custom_assistance_type") or r.get("assistance_type")
        or r.get("welfare_type") or r.get("purpose") or r.get("discount_purpose") or "Donation"
    )
    assistance = "Zakat" if "zakat" in str(assistance).lower() else "Donation"

    pct = r.get("custom_kpws_welfare_percentage")
    if pct in (None, ""):
        pct = r.get("custom_coverage_percentage")
    if pct in (None, ""):
        pct = r.get("coverage_percentage")
    if pct in (None, ""):
        pct = r.get("discount_value") or 0

    panel_customer = ""
    for f in ["custom_kpws_assigned_panel_customer", "custom_panel_customer", "panel_customer", "custom_panel", "panel"]:
        panel_customer = _find_customer(r.get(f), panel_only=True)
        if panel_customer:
            break

    return {
        "registration": r.name,
        "assistance_type": assistance,
        "coverage_percentage": flt(pct),
        "panel_customer": panel_customer or "",
        "mode_of_payment": _get_mode_of_payment([assistance]),
    }


@frappe.whitelist()
def get_patient_snapshot(patient=None, mr_number=None, customer=None):
    patient = _resolve_patient(patient=patient, mr_number=mr_number, customer=customer)
    if not patient:
        return {}
    p = frappe.get_doc("Patient", patient)
    patient_customer = _patient_customer(patient)
    return {
        "patient": patient,
        "patient_name": getattr(p, "patient_name", None) or patient,
        "mr_number": _patient_mr(patient),
        "customer": patient_customer or "",
        "customer_group": _customer_group(patient_customer) or getattr(p, "customer_group", "") or "",
        "mobile": _get_doc_value("Patient", patient, ["mobile", "phone", "mobile_no", "custom_mobile_no"]),
        "email": _get_doc_value("Patient", patient, ["email", "email_id", "custom_email"]),
        "cnic": _get_doc_value("Patient", patient, ["cnic", "custom_cnic", "national_id", "custom_national_id"]),
        "gender": _get_doc_value("Patient", patient, ["sex", "gender"]),
        "dob": _get_doc_value("Patient", patient, ["dob", "date_of_birth"]),
        "address": _get_doc_value("Patient", patient, ["address", "custom_address", "address_line1"]),
    }


@frappe.whitelist()
def get_patient_billing_context(patient=None, mr_number=None, customer=None):
    patient = _resolve_patient(patient=patient, mr_number=mr_number, customer=customer)
    if not patient:
        return {}

    patient_customer = _patient_customer(patient)
    billing_type = _patient_billing_type(patient, patient_customer)
    panel_customer = _patient_panel_customer(patient)
    welfare = _latest_welfare_registration(patient) if billing_type == "Welfare" else None

    invoice_customer = panel_customer if billing_type == "Panel" and panel_customer else patient_customer
    if not invoice_customer and customer and frappe.db.exists("Customer", customer):
        invoice_customer = customer

    patient_name = frappe.db.get_value("Patient", patient, "patient_name") or patient
    return {
        "patient": patient,
        "patient_name": patient_name,
        "mr_number": _patient_mr(patient),
        "patient_customer": patient_customer or "",
        "customer": invoice_customer or "",
        "panel_customer": panel_customer or "",
        "panel_customer_name": frappe.db.get_value("Customer", panel_customer, "customer_name") if panel_customer else "",
        "billing_type": billing_type,
        "customer_group": _customer_group(patient_customer) or "",
        "pos_profile": _get_pos_profile(billing_type),
        "selling_price_list": _get_price_list(billing_type),
        "welfare": welfare,
        "cash_mode_of_payment": _get_mode_of_payment(["Cash"]),
        "card_mode_of_payment": _get_mode_of_payment(["Credit Card", "Card", "Bank Card"]),
    }


@frappe.whitelist()
def get_sales_invoice_context(patient=None, mr_number=None, customer=None, is_walkin=0, walkin_name=None, walkin_mr_number=None):
    if cint(is_walkin):
        walkin_customer = None
        for c in ["Walk-in Cash Customer - KPWS", "Walk-in Customer", "Cash Customer"]:
            if frappe.db.exists("Customer", c):
                walkin_customer = c
                break
        return {
            "patient": "",
            "patient_name": walkin_name or "Walk-in Patient",
            "mr_number": walkin_mr_number or "",
            "billing_type": "Cash",
            "patient_customer": "",
            "customer": walkin_customer or customer or "",
            "panel_customer": "",
            "pos_profile": _get_pos_profile("Cash"),
            "selling_price_list": _get_price_list("Cash"),
            "welfare": None,
            "cash_mode_of_payment": _get_mode_of_payment(["Cash"]),
            "card_mode_of_payment": _get_mode_of_payment(["Credit Card", "Card", "Bank Card"]),
        }
    return get_patient_billing_context(patient=patient, mr_number=mr_number, customer=customer)


@frappe.whitelist()
def create_or_open_welfare_registration(patient):
    patient = _resolve_patient(patient=patient)
    if not patient:
        frappe.throw(_("Patient not found."))
    if not frappe.db.exists("DocType", "Patient Registration Form"):
        frappe.throw(_("Patient Registration Form DocType was not found."))

    existing = _latest_welfare_registration(patient)
    if existing:
        return {"name": existing.get("registration"), "created": 0, "route": f"/app/patient-registration-form/{existing.get('registration')}"}

    ctx = get_patient_billing_context(patient=patient)
    snap = get_patient_snapshot(patient=patient)
    doc = frappe.new_doc("Patient Registration Form")

    _set_if_field(doc, PRF_PATIENT_FIELDS, patient)
    _set_if_field(doc, PRF_MR_FIELDS, snap.get("mr_number"))
    _set_if_field(doc, PRF_NAME_FIELDS, snap.get("patient_name"))
    _set_if_field(doc, ["custom_patient_customer", "patient_customer"], ctx.get("patient_customer"))
    _set_if_field(doc, ["custom_billing_type", "billing_type", "patient_billing_type"], "Welfare")
    _set_if_field(doc, ["custom_kpws_welfare_type", "custom_assistance_type", "assistance_type", "purpose"], "Donation")
    _set_if_field(doc, ["custom_kpws_welfare_percentage", "custom_coverage_percentage", "coverage_percentage", "discount_value"], 0)
    _set_if_field(doc, ["custom_review_status", "review_status", "status"], "Pending Admin")

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "created": 1, "route": f"/app/patient-registration-form/{doc.name}"}


def validate_patient_clean(doc, method=None):
    billing_type = _patient_billing_type(doc.name, getattr(doc, "customer", None))
    panel_customer = None
    for f in PATIENT_PANEL_FIELDS:
        if doc.meta.get_field(f) and doc.get(f):
            panel_customer = _find_customer(doc.get(f), panel_only=True)
            if not panel_customer:
                frappe.throw(_("Selected panel must be an existing Customer with Is Panel checked."))
            doc.set(f, panel_customer)
            break

    if billing_type == "Panel" and not panel_customer:
        return  # KPWS: panel validation disabled; patient type can be changed freely

    if panel_customer and getattr(doc, "customer", None) == panel_customer:
        frappe.throw(_("Do not use the panel master as Patient Customer. Patient.customer must remain the patient/customer record; select panel separately."))


def prevent_panel_customer_creation_by_reception(doc, method=None):
    is_panel = _has_field("Customer", "custom_is_panel") and cint(getattr(doc, "custom_is_panel", 0)) == 1
    if not is_panel:
        return
    if _roles_allowed(ALLOWED_PANEL_ROLES):
        return
    frappe.throw(_("Panel customers can only be created by Administrator/manager roles. Reception must select an existing panel customer."))


def _ensure_custom_field(dt, fieldname, label, fieldtype, insert_after=None, options=None, depends_on=None, read_only=0, hidden=0, default=None):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    values = {
        "label": label,
        "fieldtype": fieldtype,
        "insert_after": insert_after,
        "options": options,
        "depends_on": depends_on,
        "read_only": read_only,
        "hidden": hidden,
        "default": default,
        "print_hide": 1 if hidden else 0,
    }
    if name:
        for k, v in values.items():
            if v is not None:
                frappe.db.set_value("Custom Field", name, k, v)
        return name
    doc = frappe.new_doc("Custom Field")
    doc.dt = dt
    doc.fieldname = fieldname
    for k, v in values.items():
        if v is not None:
            doc.set(k, v)
    doc.insert(ignore_permissions=True)
    return doc.name


def _hide_custom_field(dt, fieldname):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    if not name:
        return False
    for k, v in {"hidden": 1, "print_hide": 1, "in_list_view": 0, "in_standard_filter": 0, "reqd": 0, "read_only": 1}.items():
        try:
            frappe.db.set_value("Custom Field", name, k, v)
        except Exception:
            pass
    return True


def _unhide_custom_field(dt, fieldname, label=None):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    if not name:
        return False
    updates = {"hidden": 0, "print_hide": 0, "read_only": 0}
    if label:
        updates["label"] = label
    for k, v in updates.items():
        frappe.db.set_value("Custom Field", name, k, v)
    return True


def _disable_old_client_scripts():
    if not frappe.db.exists("DocType", "Client Script"):
        return []
    disabled = []
    targets = {"Patient", "Patient Registration Form", "Sales Invoice"}
    keywords = ["kpws", "welfare", "panel", "billing", "patient"]
    rows = frappe.get_all("Client Script", filters={"dt": ["in", list(targets)]}, fields=["name", "dt", "script", "enabled"])
    for r in rows:
        hay = f"{r.name} {r.dt} {r.script or ''}".lower()
        if "kpws clean" in hay:
            continue
        if any(k in hay for k in keywords):
            try:
                frappe.db.set_value("Client Script", r.name, "enabled", 0)
                disabled.append(r.name)
            except Exception:
                pass
    return disabled


@frappe.whitelist()
def install_clean_flow():
    """Run after deploying clean JS/hooks. Soft-disables old messy metadata and creates minimal clean fields."""
    if not _has_field("Customer", "custom_is_panel"):
        _ensure_custom_field("Customer", "custom_is_panel", "Is Panel", "Check", insert_after="customer_group", default=0)

    _ensure_custom_field("Sales Invoice", "custom_kpws_mr_number", "MR Number", "Data", insert_after="customer")
    _ensure_custom_field("Sales Invoice", "custom_is_walkin", "Walk-in Patient", "Check", insert_after="custom_kpws_mr_number", default=0)
    _ensure_custom_field("Sales Invoice", "custom_walkin_patient_name", "Walk-in Patient Name", "Data", insert_after="custom_is_walkin", depends_on="eval:doc.custom_is_walkin")
    _ensure_custom_field("Sales Invoice", "custom_walkin_mr_number", "Walk-in MR Number", "Data", insert_after="custom_walkin_patient_name", depends_on="eval:doc.custom_is_walkin")

    if frappe.db.exists("DocType", "Patient Registration Form"):
        _ensure_custom_field("Patient Registration Form", "custom_kpws_patient_snapshot_html", "Patient Information", "HTML")
        _ensure_custom_field("Patient Registration Form", "custom_kpws_welfare_type", "Purpose", "Select", insert_after="custom_kpws_patient_snapshot_html", options="Zakat\nDonation", default="Donation")
        _ensure_custom_field("Patient Registration Form", "custom_kpws_welfare_percentage", "Percentage", "Percent", insert_after="custom_kpws_welfare_type", default=0)
        _ensure_custom_field("Patient Registration Form", "custom_kpws_assigned_panel_customer", "Linked Panel", "Link", insert_after="custom_kpws_welfare_percentage", options="Customer")
        _ensure_custom_field("Patient Registration Form", "custom_kpws_admin_notes", "Admin Remarks", "Small Text", insert_after="custom_kpws_assigned_panel_customer")

    hide_map = {
        "Patient": [
            "custom_patient_billing_type", "custom_panel_customer", "custom_latest_welfare_registration",
            "custom_welfare_type", "custom_welfare_percentage", "custom_kpws_assigned_panel_customer",
        ],
        "Sales Invoice": [
            "custom_patient", "custom_kpws_billing_type", "custom_kpws_panel_customer",
            "custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage",
            "custom_panel_customer", "custom_welfare_registration", "custom_welfare_type", "custom_welfare_percentage",
        ],
        "Patient Registration Form": [
            "custom_patient", "custom_mr_number", "custom_patient_customer", "custom_billing_type",
            "custom_assistance_type", "custom_coverage_percentage", "custom_panel_customer",
            "custom_review_status", "custom_approval_remarks", "custom_panel", "custom_assigned_panel",
        ],
    }
    hidden = []
    for dt, fields in hide_map.items():
        for f in fields:
            if _hide_custom_field(dt, f):
                hidden.append(f"{dt}.{f}")

    for f in ["custom_kpws_mr_number", "custom_is_walkin", "custom_walkin_patient_name", "custom_walkin_mr_number"]:
        _unhide_custom_field("Sales Invoice", f)
    if frappe.db.exists("DocType", "Patient Registration Form"):
        for f in ["custom_kpws_patient_snapshot_html", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage", "custom_kpws_assigned_panel_customer", "custom_kpws_admin_notes"]:
            _unhide_custom_field("Patient Registration Form", f)

    disabled_scripts = _disable_old_client_scripts()
    frappe.clear_cache()
    frappe.db.commit()
    return {"status": "success", "disabled_client_scripts": disabled_scripts, "hidden_custom_fields": hidden}


def autoname_patient_kpws(doc, method=None):
    """Force Patient numbering as KPWS-#### for new patients."""
    # This hook runs after Healthcare's own autoname. We intentionally override it.
    doc.naming_series = "KPWS-"
    doc.name = make_autoname("KPWS-.####", doc=doc)
