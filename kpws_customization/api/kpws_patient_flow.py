import frappe
from frappe import _
from frappe.utils import flt, cint

ALLOWED_PANEL_ROLES = {"Administrator", "System Manager", "Accounts Manager", "Healthcare Manager"}

PATIENT_BILLING_FIELDS = [
    "custom_patient_billing_type", "patient_billing_type", "billing_type", "custom_billing_type", "customer_group"
]
PATIENT_PANEL_FIELDS = [
    "custom_panel_customer", "panel_customer", "custom_panel", "panel", "custom_panel_name", "panel_name"
]
PATIENT_MR_FIELDS = [
    "custom_reference_number", "reference_number", "mr_number", "custom_mr_number", "custom_mr_no", "uid"
]


def _has_field(doctype, fieldname):
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _get_meta_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).get_field(fieldname)
    except Exception:
        return None


def _set_if_field(doc, fieldnames, value):
    if not isinstance(fieldnames, (list, tuple)):
        fieldnames = [fieldnames]
    for fieldname in fieldnames:
        if doc.meta.get_field(fieldname):
            doc.set(fieldname, value)
            return fieldname
    return None


def _first_value(doctype, name, fieldnames):
    for fieldname in fieldnames:
        if _has_field(doctype, fieldname):
            value = frappe.db.get_value(doctype, name, fieldname)
            if value not in (None, ""):
                return value
    return None


