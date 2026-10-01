app_name = "kpws_customization"
app_title = "Kpws Customization"
app_publisher = "mohtashim"
app_description = "app for kpws customization"
app_email = "shoaibmohtashim973@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/kpws_customization/css/kpws_customization.css"
# app_include_js = "/assets/kpws_customization/js/kpws_customization.js"

# include js, css files in header of web template
# web_include_css = "/assets/kpws_customization/css/kpws_customization.css"
# web_include_js = "/assets/kpws_customization/js/kpws_customization.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "kpws_customization/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Quotation": "public/js/quotation.js",
	"POS Profile": "public/js/pos_profile.js",
	"POS Invoice": "public/js/pos_invoice.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "kpws_customization.utils.jinja_methods",
# 	"filters": "kpws_customization.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "kpws_customization.install.before_install"
after_install = "kpws_customization.setup.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "kpws_customization.uninstall.before_uninstall"
# after_uninstall = "kpws_customization.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "kpws_customization.utils.before_app_install"
# after_app_install = "kpws_customization.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "kpws_customization.utils.before_app_uninstall"
# after_app_uninstall = "kpws_customization.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "kpws_customization.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"POS Invoice": ["kpws_customization.kpws_customization.overrides.pos_invoice.KPWSCustomPOSInvoice"],
	"Material Request": ["kpws_customization.kpws_customization.overrides.material_request.KPWSCustomMaterialRequest"]
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"kpws_customization.tasks.all"
# 	],
# 	"daily": [
# 		"kpws_customization.tasks.daily"
# 	],
# 	"hourly": [
# 		"kpws_customization.tasks.hourly"
# 	],
# 	"weekly": [
# 		"kpws_customization.tasks.weekly"
# 	],
# 	"monthly": [
# 		"kpws_customization.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "kpws_customization.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "kpws_customization.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "kpws_customization.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
before_request = ["kpws_customization.kpws_customization.utils.before_request"]
# after_request = ["kpws_customization.utils.after_request"]

# Job Events
# ----------
# before_job = ["kpws_customization.utils.before_job"]
# after_job = ["kpws_customization.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"kpws_customization.auth.validate"
# ]





# KPWS Sales Invoice FIFO Batch Auto Split
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})
_existing_before_validate = doc_events["Sales Invoice"].get("before_validate")

if not _existing_before_validate:
    doc_events["Sales Invoice"]["before_validate"] = ["kpws_customization.sales_invoice_fifo_split.apply_fifo_batch_split"]
elif isinstance(_existing_before_validate, str):
    if _existing_before_validate != "kpws_customization.sales_invoice_fifo_split.apply_fifo_batch_split":
        doc_events["Sales Invoice"]["before_validate"] = [_existing_before_validate, "kpws_customization.sales_invoice_fifo_split.apply_fifo_batch_split"]
elif isinstance(_existing_before_validate, list):
    if "kpws_customization.sales_invoice_fifo_split.apply_fifo_batch_split" not in _existing_before_validate:
        _existing_before_validate.append("kpws_customization.sales_invoice_fifo_split.apply_fifo_batch_split")

# KPWS Clean Patient / Welfare / Sales Flow
try:
    doctype_js
except NameError:
    doctype_js = {}

doctype_js.update({
    "Patient": "public/js/kpws_patient_clean.js",
    "Patient Registration Form": "public/js/kpws_patient_registration_clean.js",
# disabled by final standard patient sales flow:     "Sales Invoice": "public/js/kpws_sales_invoice_clean_v2.js",
})

try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient", {})
doc_events["Patient"].setdefault("validate", [])
if isinstance(doc_events["Patient"].get("validate"), str):
    doc_events["Patient"]["validate"] = [doc_events["Patient"]["validate"]]
if "kpws_customization.api.kpws_clean_flow.validate_patient_clean" not in doc_events["Patient"]["validate"]:
    doc_events["Patient"]["validate"].append("kpws_customization.api.kpws_clean_flow.validate_patient_clean")

doc_events.setdefault("Customer", {})
doc_events["Customer"].setdefault("before_insert", [])
if isinstance(doc_events["Customer"].get("before_insert"), str):
    doc_events["Customer"]["before_insert"] = [doc_events["Customer"]["before_insert"]]
if "kpws_customization.api.kpws_clean_flow.prevent_panel_customer_creation_by_reception" not in doc_events["Customer"]["before_insert"]:
    doc_events["Customer"]["before_insert"].append("kpws_customization.api.kpws_clean_flow.prevent_panel_customer_creation_by_reception")

# KPWS Clean Patient / Welfare / Sales Flow
try:
    doctype_js
except NameError:
    doctype_js = {}

doctype_js.update({
    "Patient": "public/js/kpws_patient_clean.js",
    "Patient Registration Form": "public/js/kpws_patient_registration_clean.js",
# disabled by final standard patient sales flow:     "Sales Invoice": "public/js/kpws_sales_invoice_clean_v2.js",
})

try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient", {})
doc_events["Patient"].setdefault("validate", [])
if isinstance(doc_events["Patient"].get("validate"), str):
    doc_events["Patient"]["validate"] = [doc_events["Patient"]["validate"]]
