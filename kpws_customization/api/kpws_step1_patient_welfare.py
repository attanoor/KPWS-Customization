import frappe
from frappe import _
from frappe.utils import nowdate, flt, cint

ALLOWED_BILLING_TYPES = ["Cash", "Welfare", "Panel"]
ADMIN_ROLES = {"Administrator", "System Manager", "Healthcare Manager", "Welfare Manager"}


def _meta_has(doctype, fieldname):
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _set_if_has(doc, fieldname, value, overwrite=True):
    if doc.meta.get_field(fieldname):
        if overwrite or not doc.get(fieldname):
            doc.set(fieldname, value)


def _get_roles():
    try:
        return set(frappe.get_roles(frappe.session.user))
    except Exception:
        return set()


def _is_admin_user():
    return frappe.session.user == "Administrator" or bool(_get_roles().intersection(ADMIN_ROLES))


def _require_admin():
    if not _is_admin_user():
        frappe.throw(_("Only Administrator / Manager can perform this action."), frappe.PermissionError)


def _get_patient_doc(patient):
    if not patient:
        return None

    if frappe.db.exists("Patient", patient):
        return frappe.get_doc("Patient", patient)

    found = frappe.db.get_value("Patient", {"patient_name": patient}, "name")
    if found:
        return frappe.get_doc("Patient", found)

    return None


def _patient_mr(patient_doc):
    for f in ["custom_reference_number", "mr_no", "mr_number", "ref_no", "old_kpws_number"]:
        if patient_doc.meta.get_field(f) and patient_doc.get(f):
            return patient_doc.get(f)

    return patient_doc.name


def _patient_cnic(patient_doc):
    for f in ["cnic_number", "cnic", "custom_cnic", "uid", "national_id"]:
        if patient_doc.meta.get_field(f) and patient_doc.get(f):
            return patient_doc.get(f)

    return None


def _patient_mobile(patient_doc):
    for f in ["mobile", "phone", "mobile_no", "contact_no"]:
        if patient_doc.meta.get_field(f) and patient_doc.get(f):
            return patient_doc.get(f)

    return None


def _get_patient_panel_customer(patient_doc):
    for f in ["panel_name", "custom_panel_customer"]:
        if patient_doc.meta.get_field(f) and patient_doc.get(f):
            return patient_doc.get(f)

    return None