def _is_panel_customer(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False
    if _has_field("Customer", "custom_is_panel") and cint(frappe.db.get_value("Customer", customer, "custom_is_panel")):
        return True
    group = (frappe.db.get_value("Customer", customer, "customer_group") or "").lower()
    return "panel" in group


def _panel_condition_sql(txt=""):
    txt = f"%{txt or ''}%"
    if _has_field("Customer", "custom_is_panel"):
        return "(IFNULL(custom_is_panel,0)=1 OR customer_group LIKE '%Panel%')", txt
    return "(customer_group LIKE '%Panel%')", txt


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    txt = txt or ""
    like_txt = "%" + txt + "%"
    panel_like = "%Panel%"

    has_is_panel = _has_field("Customer", "custom_is_panel")

    if has_is_panel:
        panel_condition = "(IFNULL(custom_is_panel, 0) = 1 OR customer_group LIKE %(panel_like)s)"
    else:
        panel_condition = "(customer_group LIKE %(panel_like)s)"

    return frappe.db.sql(
        f"""
        SELECT name, customer_name, customer_group
        FROM `tabCustomer`
        WHERE disabled = 0
          AND {panel_condition}
          AND (
                name LIKE %(like_txt)s
             OR customer_name LIKE %(like_txt)s
             OR customer_group LIKE %(like_txt)s
          )
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "like_txt": like_txt,
            "panel_like": panel_like,
            "start": cint(start or 0),
            "page_len": cint(page_len or 20),
        },
    )


def _resolve_patient(patient=None, mr_number=None, customer=None):
    patient = (patient or "").strip()
    mr_number = (mr_number or "").strip()
    customer = (customer or "").strip()

    if patient:
        if frappe.db.exists("Patient", patient):
            return patient
        for fieldname in ["patient_name"] + PATIENT_MR_FIELDS:
            if _has_field("Patient", fieldname):
                found = frappe.db.get_value("Patient", {fieldname: patient}, "name")
                if found:
                    return found

    if mr_number:
        for fieldname in PATIENT_MR_FIELDS:
            if _has_field("Patient", fieldname):
                found = frappe.db.get_value("Patient", {fieldname: mr_number}, "name")
                if found:
                    return found

    if customer and _has_field("Patient", "customer"):
        found = frappe.db.get_value("Patient", {"customer": customer}, "name")
        if found:
            return found

    return None


def _customer_group_key(customer):
    if not customer:
        return ""
    group = (frappe.db.get_value("Customer", customer, "customer_group") or "").lower()
    if _is_panel_customer(customer) or "panel" in group:
        return "Panel"
    if "welfare" in group:
        return "Welfare"
    if "cash" in group:
        return "Cash"
    return ""


def _normalize_billing_type(value):
    text = str(value or "").strip().lower()
    if "panel" in text:
        return "Panel"
    if "welfare" in text or "zakat" in text or "donation" in text:
        return "Welfare"
    if "cash" in text:
        return "Cash"
    return ""


def _get_patient_customer(patient_id):
    if patient_id and _has_field("Patient", "customer"):
        customer = frappe.db.get_value("Patient", patient_id, "customer")
        if customer and frappe.db.exists("Customer", customer):
            return customer
    return None


def _get_patient_mr(patient_id):
    if not patient_id:
        return ""
    return _first_value("Patient", patient_id, PATIENT_MR_FIELDS) or patient_id


def _find_customer(value, panel_only=False):
    if not value:
        return None
    if frappe.db.exists("Customer", value):
        customer = value
    else:
        filters = {"customer_name": value}
        if panel_only and _has_field("Customer", "custom_is_panel"):
            filters["custom_is_panel"] = 1
        customer = frappe.db.get_value("Customer", filters, "name")
    if panel_only and customer and not _is_panel_customer(customer):
        return None
    return customer


def _get_patient_panel_customer(patient_id):
    if not patient_id:
        return None
    for fieldname in PATIENT_PANEL_FIELDS:
        if not _has_field("Patient", fieldname):
            continue
        value = frappe.db.get_value("Patient", patient_id, fieldname)
        customer = _find_customer(value, panel_only=True)
        if customer:
            return customer
    return None



def _get_patient_billing_type(patient_id, patient_customer=None, panel_customer=None):
    # Explicit patient billing type must win. Panel customer alone should not convert Welfare/Cash into Panel.
    for fieldname in PATIENT_BILLING_FIELDS:
        if _has_field("Patient", fieldname):
            val = frappe.db.get_value("Patient", patient_id, fieldname)
            billing = _normalize_billing_type(val)
            if billing:
                return billing

    # Backward compatibility: old records with panel selected but no billing type become Panel.
    if panel_customer:
        return "Panel"

    return _customer_group_key(patient_customer) or "Cash"
def _get_pos_profile(billing_type):
    key = (billing_type or "Cash").lower()
    preferred = {
        "cash": ["Cash", "KPWS Cash", "Cash - KPWS"],
        "welfare": ["Welfare", "KPWS Welfare", "Welfare - KPWS"],
        "panel": ["Panel", "KPWS Panel", "Panel - KPWS"],
    }.get(key, [])
    for name in preferred:
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


def _get_mode_of_payment(candidates):
    for mode in candidates:
        if frappe.db.exists("Mode of Payment", mode):
            return mode
    return candidates[0] if candidates else ""



def _latest_welfare_registration(patient_id):
    if not patient_id or not frappe.db.exists("DocType", "Patient Registration Form"):
        return None

    meta = frappe.get_meta("Patient Registration Form")
    patient_name = frappe.db.get_value("Patient", patient_id, "patient_name") or ""
    mr_number = _first_value("Patient", patient_id, PATIENT_MR_FIELDS) or ""

    search_filters = []

    # Prefer direct Patient link fields where available.
    for f in ["patient", "custom_patient", "patient_id", "kpws_patient"]:
        if meta.get_field(f):
            search_filters.append({f: patient_id})

    # Old Patient Registration Form has MR No and Patient Name fields.
    for f in ["mr_no", "mr_number", "custom_mr_number", "custom_reference_number", "reference_number"]:
        if mr_number and meta.get_field(f):
            search_filters.append({f: mr_number})

    for f in ["patient_full_name", "patient_name", "custom_patient_name", "full_name", "patient_full_name"]:
        if patient_name and meta.get_field(f):
            search_filters.append({f: patient_name})

    if not search_filters:
        return None

    fields = ["name", "workflow_state", "docstatus", "modified"]
    candidate_fields = [
        "discount_type", "discount_value", "purpose",
        "custom_assistance_type", "assistance_type", "welfare_type",
        "custom_coverage_percentage", "coverage_percentage",
        "custom_panel_customer", "panel_customer", "custom_panel", "panel",
    ]
    for f in candidate_fields:
        if meta.get_field(f) and f not in fields:
            fields.append(f)

    rows = []
    seen = set()
    for filters in search_filters:
        filters = dict(filters)
        if meta.get_field("workflow_state"):
            filters["workflow_state"] = ["in", ["Approved", "Pending Admin", "Submitted for Review"]]
        try:
            found = frappe.get_all("Patient Registration Form", filters=filters, fields=fields, order_by="modified desc", limit=5)
        except Exception:
            found = []
        for r in found:
            if r.name not in seen:
                seen.add(r.name)
                rows.append(r)

    if not rows:
        return None

    # Prefer Approved, otherwise latest pending/submitted.
    rows.sort(key=lambda r: (0 if str(r.get("workflow_state") or "").lower() == "approved" else 1, str(r.get("modified") or "")), reverse=False)
    r = rows[0]

    assistance_type = (
        r.get("custom_assistance_type") or r.get("assistance_type") or r.get("welfare_type") or r.get("purpose") or r.get("discount_type") or "Donation"
    )

    pct = r.get("custom_coverage_percentage")
    if pct in (None, ""):
        pct = r.get("coverage_percentage")
    if pct in (None, ""):
        pct = r.get("discount_value") or 0

    panel_customer = None
    for f in ["custom_panel_customer", "panel_customer", "custom_panel", "panel"]:
        panel_customer = _find_customer(r.get(f), panel_only=True)
        if panel_customer:
            break

    return {
        "registration": r.name,
        "workflow_state": r.get("workflow_state") or "",
        "assistance_type": "Zakat" if "zakat" in str(assistance_type).lower() else "Donation",
        "coverage_percentage": flt(pct),
        "panel_customer": panel_customer or "",
        "mode_of_payment": _get_mode_of_payment(["Zakat"] if "zakat" in str(assistance_type).lower() else ["Donation"]),
    }
@frappe.whitelist()
def get_patient_billing_context(patient=None, mr_number=None, customer=None):
    patient_id = _resolve_patient(patient=patient, mr_number=mr_number, customer=customer)
    if not patient_id:
        return {}

    patient_customer = _get_patient_customer(patient_id)
    panel_customer = _get_patient_panel_customer(patient_id)
    billing_type = _get_patient_billing_type(patient_id, patient_customer, panel_customer)
    welfare = _latest_welfare_registration(patient_id) if billing_type == "Welfare" else None

    # Administrator can link a panel on the welfare registration. If available, it becomes panel reference, not patient.customer.
    if welfare and welfare.get("panel_customer") and not panel_customer:
        panel_customer = welfare.get("panel_customer")

    invoice_customer = panel_customer if billing_type == "Panel" and panel_customer else patient_customer
    if not invoice_customer and customer and frappe.db.exists("Customer", customer):
        invoice_customer = customer

    patient_name = frappe.db.get_value("Patient", patient_id, "patient_name") or patient_id
    customer_group = frappe.db.get_value("Customer", invoice_customer, "customer_group") if invoice_customer else ""

    return {
        "patient": patient_id,
        "patient_name": patient_name,
        "mr_number": _get_patient_mr(patient_id),
        "patient_customer": patient_customer or "",
        "panel_customer": panel_customer or "",
        "panel_customer_name": frappe.db.get_value("Customer", panel_customer, "customer_name") if panel_customer else "",
        "customer": invoice_customer or "",
        "customer_group": customer_group or "",
        "billing_type": billing_type,
        "pos_profile": _get_pos_profile(billing_type),
        "selling_price_list": _get_price_list(billing_type),
        "welfare": welfare,
        "cash_mode_of_payment": _get_mode_of_payment(["Cash"]),
        "card_mode_of_payment": _get_mode_of_payment(["Credit Card", "Card", "Bank Card"]),
    }


@frappe.whitelist()
def get_sales_invoice_context(patient=None, mr_number=None, customer=None, is_walkin=0):
    if cint(is_walkin):
        walkin_customer = None
        for c in ["Walk-in Cash Customer - KPWS", "Walk-in Customer", "Cash Customer"]:
            if frappe.db.exists("Customer", c):
                walkin_customer = c
                break
        return {
            "patient": "",
            "billing_type": "Cash",
            "customer": walkin_customer or customer or "",
            "patient_customer": "",
            "panel_customer": "",
            "pos_profile": _get_pos_profile("Cash"),
            "selling_price_list": _get_price_list("Cash"),
            "welfare": None,
            "cash_mode_of_payment": _get_mode_of_payment(["Cash"]),
        }
    return get_patient_billing_context(patient=patient, mr_number=mr_number, customer=customer)


@frappe.whitelist()

@frappe.whitelist()
def create_welfare_registration(patient):
    if not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient not found."))
    if not frappe.db.exists("DocType", "Patient Registration Form"):
        frappe.throw(_("Patient Registration Form DocType was not found."))

    ctx = get_patient_billing_context(patient=patient)
    doc = frappe.new_doc("Patient Registration Form")
    meta = frappe.get_meta("Patient Registration Form")

    # Set direct Patient link if available.
    _set_if_field(doc, ["custom_patient", "patient", "patient_id", "kpws_patient"], patient)

    # Set old required fields used by the current KPWS form.
    _set_if_field(doc, ["mr_no", "custom_mr_number", "mr_number", "custom_reference_number", "reference_number"], ctx.get("mr_number"))
    _set_if_field(doc, ["patient_full_name", "patient_name", "custom_patient_name", "full_name"], ctx.get("patient_name") or patient)

    # Helpful read-only/reference fields.
    _set_if_field(doc, ["custom_patient_customer", "patient_customer"], ctx.get("patient_customer"))
    _set_if_field(doc, ["custom_billing_type", "billing_type", "patient_billing_type"], "Welfare")
    _set_if_field(doc, ["custom_panel_customer", "panel_customer", "custom_panel", "panel"], ctx.get("panel_customer"))
    _set_if_field(doc, ["custom_review_status", "review_status", "status"], "Submitted for Review")

    # Keep old discount fields blank for Administrator review.
    if meta.get_field("discount_type") and not doc.get("discount_type"):
        doc.discount_type = "Percentage"
    if meta.get_field("discount_value") and not doc.get("discount_value"):
        doc.discount_value = 0

    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "doctype": doc.doctype, "route": f"/app/patient-registration-form/{doc.name}"}
@frappe.whitelist()
def create_panel_customer(panel_name, contact_no=None, email_id=None):
    panel_name = (panel_name or "").strip()
    if not panel_name:
        frappe.throw(_("Panel name is required."))

    roles = set(frappe.get_roles(frappe.session.user)) | {frappe.session.user}
    if not roles.intersection(ALLOWED_PANEL_ROLES):
        frappe.throw(_("Only Administrator or manager roles can create a new panel customer."))

    existing = frappe.db.get_value("Customer", {"customer_name": panel_name}, "name")
    if existing:
        if _has_field("Customer", "custom_is_panel") and not cint(frappe.db.get_value("Customer", existing, "custom_is_panel")):
            frappe.db.set_value("Customer", existing, "custom_is_panel", 1)
        return {"name": existing, "created": 0}

    customer_group = "Panel" if frappe.db.exists("Customer Group", "Panel") else frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    territory = "All Territories" if frappe.db.exists("Territory", "All Territories") else frappe.db.get_value("Territory", {"is_group": 0}, "name")

    doc = frappe.new_doc("Customer")
    doc.customer_name = panel_name
    doc.customer_type = "Company"
    doc.customer_group = customer_group
    doc.territory = territory
    if _has_field("Customer", "custom_is_panel"):
        doc.custom_is_panel = 1
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "created": 1}


def validate_patient_panel_link(doc, method=None):
    panel_customer = None
    for f in PATIENT_PANEL_FIELDS:
        if doc.meta.get_field(f):
            panel_customer = _find_customer(doc.get(f), panel_only=True)
            if doc.get(f) and not panel_customer:
                frappe.throw(_("Selected panel must be an existing Customer with Is Panel Customer checked."))
            if panel_customer:
                doc.set(f, panel_customer)
                break

    # Do not allow old scripts to overwrite the Patient.customer field with a panel master.
    if panel_customer and getattr(doc, "customer", None) == panel_customer:
        frappe.throw(_("Do not save the Panel Customer in Patient.customer. Use the Panel Customer field. Patient.customer must remain the patient's own customer."))


def prevent_panel_customer_creation_by_reception(doc, method=None):
    is_panel = False
    if _has_field("Customer", "custom_is_panel"):
        is_panel = cint(getattr(doc, "custom_is_panel", 0)) == 1
    is_panel = is_panel or "panel" in str(getattr(doc, "customer_group", "") or "").lower()
    if not is_panel:
        return

    roles = set(frappe.get_roles(frappe.session.user)) | {frappe.session.user}
    if roles.intersection(ALLOWED_PANEL_ROLES):
        return

    frappe.throw(_("Panel customers can only be created by Administrator/manager roles. Reception must select an existing panel customer."))