if "kpws_customization.api.kpws_clean_flow.validate_patient_clean" not in doc_events["Patient"]["validate"]:
    doc_events["Patient"]["validate"].append("kpws_customization.api.kpws_clean_flow.validate_patient_clean")

doc_events.setdefault("Customer", {})
doc_events["Customer"].setdefault("before_insert", [])
if isinstance(doc_events["Customer"].get("before_insert"), str):
    doc_events["Customer"]["before_insert"] = [doc_events["Customer"]["before_insert"]]
if "kpws_customization.api.kpws_clean_flow.prevent_panel_customer_creation_by_reception" not in doc_events["Customer"]["before_insert"]:
    doc_events["Customer"]["before_insert"].append("kpws_customization.api.kpws_clean_flow.prevent_panel_customer_creation_by_reception")



# KPWS Patient naming hotfix: KPWS-####
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient", {})
doc_events["Patient"].setdefault("autoname", [])
if isinstance(doc_events["Patient"].get("autoname"), str):
    doc_events["Patient"]["autoname"] = [doc_events["Patient"]["autoname"]]
if "kpws_customization.api.kpws_clean_flow.autoname_patient_kpws" not in doc_events["Patient"]["autoname"]:
    doc_events["Patient"]["autoname"].append("kpws_customization.api.kpws_clean_flow.autoname_patient_kpws")


# KPWS final clean Sales Invoice validation
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "kpws_customization.api.kpws_sales_invoice_final.validate_sales_invoice" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("kpws_customization.api.kpws_sales_invoice_final.validate_sales_invoice")


# KPWS strict Sales Invoice price list enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "kpws_customization.api.kpws_price_enforcement.enforce_strict_price_list_on_sales_invoice" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("kpws_customization.api.kpws_price_enforcement.enforce_strict_price_list_on_sales_invoice")


# KPWS final billing profile enforcement for Sales Invoice
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "kpws_customization.api.kpws_billing_profile_enforcement.enforce_on_sales_invoice" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("kpws_customization.api.kpws_billing_profile_enforcement.enforce_on_sales_invoice")


# KPWS Sales Invoice POS and warehouse enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "kpws_customization.api.kpws_si_pos_warehouse_fix.enforce_on_sales_invoice" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("kpws_customization.api.kpws_si_pos_warehouse_fix.enforce_on_sales_invoice")


# KPWS unified Sales Invoice server enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "kpws_customization.api.kpws_si_unified_flow.enforce_on_validate" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("kpws_customization.api.kpws_si_unified_flow.enforce_on_validate")


# KPWS final Sales Invoice payment mode enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("before_validate", [])
if isinstance(doc_events["Sales Invoice"]["before_validate"], str):
    doc_events["Sales Invoice"]["before_validate"] = [doc_events["Sales Invoice"]["before_validate"]]
if "kpws_customization.api.kpws_si_unified_flow.enforce_payment_modes_on_validate" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("kpws_customization.api.kpws_si_unified_flow.enforce_payment_modes_on_validate")


# KPWS final POS payment account enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})

doc_events["Sales Invoice"].setdefault("before_validate", [])
if isinstance(doc_events["Sales Invoice"]["before_validate"], str):
    doc_events["Sales Invoice"]["before_validate"] = [doc_events["Sales Invoice"]["before_validate"]]
if "kpws_customization.api.kpws_si_payment_account_fix.enforce_payment_accounts_on_sales_invoice" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("kpws_customization.api.kpws_si_payment_account_fix.enforce_payment_accounts_on_sales_invoice")

doc_events["Sales Invoice"].setdefault("before_submit", [])
if isinstance(doc_events["Sales Invoice"]["before_submit"], str):
    doc_events["Sales Invoice"]["before_submit"] = [doc_events["Sales Invoice"]["before_submit"]]
if "kpws_customization.api.kpws_si_payment_account_fix.enforce_payment_accounts_on_sales_invoice" not in doc_events["Sales Invoice"]["before_submit"]:
    doc_events["Sales Invoice"]["before_submit"].append("kpws_customization.api.kpws_si_payment_account_fix.enforce_payment_accounts_on_sales_invoice")


# KPWS final Sales Invoice payment enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})

_old_kpws_payment_methods = [
    "kpws_customization.api.kpws_si_payment_account_fix.enforce_payment_accounts_on_sales_invoice",
    "kpws_customization.api.kpws_si_unified_flow.enforce_payment_modes_on_validate",
]

for _event in ["before_validate", "before_submit"]:
    doc_events["Sales Invoice"].setdefault(_event, [])
    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]
    doc_events["Sales Invoice"][_event] = [
        _m for _m in doc_events["Sales Invoice"][_event]
        if _m not in _old_kpws_payment_methods
    ]

doc_events["Sales Invoice"].setdefault("before_validate", [])
if "kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments")

doc_events["Sales Invoice"].setdefault("before_submit", [])
if "kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments" not in doc_events["Sales Invoice"]["before_submit"]:
    doc_events["Sales Invoice"]["before_submit"].append("kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments")