def _is_panel_customer(customer):
    if not customer:
        return False

    if not frappe.db.exists("Customer", customer):
        return False

    if _meta_has("Customer", "custom_is_panel"):
        return cint(frappe.db.get_value("Customer", customer, "custom_is_panel")) == 1

    return False


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    """
    Strict panel lookup.
    Only Customer records where custom_is_panel = 1 will show.
    """
    txt = txt or ""

    if not _meta_has("Customer", "custom_is_panel"):
        return []

    return frappe.db.sql(
        """
        SELECT name, customer_name, customer_group
        FROM `tabCustomer`
        WHERE IFNULL(disabled, 0) = 0
          AND IFNULL(custom_is_panel, 0) = 1
          AND (
                name LIKE %(txt)s
             OR customer_name LIKE %(txt)s
             OR customer_group LIKE %(txt)s
          )
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": "%" + txt + "%",
            "start": cint(start or 0),
            "page_len": cint(page_len or 20),
        },
    )


def validate_and_sync_patient(doc, method=None):
    """
    Patient save rule:
    - Patient Billing Type is the main visible field.
    - Old Panel Group / customer_group is synced internally for compatibility.
    - No Customer is created here.
    """
    billing_type = doc.get("custom_patient_billing_type") or doc.get("customer_group") or "Cash"

    if billing_type not in ALLOWED_BILLING_TYPES:
        frappe.throw(_("Patient Billing Type must be Cash, Welfare or Panel."))

    if doc.meta.get_field("custom_patient_billing_type"):
        doc.custom_patient_billing_type = billing_type

    if doc.meta.get_field("customer_group"):
        doc.customer_group = billing_type

    panel_customer = doc.get("panel_name") or doc.get("custom_panel_customer")

    if billing_type == "Panel":
        if not panel_customer:
            frappe.throw(_("Please select Panel Name for Panel patient."))

        if not _is_panel_customer(panel_customer):
            frappe.throw(_("Panel Name must be a Customer where Is Panel is checked."))

        if doc.meta.get_field("panel_name"):
            doc.panel_name = panel_customer

        if doc.meta.get_field("custom_panel_customer"):
            doc.custom_panel_customer = panel_customer

    elif billing_type == "Cash":
        if doc.meta.get_field("panel_name"):
            doc.panel_name = None

        if doc.meta.get_field("custom_panel_customer"):
            doc.custom_panel_customer = None

    # Welfare may later receive panel assignment from Welfare Registration,
    # so we do not clear panel fields automatically for Welfare.


def sync_prf_patient_fields(doc, method=None):
    """
    Auto-fill Patient Registration Form / Welfare Registration from Patient.
    Uses existing fields:
    - patient_name
    - mr_no
    - patient_full_name
    - cnic
    - contact_no
    - address
    """
    patient = doc.get("patient_name") or doc.get("custom_patient")
    patient_doc = _get_patient_doc(patient)

    if not patient_doc:
        return

    mr = _patient_mr(patient_doc)
    patient_full_name = patient_doc.get("patient_name") or patient_doc.name
    patient_customer = patient_doc.get("customer")
    panel_customer = _get_patient_panel_customer(patient_doc)

    _set_if_has(doc, "patient_name", patient_doc.name, overwrite=True)
    _set_if_has(doc, "custom_patient", patient_doc.name, overwrite=True)
    _set_if_has(doc, "mr_no", mr, overwrite=True)
    _set_if_has(doc, "custom_mr_number", mr, overwrite=True)
    _set_if_has(doc, "patient_full_name", patient_full_name, overwrite=True)
    _set_if_has(doc, "actual_patient_name", patient_full_name, overwrite=True)
    _set_if_has(doc, "custom_patient_customer", patient_customer, overwrite=True)
    _set_if_has(doc, "customer", patient_customer, overwrite=True)
    _set_if_has(doc, "custom_billing_type", "Welfare", overwrite=True)

    if panel_customer:
        for f in ["custom_assigned_panel", "custom_panel_customer", "custom_kpws_assigned_panel_customer"]:
            _set_if_has(doc, f, panel_customer, overwrite=False)

    # Fill contact details only when empty, so Administrator can review/update.
    _set_if_has(doc, "cnic", _patient_cnic(patient_doc), overwrite=False)
    _set_if_has(doc, "contact_no", _patient_mobile(patient_doc), overwrite=False)
    _set_if_has(doc, "address", patient_doc.get("patient_details"), overwrite=False)


@frappe.whitelist()
def create_or_open_welfare_registration(patient):
    patient_doc = _get_patient_doc(patient)

    if not patient_doc:
        frappe.throw(_("Patient not found."))

    existing = frappe.get_all(
        "Patient Registration Form",
        filters={
            "patient_name": patient_doc.name,
            "docstatus": ["<", 2],
        },
        fields=["name", "workflow_state", "modified"],
        order_by="modified desc",
        limit=1,
    )

    if existing:
        return {
            "created": 0,
            "name": existing[0].name,
            "workflow_state": existing[0].workflow_state,
        }

    doc = frappe.new_doc("Patient Registration Form")
    doc.patient_name = patient_doc.name

    if doc.meta.get_field("date"):
        doc.date = nowdate()

    if doc.meta.get_field("workflow_state"):
        doc.workflow_state = "Draft"

    sync_prf_patient_fields(doc)
    doc.insert(ignore_permissions=True)

    updates = {}

    if patient_doc.meta.get_field("custom_latest_welfare_registration"):
        updates["custom_latest_welfare_registration"] = doc.name

    if patient_doc.meta.get_field("custom_patient_billing_type"):
        updates["custom_patient_billing_type"] = "Welfare"

    if patient_doc.meta.get_field("customer_group"):
        updates["customer_group"] = "Welfare"

    if updates:
        frappe.db.set_value("Patient", patient_doc.name, updates, update_modified=False)

    frappe.db.commit()

    return {
        "created": 1,
        "name": doc.name,
        "workflow_state": doc.get("workflow_state"),
    }


@frappe.whitelist()
def submit_welfare_for_review(prf_name):
    doc = frappe.get_doc("Patient Registration Form", prf_name)

    sync_prf_patient_fields(doc)

    if doc.meta.get_field("workflow_state"):
        doc.workflow_state = "Pending Admin"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "name": doc.name,
        "workflow_state": doc.get("workflow_state"),
    }


@frappe.whitelist()
def create_panel_from_welfare_form(panel_name, contact_person=None, phone=None, email=None, default_mode_of_payment=None):
    _require_admin()

    panel_name = (panel_name or "").strip()

    if not panel_name:
        frappe.throw(_("Panel Name is required."))

    customer = None

    # Prefer KPWS Panel master. Existing KPWS Panel server script syncs/creates Customer.
    if frappe.db.exists("DocType", "KPWS Panel"):
        existing = frappe.db.get_value("KPWS Panel", {"panel_name": panel_name}, "name")
        panel = frappe.get_doc("KPWS Panel", existing) if existing else frappe.new_doc("KPWS Panel")

        panel.panel_name = panel_name

        if panel.meta.get_field("contact_person"):
            panel.contact_person = contact_person

        if panel.meta.get_field("phone"):
            panel.phone = phone

        if panel.meta.get_field("email"):
            panel.email = email

        if panel.meta.get_field("default_mode_of_payment"):
            panel.default_mode_of_payment = default_mode_of_payment

        if panel.meta.get_field("is_active"):
            panel.is_active = 1

        if panel.is_new():
            panel.insert(ignore_permissions=True)
        else:
            panel.save(ignore_permissions=True)

        panel.reload()
        customer = panel.get("customer")

    if not customer:
        customer = frappe.db.get_value("Customer", {"customer_name": panel_name}, "name")

        if not customer:
            c = frappe.new_doc("Customer")
            c.customer_name = panel_name

            if c.meta.get_field("customer_group"):
                c.customer_group = "Panel"

            if c.meta.get_field("custom_is_panel"):
                c.custom_is_panel = 1

            if c.meta.get_field("mobile_no") and phone:
                c.mobile_no = phone

            if c.meta.get_field("email_id") and email:
                c.email_id = email

            c.insert(ignore_permissions=True, ignore_mandatory=True)
            customer = c.name

    if customer and _meta_has("Customer", "custom_is_panel"):
        frappe.db.set_value("Customer", customer, "custom_is_panel", 1, update_modified=False)

    frappe.db.commit()

    return {
        "customer": customer,
        "panel_name": panel_name,
    }


@frappe.whitelist()
def approve_welfare_registration(prf_name):
    _require_admin()

    doc = frappe.get_doc("Patient Registration Form", prf_name)
    sync_prf_patient_fields(doc)

    if not doc.get("discount_type"):
        frappe.throw(_("Please set Discount Type."))

    if flt(doc.get("discount_value")) <= 0:
        frappe.throw(_("Please set Discount Value / Percentage."))

    if not doc.get("purpose"):
        frappe.throw(_("Please select Purpose: Zakat or Donation."))

    assigned_panel = None

    for f in ["custom_kpws_assigned_panel_customer", "custom_assigned_panel", "custom_panel_customer", "custom_panel"]:
        if doc.meta.get_field(f) and doc.get(f):
            candidate = doc.get(f)
            if frappe.db.exists("Customer", candidate):
                assigned_panel = candidate
                break

    if assigned_panel and not _is_panel_customer(assigned_panel):
        frappe.throw(_("Assigned Panel must be a Customer where Is Panel is checked."))

    if doc.meta.get_field("workflow_state"):
        doc.workflow_state = "Approved"

    doc.save(ignore_permissions=True)

    patient_doc = _get_patient_doc(doc.get("patient_name") or doc.get("custom_patient"))

    if patient_doc:
        updates = {}

        if patient_doc.meta.get_field("custom_patient_billing_type"):
            updates["custom_patient_billing_type"] = "Welfare"

        if patient_doc.meta.get_field("customer_group"):
            updates["customer_group"] = "Welfare"

        if patient_doc.meta.get_field("custom_latest_welfare_registration"):
            updates["custom_latest_welfare_registration"] = doc.name

        if patient_doc.meta.get_field("custom_welfare_type"):
            updates["custom_welfare_type"] = doc.get("purpose")

        if patient_doc.meta.get_field("custom_welfare_percentage"):
            updates["custom_welfare_percentage"] = flt(doc.get("discount_value"))

        if assigned_panel:
            if patient_doc.meta.get_field("panel_name"):
                updates["panel_name"] = assigned_panel

            if patient_doc.meta.get_field("custom_panel_customer"):
                updates["custom_panel_customer"] = assigned_panel

        if updates:
            frappe.db.set_value("Patient", patient_doc.name, updates, update_modified=True)

    frappe.db.commit()

    return {
        "name": doc.name,
        "workflow_state": doc.get("workflow_state"),
    }

# KPWS CORE SAFE STRICT PANEL LOOKUP OVERRIDE
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    """
    Strict Panel lookup:
    Only Customers where custom_is_panel = 1 should appear.
    This keeps ERPNext Customer core intact and only changes KPWS panel selection.
    """
    from frappe.utils import cint

    txt = txt or ""

    try:
        if not frappe.get_meta("Customer").get_field("custom_is_panel"):
            return []
    except Exception:
        return []

    return frappe.db.sql(
        """
        SELECT
            name,
            customer_name,
            customer_group
        FROM `tabCustomer`
        WHERE IFNULL(disabled, 0) = 0
          AND IFNULL(custom_is_panel, 0) = 1
          AND (
                name LIKE %(txt)s
             OR customer_name LIKE %(txt)s
             OR customer_group LIKE %(txt)s
          )
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": "%" + txt + "%",
            "start": cint(start or 0),
            "page_len": cint(page_len or 20),
        },
    )

