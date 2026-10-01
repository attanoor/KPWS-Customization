import frappe
from frappe import _


def _user_allowed():
    if frappe.session.user == "Administrator":
        return True

    allowed_roles = {
        "System Manager",
        "Accounts Manager",
        "Accounts User",
        "Healthcare Manager",
        "Healthcare User",
        "Receptionist",
        "Nursing User",
    }

    user_roles = set(frappe.get_roles(frappe.session.user))
    if user_roles.intersection(allowed_roles):
        return True

    try:
        if frappe.has_permission("Patient", "create"):
            return True
    except Exception:
        pass

    return False


def _ensure_setup():
    if not frappe.db.exists("Customer Group", "Panel"):
        parent = "All Customer Groups" if frappe.db.exists("Customer Group", "All Customer Groups") else None

        cg = frappe.new_doc("Customer Group")
        cg.customer_group_name = "Panel"
        cg.is_group = 0

        if parent and cg.meta.get_field("parent_customer_group"):
            cg.parent_customer_group = parent

        cg.insert(ignore_permissions=True, ignore_mandatory=True)

    if not frappe.get_meta("Customer").get_field("custom_is_panel"):
        cf = frappe.new_doc("Custom Field")
        cf.dt = "Customer"
        cf.fieldname = "custom_is_panel"
        cf.label = "Is Panel"
        cf.fieldtype = "Check"
        cf.insert_after = "customer_group"
        cf.insert(ignore_permissions=True)

    try:
        frappe.db.sql("""
            ALTER TABLE `tabCustomer`
            ADD COLUMN IF NOT EXISTS `custom_is_panel` int(1) NOT NULL DEFAULT 0
        """)
    except Exception:
        pass


@frappe.whitelist()
def create_panel_customer(panel_name, phone=None, email=None):
    if not _user_allowed():
        frappe.throw(_("You are not allowed to create a Panel."), frappe.PermissionError)

    panel_name = (panel_name or "").strip()
    phone = (phone or "").strip()
    email = (email or "").strip()

    if not panel_name:
        frappe.throw(_("Panel Name is required."))

    _ensure_setup()

    existing = frappe.db.get_value(
        "Customer",
        {
            "customer_name": panel_name,
            "custom_is_panel": 1
        },
        "name"
    )

    if existing:
        return {
            "status": "exists",
            "customer": existing,
            "customer_name": panel_name
        }

    customer = frappe.new_doc("Customer")
    customer.customer_name = panel_name

    if customer.meta.get_field("customer_group"):
        customer.customer_group = "Panel"

    if customer.meta.get_field("custom_is_panel"):
        customer.custom_is_panel = 1

    if phone and customer.meta.get_field("mobile_no"):
        customer.mobile_no = phone

    if email and customer.meta.get_field("email_id"):
        customer.email_id = email

    customer.insert(ignore_permissions=True, ignore_mandatory=True)

    frappe.db.commit()

    return {
        "status": "created",
        "customer": customer.name,
        "customer_name": panel_name
    }