# KPWS Patient Registration Form patient data sync
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Patient Registration Form", {})
doc_events["Patient Registration Form"].setdefault("before_validate", [])
if isinstance(doc_events["Patient Registration Form"]["before_validate"], str):
    doc_events["Patient Registration Form"]["before_validate"] = [doc_events["Patient Registration Form"]["before_validate"]]
if "kpws_customization.api.kpws_prf_patient_data_fix.populate_on_validate" not in doc_events["Patient Registration Form"]["before_validate"]:
    doc_events["Patient Registration Form"]["before_validate"].append("kpws_customization.api.kpws_prf_patient_data_fix.populate_on_validate")


# KPWS Sales Invoice MR Number enforcement from Patient.custom_reference_number
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})
doc_events["Sales Invoice"].setdefault("before_validate", [])
if isinstance(doc_events["Sales Invoice"]["before_validate"], str):
    doc_events["Sales Invoice"]["before_validate"] = [doc_events["Sales Invoice"]["before_validate"]]
if "kpws_customization.api.kpws_si_mr_reference_fix.enforce_sales_invoice_mr_number" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("kpws_customization.api.kpws_si_mr_reference_fix.enforce_sales_invoice_mr_number")


# KPWS Sales Invoice Pharmacy stock enforcement
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Sales Invoice", {})

doc_events["Sales Invoice"].setdefault("before_validate", [])
if isinstance(doc_events["Sales Invoice"]["before_validate"], str):
    doc_events["Sales Invoice"]["before_validate"] = [doc_events["Sales Invoice"]["before_validate"]]
if "kpws_customization.api.kpws_si_stock_filter.set_pharmacy_warehouse" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("kpws_customization.api.kpws_si_stock_filter.set_pharmacy_warehouse")

doc_events["Sales Invoice"].setdefault("validate", [])
if isinstance(doc_events["Sales Invoice"]["validate"], str):
    doc_events["Sales Invoice"]["validate"] = [doc_events["Sales Invoice"]["validate"]]
if "kpws_customization.api.kpws_si_stock_filter.validate_pharmacy_stock" not in doc_events["Sales Invoice"]["validate"]:
    doc_events["Sales Invoice"]["validate"].append("kpws_customization.api.kpws_si_stock_filter.validate_pharmacy_stock")


# KPWS safe Patient Registration Form patient sync
doc_events = globals().get("doc_events", {})
doc_events.setdefault("Patient Registration Form", {})
doc_events["Patient Registration Form"].setdefault("before_validate", [])
if isinstance(doc_events["Patient Registration Form"]["before_validate"], str):
    doc_events["Patient Registration Form"]["before_validate"] = [doc_events["Patient Registration Form"]["before_validate"]]
if "kpws_customization.api.kpws_prf_safe_recovery.populate_on_validate" not in doc_events["Patient Registration Form"]["before_validate"]:
    doc_events["Patient Registration Form"]["before_validate"].append("kpws_customization.api.kpws_prf_safe_recovery.populate_on_validate")


# KPWS Patient / Customer Group / Panel restrictions
def _kpws_add_doc_event(_doctype, _event, _handler):
    global doc_events

    try:
        doc_events
    except NameError:
        doc_events = {}

    doc_events.setdefault(_doctype, {})

    current = doc_events[_doctype].get(_event)

    if not current:
        doc_events[_doctype][_event] = _handler
    elif isinstance(current, str):
        if current != _handler:
            doc_events[_doctype][_event] = [current, _handler]
    elif isinstance(current, (list, tuple)):
        current = list(current)
        if _handler not in current:
            current.append(_handler)
        doc_events[_doctype][_event] = current


_kpws_add_doc_event(
    "Patient",
    "before_validate",
    "kpws_customization.api.kpws_patient_customer_rules.validate_patient_customer_rules"
)

_kpws_add_doc_event(
    "Customer",
    "validate",
    "kpws_customization.api.kpws_patient_customer_rules.validate_customer_panel_rules"
)

# KPWS Sales Invoice patient billing control
def _kpws_add_si_doc_event(_doctype, _event, _handler):
    global doc_events

    try:
        doc_events
    except NameError:
        doc_events = {}

    doc_events.setdefault(_doctype, {})

    current = doc_events[_doctype].get(_event)

    if not current:
        doc_events[_doctype][_event] = _handler
    elif isinstance(current, str):
        if current != _handler:
            doc_events[_doctype][_event] = [current, _handler]
    elif isinstance(current, (list, tuple)):
        current = list(current)
        if _handler not in current:
            current.append(_handler)
        doc_events[_doctype][_event] = current


_kpws_add_si_doc_event(
    "Sales Invoice",
    "validate",
    "kpws_customization.api.kpws_patient_invoice_control.validate_sales_invoice_patient_billing_rules"
)

# KPWS Sales Invoice item pricing control
def _kpws_add_si_pricing_doc_event(_doctype, _event, _handler):
    global doc_events

    try:
        doc_events
    except NameError:
        doc_events = {}

    doc_events.setdefault(_doctype, {})

    current = doc_events[_doctype].get(_event)

    if not current:
        doc_events[_doctype][_event] = _handler
    elif isinstance(current, str):
        if current != _handler:
            doc_events[_doctype][_event] = [current, _handler]
    elif isinstance(current, (list, tuple)):
        current = list(current)
        if _handler not in current:
            current.append(_handler)
        doc_events[_doctype][_event] = current