# KPWS CLEAN STRICT PANEL LOOKUP OVERRIDE
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    """
    Panel lookup for KPWS:
    show only Customer where custom_is_panel = 1.
    Does not alter ERPNext Customer core.
    """
    from frappe.utils import cint

    txt = txt or ""

    try:
        if not frappe.get_meta("Customer").get_field("custom_is_panel"):
            return []
    except Exception:
        return []

    return frappe.db.sql(
        """
        SELECT
            name,
            customer_name,
            customer_group
        FROM `tabCustomer`
        WHERE IFNULL(disabled, 0) = 0
          AND IFNULL(custom_is_panel, 0) = 1
          AND (
                name LIKE %(txt)s
             OR customer_name LIKE %(txt)s
             OR customer_group LIKE %(txt)s
          )
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": "%" + txt + "%",
            "start": cint(start or 0),
            "page_len": cint(page_len or 20),
        },
    )

# KPWS WELFARE CREATE OVERRIDE - NO DUPLICATE
@frappe.whitelist()
def create_or_open_welfare_registration(patient):
    """
    Create Welfare Registration once per active Patient.
    If one already exists, do not create duplicate.
    Reception should contact Administrator for changes.
    """
    from frappe import _
    from frappe.utils import nowdate

    patient_doc = _get_patient_doc(patient)

    if not patient_doc:
        frappe.throw(_("Patient not found."))

    mr = _patient_mr(patient_doc)

    # Strong duplicate check:
    # 1. patient_name = patient id
    # 2. custom_patient = patient id
    # 3. mr_no = patient's MR number
    conditions = []
    values = {
        "patient": patient_doc.name,
        "mr_no": mr,
    }

    conditions.append("patient_name = %(patient)s")

    if frappe.get_meta("Patient Registration Form").get_field("custom_patient"):
        conditions.append("custom_patient = %(patient)s")

    if mr:
        conditions.append("mr_no = %(mr_no)s")

    existing = frappe.db.sql(
        f"""
        SELECT name, workflow_state, docstatus, modified
        FROM `tabPatient Registration Form`
        WHERE docstatus < 2
          AND ({' OR '.join(conditions)})
        ORDER BY modified DESC
        LIMIT 1
        """,
        values,
        as_dict=True,
    )

    if existing:
        frappe.msgprint(
            _("Welfare Registration {0} already exists for this patient. Please contact Administrator if any changes are required.").format(
                frappe.bold(existing[0].name)
            ),
            title=_("Welfare Registration Already Exists"),
            indicator="orange",
        )

        return {
            "created": 0,
            "existing": 1,
            "name": existing[0].name,
            "workflow_state": existing[0].workflow_state,
        }

    doc = frappe.new_doc("Patient Registration Form")
    doc.patient_name = patient_doc.name

    if doc.meta.get_field("date"):
        doc.date = nowdate()

    if doc.meta.get_field("workflow_state"):
        doc.workflow_state = "Draft"

    # Auto-fill from Patient.
    sync_prf_patient_fields(doc)

    # These are Administrator approval fields.
    # Do not force Reception to enter them at creation time.
    if doc.meta.get_field("discount_value") and not doc.get("discount_value"):
        doc.discount_value = 0

    # Avoid invalid phone values being copied into PRF contact_no.
    # Frappe core validates Phone fields; we keep that intact.
    if doc.meta.get_field("contact_no") and doc.get("contact_no"):
        raw_phone = str(doc.get("contact_no") or "").strip()
        cleaned = raw_phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if cleaned and not cleaned.isdigit():
            doc.contact_no = None

    # Insert as a draft welfare registration.
    # Approval function will require purpose/discount type/discount value.
    doc.insert(ignore_permissions=True, ignore_mandatory=True)

    updates = {}

    if patient_doc.meta.get_field("custom_latest_welfare_registration"):
        updates["custom_latest_welfare_registration"] = doc.name

    if patient_doc.meta.get_field("custom_patient_billing_type"):
        updates["custom_patient_billing_type"] = "Welfare"

    if patient_doc.meta.get_field("customer_group"):
        updates["customer_group"] = "Welfare"

    if updates:
        frappe.db.set_value("Patient", patient_doc.name, updates, update_modified=False)

    frappe.db.commit()

    return {
        "created": 1,
        "existing": 0,
        "name": doc.name,
        "workflow_state": doc.get("workflow_state"),
    }

# KPWS WELFARE CREATE OVERRIDE - NO DUPLICATE CLEAN
@frappe.whitelist()
def create_or_open_welfare_registration(patient):
    from frappe import _
    from frappe.utils import nowdate

    patient_doc = _get_patient_doc(patient)

    if not patient_doc:
        frappe.throw(_("Patient not found."))

    mr = _patient_mr(patient_doc)

    conditions = ["patient_name = %(patient)s"]
    values = {"patient": patient_doc.name, "mr_no": mr}

    if frappe.get_meta("Patient Registration Form").get_field("custom_patient"):
        conditions.append("custom_patient = %(patient)s")

    if mr:
        conditions.append("mr_no = %(mr_no)s")

    existing = frappe.db.sql(
        f"""
        SELECT name, workflow_state, docstatus, modified
        FROM `tabPatient Registration Form`
        WHERE docstatus < 2
          AND ({' OR '.join(conditions)})
        ORDER BY modified DESC
        LIMIT 1
        """,
        values,
        as_dict=True,
    )

    if existing:
        frappe.msgprint(
            _("Welfare Registration {0} already exists for this patient. Please contact Administrator if any changes are required.").format(
                frappe.bold(existing[0].name)
            ),
            title=_("Welfare Registration Already Exists"),
            indicator="orange",
        )

        return {
            "created": 0,
            "existing": 1,
            "name": existing[0].name,
            "workflow_state": existing[0].workflow_state,
        }

    doc = frappe.new_doc("Patient Registration Form")
    doc.patient_name = patient_doc.name

    if doc.meta.get_field("date"):
        doc.date = nowdate()

    if doc.meta.get_field("workflow_state"):
        doc.workflow_state = "Draft"

    sync_prf_patient_fields(doc)

    # These are Administrator approval fields, not Reception creation fields.
    if doc.meta.get_field("discount_value") and not doc.get("discount_value"):
        doc.discount_value = 0

    if doc.meta.get_field("contact_no") and doc.get("contact_no"):
        raw_phone = str(doc.get("contact_no") or "").strip()
        cleaned = raw_phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if cleaned and not cleaned.isdigit():
            doc.contact_no = None

    doc.insert(ignore_permissions=True, ignore_mandatory=True)

    updates = {}

    if patient_doc.meta.get_field("custom_latest_welfare_registration"):
        updates["custom_latest_welfare_registration"] = doc.name

    if patient_doc.meta.get_field("custom_patient_billing_type"):
        updates["custom_patient_billing_type"] = "Welfare"

    if patient_doc.meta.get_field("customer_group"):
        updates["customer_group"] = "Welfare"

    if updates:
        frappe.db.set_value("Patient", patient_doc.name, updates, update_modified=False)

    frappe.db.commit()

    return {
        "created": 1,
        "existing": 0,
        "name": doc.name,
        "workflow_state": doc.get("workflow_state"),
    }