_kpws_add_si_pricing_doc_event(
    "Sales Invoice",
    "validate",
    "kpws_customization.api.kpws_sales_invoice_pricing_control.validate_sales_invoice_item_pricing"
)



# KPWS_PRF_PERCENTAGE_FIX_V28_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient Registration Form", {})

_existing_validate = doc_events["Patient Registration Form"].get("validate", [])

if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]

if "kpws_customization.api.kpws_prf_percentage_fix_v28.validate_percentage" not in _existing_validate:
    _existing_validate.append("kpws_customization.api.kpws_prf_percentage_fix_v28.validate_percentage")

doc_events["Patient Registration Form"]["validate"] = _existing_validate


# KPWS_PRF_UPDATE_AFTER_SUBMIT_FIX_V29_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient Registration Form", {})

_existing_validate = doc_events["Patient Registration Form"].get("validate", [])
if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]
if "kpws_customization.api.kpws_prf_update_after_submit_fix_v29.validate_percentage" not in _existing_validate:
    _existing_validate.append("kpws_customization.api.kpws_prf_update_after_submit_fix_v29.validate_percentage")
doc_events["Patient Registration Form"]["validate"] = _existing_validate

_existing_before_save = doc_events["Patient Registration Form"].get("before_save", [])
if isinstance(_existing_before_save, str):
    _existing_before_save = [_existing_before_save]
if "kpws_customization.api.kpws_prf_update_after_submit_fix_v29.allow_limited_update_after_submit" not in _existing_before_save:
    _existing_before_save.append("kpws_customization.api.kpws_prf_update_after_submit_fix_v29.allow_limited_update_after_submit")
doc_events["Patient Registration Form"]["before_save"] = _existing_before_save


# KPWS_PRF_AUTO_IDENTITY_FETCH_V34_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient Registration Form", {})

def _kpws_append_prf_hook(event_name, method_path):
    existing = doc_events["Patient Registration Form"].get(event_name, [])
    if isinstance(existing, str):
        existing = [existing]
    if method_path not in existing:
        existing.append(method_path)
    doc_events["Patient Registration Form"][event_name] = existing

_kpws_append_prf_hook("before_insert", "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.before_insert")
_kpws_append_prf_hook("before_save", "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.before_save")
_kpws_append_prf_hook("validate", "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.validate_percentage")


# KPWS_PRF_DYNAMIC_IDENTITY_FETCH_V35_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient Registration Form", {})

def _kpws_prf_v35_append(event_name, method_path):
    existing = doc_events["Patient Registration Form"].get(event_name, [])
    if isinstance(existing, str):
        existing = [existing]
    if method_path not in existing:
        existing.append(method_path)
    doc_events["Patient Registration Form"][event_name] = existing

_kpws_prf_v35_append("before_insert", "kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35.before_insert")
_kpws_prf_v35_append("before_save", "kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35.before_save")


# KPWS_BULK_WELFARE_PRF_V36_HOOK
try:
    doctype_list_js
except NameError:
    doctype_list_js = {}

def _kpws_v36_add_list_js(doctype, path):
    existing = doctype_list_js.get(doctype)

    if not existing:
        doctype_list_js[doctype] = path
        return

    if isinstance(existing, str):
        if existing != path:
            doctype_list_js[doctype] = [existing, path]
        return

    if isinstance(existing, list) and path not in existing:
        existing.append(path)
        doctype_list_js[doctype] = existing

_kpws_v36_add_list_js("Patient", "public/js/kpws_patient_bulk_welfare_list.js")
_kpws_v36_add_list_js("Patient Registration Form", "public/js/kpws_prf_bulk_approval_list.js")


# KPWS_PRF_PANEL_UPDATE_AFTER_SUBMIT_V42_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient Registration Form", {})

_existing_before_save = doc_events["Patient Registration Form"].get("before_save", [])
if isinstance(_existing_before_save, str):
    _existing_before_save = [_existing_before_save]

_method = "kpws_customization.api.kpws_prf_panel_update_after_submit_v42.allow_panel_update_after_submit"
if _method not in _existing_before_save:
    _existing_before_save.append(_method)

doc_events["Patient Registration Form"]["before_save"] = _existing_before_save


# KPWS_PATIENT_TYPE_CHANGE_FLOW_V46_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient", {})

_existing_validate = doc_events["Patient"].get("validate", [])
if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]

_method = "kpws_customization.api.kpws_patient_type_change_flow_v46._sync_direct_save"
if _method not in _existing_validate:
    _existing_validate.append(_method)

doc_events["Patient"]["validate"] = _existing_validate


# KPWS_PATIENT_TYPE_CHANGE_FLOW_V48_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Patient", {})

_existing_validate = doc_events["Patient"].get("validate", [])
if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]

_method = "kpws_customization.api.kpws_patient_type_change_flow_v48._sync_direct_save"
if _method not in _existing_validate:
    _existing_validate.append(_method)

doc_events["Patient"]["validate"] = _existing_validate

# KPWS_WELFARE_PANEL_ACCOUNTING_V27_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

for _event, _method in {
    "on_submit": "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_submit",
    "on_cancel": "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_cancel",
}.items():
    doc_events["Sales Invoice"].setdefault(_event, [])
    if isinstance(doc_events["Sales Invoice"].get(_event), str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]
    if _method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_method)


# KPWS_DISABLE_OLD_WELFARE_PAYMENT_SPLIT_AND_USE_AUTO_JE
# Reason:
# Old hook was forcing Welfare/Zakat/Donation as Mode of Payment.
# New flow uses:
# Dr ZAKAT/DONATION DISBURSE
# Cr WELFARE RECEIVABLE
# through automatic Journal Entry after Sales Invoice submission.

try:
    doc_events
except NameError:
    doc_events = {}

OLD_KPWS_WELFARE_HOOKS = {
    "kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments",
}

def _kpws_remove_old_welfare_hooks_from_event(event_value):
    if not event_value:
        return event_value

    if isinstance(event_value, str):
        if event_value in OLD_KPWS_WELFARE_HOOKS:
            return None
        return event_value

    if isinstance(event_value, (list, tuple, set)):
        cleaned = []
        for method in event_value:
            if method not in OLD_KPWS_WELFARE_HOOKS:
                cleaned.append(method)
        return cleaned

    return event_value


if isinstance(doc_events.get("Sales Invoice"), dict):
    for _event_name in list(doc_events["Sales Invoice"].keys()):
        _cleaned_value = _kpws_remove_old_welfare_hooks_from_event(
            doc_events["Sales Invoice"].get(_event_name)
        )

        if _cleaned_value in (None, [], (), set()):
            doc_events["Sales Invoice"].pop(_event_name, None)
        else:
            doc_events["Sales Invoice"][_event_name] = _cleaned_value


doc_events.setdefault("Sales Invoice", {})

for _event, _method in {
    "on_submit": "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_submit",
    "on_cancel": "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_cancel",
}.items():
    doc_events["Sales Invoice"].setdefault(_event, [])

    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]

    if _method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_method)



# KPWS_BEFORE_SUBMIT_FORCE_NON_POS_V30_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

_method = "kpws_customization.api.kpws_pharmacy_welfare_accounting.before_sales_invoice_submit"

doc_events["Sales Invoice"].setdefault("before_submit", [])

if isinstance(doc_events["Sales Invoice"]["before_submit"], str):
    doc_events["Sales Invoice"]["before_submit"] = [doc_events["Sales Invoice"]["before_submit"]]

if _method not in doc_events["Sales Invoice"]["before_submit"]:
    doc_events["Sales Invoice"]["before_submit"].append(_method)


# KPWS_FINAL_WELFARE_SETTLEMENT_V34_HOOKS
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

for _event, _method in {
    "on_submit": "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_submit",
    "before_save": "kpws_customization.api.kpws_pharmacy_welfare_accounting.protect_submitted_kpws_invoice_before_save",
}.items():
    doc_events["Sales Invoice"].setdefault(_event, [])

    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]

    if _method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_method)


# KPWS_FINAL_WELFARE_SETTLEMENT_CLEAN_HOOKS
try:
    doc_events
except NameError:
    doc_events = {}

_old_welfare_methods = {
    "kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_submit",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_cancel",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.before_sales_invoice_submit",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.protect_submitted_kpws_invoice_before_save",
}

if isinstance(doc_events.get("Sales Invoice"), dict):
    for _event in list(doc_events["Sales Invoice"].keys()):
        _value = doc_events["Sales Invoice"].get(_event)

        if isinstance(_value, str):
            if _value in _old_welfare_methods:
                doc_events["Sales Invoice"].pop(_event, None)

        elif isinstance(_value, (list, tuple, set)):
            _cleaned = [m for m in _value if m not in _old_welfare_methods]
            if _cleaned:
                doc_events["Sales Invoice"][_event] = _cleaned
            else:
                doc_events["Sales Invoice"].pop(_event, None)

doc_events.setdefault("Sales Invoice", {})

_final_before_submit = "kpws_customization.api.kpws_welfare_final_settlement.before_sales_invoice_submit"
_final_on_submit = "kpws_customization.api.kpws_welfare_final_settlement.on_sales_invoice_submit"

for _event, _method in {
    "before_submit": _final_before_submit,
    "on_submit": _final_on_submit,
}.items():
    doc_events["Sales Invoice"].setdefault(_event, [])

    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]

    if _method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_method)


# KPWS_SUBMITTED_WELFARE_INVOICE_PROTECTION_V35_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

_method = "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_invoice_before_save"

doc_events["Sales Invoice"].setdefault("before_save", [])

if isinstance(doc_events["Sales Invoice"]["before_save"], str):
    doc_events["Sales Invoice"]["before_save"] = [doc_events["Sales Invoice"]["before_save"]]

if _method not in doc_events["Sales Invoice"]["before_save"]:
    doc_events["Sales Invoice"]["before_save"].append(_method)


# KPWS_SUBMITTED_WELFARE_INVOICE_PROTECTION_V35_HOOK
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

_method = "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_invoice_before_save"

doc_events["Sales Invoice"].setdefault("before_save", [])

if isinstance(doc_events["Sales Invoice"]["before_save"], str):
    doc_events["Sales Invoice"]["before_save"] = [doc_events["Sales Invoice"]["before_save"]]

if _method not in doc_events["Sales Invoice"]["before_save"]:
    doc_events["Sales Invoice"]["before_save"].append(_method)


# KPWS_FINAL_SUBMITTED_SALES_INVOICE_LOCK_V36_HOOKS
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

_protect_method = "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_sales_invoice_before_save"

for _event in ["before_save", "before_update_after_submit"]:
    doc_events["Sales Invoice"].setdefault(_event, [])

    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]

    if _protect_method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_protect_method)


# KPWS_BILLING_PANEL_AUDIT_FIX_V40_HOOKS
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

# Remove old/conflicting welfare settlement hooks. Keep FIFO, stock filter, MR reference,
# patient invoice control, and pricing controls intact.
_KPWS_V40_REMOVE = {
    "kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.before_sales_invoice_submit",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_submit",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_cancel",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.protect_submitted_kpws_invoice_before_save",
    "kpws_customization.api.kpws_welfare_final_settlement.before_sales_invoice_submit",
    "kpws_customization.api.kpws_welfare_final_settlement.on_sales_invoice_submit",
    "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_invoice_before_save",
    "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_sales_invoice_before_save",
    "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_kpws_invoice_before_save",
    "kpws_customization.api.kpws_si_payment_account_fix.enforce_payment_accounts_on_sales_invoice",
}

for _event in list(doc_events.get("Sales Invoice", {}).keys()):
    _value = doc_events["Sales Invoice"].get(_event)
    if isinstance(_value, str):
        if _value in _KPWS_V40_REMOVE:
            doc_events["Sales Invoice"].pop(_event, None)
    elif isinstance(_value, (list, tuple, set)):
        _cleaned = [m for m in _value if m not in _KPWS_V40_REMOVE]
        if _cleaned:
            doc_events["Sales Invoice"][_event] = _cleaned
        else:
            doc_events["Sales Invoice"].pop(_event, None)

_FINAL = {
    "before_submit": "kpws_customization.api.kpws_billing_policy_v40.before_submit_sales_invoice",
    "on_submit": "kpws_customization.api.kpws_billing_policy_v40.on_submit_sales_invoice",
    "before_cancel": "kpws_customization.api.kpws_billing_policy_v40.before_cancel_sales_invoice",
    "before_save": "kpws_customization.api.kpws_billing_policy_v40.protect_submitted_invoice_before_save",
    "before_update_after_submit": "kpws_customization.api.kpws_billing_policy_v40.protect_submitted_invoice_before_save",
}

for _event, _method in _FINAL.items():
    doc_events["Sales Invoice"].setdefault(_event, [])
    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]
    if _method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_method)


# KPWS_PANEL_FINAL_POLICY_HOOKS_V44
try:
    doc_events
except NameError:
    doc_events = {}

doc_events.setdefault("Sales Invoice", {})

_panel_methods = {
    "before_validate": "kpws_customization.api.kpws_panel_final_policy.apply_panel_policy",
    "before_submit": "kpws_customization.api.kpws_panel_final_policy.apply_panel_policy",
    "before_save": "kpws_customization.api.kpws_panel_final_policy.protect_submitted_panel_invoice",
    "before_update_after_submit": "kpws_customization.api.kpws_panel_final_policy.protect_submitted_panel_invoice",
}

for _event, _method in _panel_methods.items():
    doc_events["Sales Invoice"].setdefault(_event, [])

    if isinstance(doc_events["Sales Invoice"][_event], str):
        doc_events["Sales Invoice"][_event] = [doc_events["Sales Invoice"][_event]]

    if _method not in doc_events["Sales Invoice"][_event]:
        doc_events["Sales Invoice"][_event].append(_method)


# KPWS_PATIENT_PHARMACY_FLOW_V50_HOOKS
try:
    doc_events
except NameError:
    doc_events = {}

# Remove known older conflicting KPWS welfare/panel handlers from runtime doc_events.
_old_kpws_methods_v50 = {
    "kpws_customization.api.kpws_welfare_payment_split.enforce_sales_invoice_payments",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.before_sales_invoice_submit",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_submit",
    "kpws_customization.api.kpws_pharmacy_welfare_accounting.on_sales_invoice_cancel",
    "kpws_customization.api.kpws_welfare_final_settlement.before_sales_invoice_submit",
    "kpws_customization.api.kpws_welfare_final_settlement.on_sales_invoice_submit",
    "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_invoice_before_save",
    "kpws_customization.api.kpws_welfare_final_settlement.protect_submitted_sales_invoice_before_save",
    "kpws_customization.api.kpws_panel_final_policy.apply_panel_policy",
    "kpws_customization.api.kpws_panel_final_policy.protect_submitted_panel_invoice",
}

for _dt, _events in list(doc_events.items()):
    if isinstance(_events, dict):
        for _event in list(_events.keys()):
            _value = _events.get(_event)
            if isinstance(_value, str):
                if _value in _old_kpws_methods_v50:
                    _events.pop(_event, None)
            elif isinstance(_value, (list, tuple, set)):
                _cleaned = [m for m in _value if m not in _old_kpws_methods_v50]
                if _cleaned:
                    _events[_event] = _cleaned
                else:
                    _events.pop(_event, None)

doc_events.setdefault("Patient", {})
doc_events.setdefault("Patient Registration Form", {})
doc_events.setdefault("Sales Invoice", {})

_new_events_v50 = {
    "Patient": {
        "validate": "kpws_customization.api.kpws_patient_billing_flow_v50.validate_patient",
    },
    "Patient Registration Form": {
        "validate": "kpws_customization.api.kpws_patient_billing_flow_v50.validate_patient_registration_form",
        "on_submit": "kpws_customization.api.kpws_patient_billing_flow_v50.on_patient_registration_submit",
    },
    "Sales Invoice": {
        "before_validate": "kpws_customization.api.kpws_patient_billing_flow_v50.apply_sales_invoice_policy",
        "before_submit": "kpws_customization.api.kpws_patient_billing_flow_v50.apply_sales_invoice_policy",
        "on_submit": "kpws_customization.api.kpws_patient_billing_flow_v50.on_sales_invoice_submit",
        "before_save": "kpws_customization.api.kpws_patient_billing_flow_v50.protect_submitted_invoice",
        "before_update_after_submit": "kpws_customization.api.kpws_patient_billing_flow_v50.protect_submitted_invoice",
    },
}

for _dt, _events in _new_events_v50.items():
    doc_events.setdefault(_dt, {})
    for _event, _method in _events.items():
        doc_events[_dt].setdefault(_event, [])
        if isinstance(doc_events[_dt][_event], str):
            doc_events[_dt][_event] = [doc_events[_dt][_event]]
        if _method not in doc_events[_dt][_event]:
            doc_events[_dt][_event].append(_method)


# KPWS_PATIENT_INTAKE_FLOW_V51_HOOKS
try:
    doc_events
except NameError:
    doc_events = {}

def _kpws_v51_append_hook(_doctype, _event, _method):
    doc_events.setdefault(_doctype, {})
    doc_events[_doctype].setdefault(_event, [])
    if isinstance(doc_events[_doctype][_event], str):
        doc_events[_doctype][_event] = [doc_events[_doctype][_event]]
    if _method not in doc_events[_doctype][_event]:
        doc_events[_doctype][_event].append(_method)

_kpws_v51_append_hook("Patient", "validate", "kpws_customization.api.kpws_patient_intake_v51.validate_patient")
_kpws_v51_append_hook("Patient Registration Form", "validate", "kpws_customization.api.kpws_patient_intake_v51.validate_prf")
_kpws_v51_append_hook("Patient Registration Form", "on_submit", "kpws_customization.api.kpws_patient_intake_v51.on_prf_submit")


# KPWS_DISABLE_OLD_PATIENT_TYPE_CHANGE_HOOKS_V62
try:
    doc_events
except NameError:
    doc_events = {}

_old_patient_type_methods = {
    "kpws_customization.api.kpws_patient_type_change_flow_v48.before_patient_save",
    "kpws_customization.api.kpws_patient_type_change_flow_v48.validate_patient",
    "kpws_customization.api.kpws_patient_type_change_flow_v48.on_patient_update",
    "kpws_customization.api.kpws_patient_type_change_flow_v48._sync_direct_save",
    "kpws_customization.api.kpws_patient_customer_rules.validate_patient_customer_rules",
}

if isinstance(doc_events.get("Patient"), dict):
    for _event in list(doc_events["Patient"].keys()):
        _value = doc_events["Patient"].get(_event)

        if isinstance(_value, str):
            if _value in _old_patient_type_methods:
                doc_events["Patient"].pop(_event, None)

        elif isinstance(_value, (list, tuple, set)):
            _cleaned = [m for m in _value if m not in _old_patient_type_methods]
            if _cleaned:
                doc_events["Patient"][_event] = _cleaned
            else:
                doc_events["Patient"].pop(_event, None)


# KPWS_DISABLE_OLD_PATIENT_CUSTOMER_SYNC_V76
# Patient Intake now controls patient classification.
# Old patient type/customer sync hooks must not create/overwrite Customer on Patient type changes.

try:
    doc_events
except NameError:
    doc_events = {}

_BLOCK_PATIENT_HOOK_MODULES = (
    "kpws_patient_type_change_flow_v48",
    "kpws_patient_customer_rules",
)

if isinstance(doc_events.get("Patient"), dict):
    for _event in list(doc_events["Patient"].keys()):
        _value = doc_events["Patient"].get(_event)

        if isinstance(_value, str):
            if any(_m in _value for _m in _BLOCK_PATIENT_HOOK_MODULES):
                doc_events["Patient"].pop(_event, None)

        elif isinstance(_value, (list, tuple, set)):
            _cleaned = [
                _method for _method in _value
                if not any(_m in str(_method) for _m in _BLOCK_PATIENT_HOOK_MODULES)
            ]

            if _cleaned:
                doc_events["Patient"][_event] = _cleaned
            else:
                doc_events["Patient"].pop(_event, None)


# KPWS_CLEAN_PATIENT_INTAKE_HOOK_SANITIZER_V80
# Final cleanup: Patient Intake v80 owns classification.
# Remove old Patient/Customer hooks that created/updated customers during Patient changes.

try:
    doc_events
except NameError:
    doc_events = {}

def _kpws_v80_clean_event_list(value, blocked_tokens):
    if not value:
        return value
    if isinstance(value, str):
        return None if any(t in value for t in blocked_tokens) else value
    if isinstance(value, (list, tuple, set)):
        cleaned = [x for x in value if not any(t in str(x) for t in blocked_tokens)]
        return cleaned
    return value

_patient_blocked = [
    "kpws_patient_type_change_flow_v48",
    "kpws_patient_customer_rules",
    "kpws_clean_flow.validate_patient_clean",
]

_customer_blocked = [
    "kpws_clean_flow.prevent_panel_customer_creation_by_reception",
]

if isinstance(doc_events.get("Patient"), dict):
    for _event in list(doc_events["Patient"].keys()):
        if _event == "autoname":
            continue
        _cleaned = _kpws_v80_clean_event_list(doc_events["Patient"].get(_event), _patient_blocked)
        if _cleaned:
            doc_events["Patient"][_event] = _cleaned
        else:
            doc_events["Patient"].pop(_event, None)

if isinstance(doc_events.get("Customer"), dict):
    for _event in list(doc_events["Customer"].keys()):
        _cleaned = _kpws_v80_clean_event_list(doc_events["Customer"].get(_event), _customer_blocked)
        if _cleaned:
            doc_events["Customer"][_event] = _cleaned
        else:
            doc_events["Customer"].pop(_event, None)


# KPWS extra patient fields on custom Patient Intake / Welfare Approval pages
try:
    app_include_js
except NameError:
    app_include_js = []

if isinstance(app_include_js, str):
    app_include_js = [app_include_js]

if "/assets/kpws_customization/js/kpws_extra_patient_fields_widget.js" not in app_include_js:
    app_include_js.append("/assets/kpws_customization/js/kpws_extra_patient_fields_widget.js")

# KPWS_PRF_EXTRA_FIELDS_AUTOSYNC_HOOK_V1
def _kpws_append_doc_event(dt, event, method):
    global doc_events

    try:
        doc_events
    except NameError:
        doc_events = {}

    doc_events.setdefault(dt, {})

    existing = doc_events[dt].get(event)

    if not existing:
        doc_events[dt][event] = [method]
    elif isinstance(existing, str):
        if existing != method:
            doc_events[dt][event] = [existing, method]
    elif isinstance(existing, (list, tuple)):
        if method not in existing:
            doc_events[dt][event] = list(existing) + [method]

_kpws_append_doc_event(
    "Patient Registration Form",
    "before_save",
    "kpws_customization.api.kpws_patient_extra_fields.prf_before_save_copy_extra_fields"
)

# KPWS_STABLE_PATIENT_PRF_EXTRA_FIELD_SYNC_HOOKS_V1
def _kpws_append_doc_event(dt, event, method):
    global doc_events

    try:
        doc_events
    except NameError:
        doc_events = {}

    doc_events.setdefault(dt, {})

    existing = doc_events[dt].get(event)

    if not existing:
        doc_events[dt][event] = [method]
    elif isinstance(existing, str):
        if existing != method:
            doc_events[dt][event] = [existing, method]
    elif isinstance(existing, (list, tuple)):
        if method not in existing:
            doc_events[dt][event] = list(existing) + [method]


_kpws_append_doc_event(
    "Patient",
    "on_update",
    "kpws_customization.api.kpws_patient_extra_fields.patient_after_save_sync_extra_fields_to_prf"
)

_kpws_append_doc_event(
    "Patient Registration Form",
    "before_save",
    "kpws_customization.api.kpws_patient_extra_fields.prf_before_save_sync_extra_fields_to_patient"
)

# KPWS Donation in Kind: auto-default warehouse/account on the two dedicated
# Stock Entry Types (Donation in Kind Receipt / Donation in Kind Transfer to Pharmacy).
_kpws_append_doc_event(
    "Stock Entry",
    "before_validate",
    "kpws_customization.api.kpws_donation_in_kind.apply_donation_in_kind_defaults"
)

# KPWS POS rounding fix: snap sub-currency-unit outstanding_amount drift to zero
# on POS invoices, caused by paid_amount being set against grand_total before
# ERPNext's rounding adjustment produces the final rounded_total. Runs on
# before_submit (after core total/rounding calculation), so it sees the final
# rounded_total. Only affects POS invoices that already have a payment recorded.
_kpws_append_doc_event(
    "Sales Invoice",
    "before_submit",
    "kpws_customization.api.kpws_pos_rounding_fix.snap_pos_rounding"
)

