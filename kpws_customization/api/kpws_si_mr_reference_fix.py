import importlib
import frappe

CLIENT_SCRIPT_NAMES = [
    "KPWS FINAL Light Sales Invoice Client",
    "KPWS FINAL Unified Sales Invoice Flow",
]


def _patient_reference_field():
    if not frappe.get_meta("Patient").get_field("custom_reference_number"):
        frappe.throw("Patient field custom_reference_number was not found.")
    return "custom_reference_number"


def get_patient_mr_number(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return ""

    fieldname = _patient_reference_field()
    return frappe.db.get_value("Patient", patient, fieldname) or ""


def find_patient_by_reference(mr_number):
    if not mr_number:
        return ""

    mr = str(mr_number).strip()
    fieldname = _patient_reference_field()

    patient = frappe.db.get_value("Patient", {fieldname: mr}, "name")
    if patient:
        return patient

    # Allow existing Patient ID only as fallback for old links,
    # but never display Patient ID as MR number.
    if frappe.db.exists("Patient", mr):
        return mr

    return ""


@frappe.whitelist()
def get_context(patient=None, mr_number=None, customer=None, is_walkin=0, walkin_name=None, walkin_mr=None):
    base = importlib.import_module("kpws_customization.api.kpws_si_unified_flow")

    # If user entered MR number, resolve using Patient.custom_reference_number first.
    if not patient and mr_number:
        patient = find_patient_by_reference(mr_number)

    ctx = base.get_context(
        patient=patient,
        mr_number=mr_number,
        customer=customer,
        is_walkin=is_walkin,
        walkin_name=walkin_name,
        walkin_mr=walkin_mr,
    ) or {}

    # Force displayed MR number from Patient.custom_reference_number.
    final_patient = ctx.get("patient") or patient

    if final_patient and frappe.db.exists("Patient", final_patient):
        ctx["patient"] = final_patient
        ctx["mr_number"] = get_patient_mr_number(final_patient)

    return ctx


def enforce_sales_invoice_mr_number(doc, method=None):
    if doc.doctype != "Sales Invoice":
        return

    if doc.get("custom_is_walkin"):
        return

    # If patient is blank but MR is entered, resolve Patient from custom_reference_number.
    if not doc.get("patient") and doc.get("custom_kpws_mr_number"):
        patient = find_patient_by_reference(doc.get("custom_kpws_mr_number"))
        if patient:
            doc.patient = patient

    # Always display true MR number from Patient.custom_reference_number.
    if doc.get("patient") and frappe.db.exists("Patient", doc.patient):
        mr = get_patient_mr_number(doc.patient)
        if doc.meta.get_field("custom_kpws_mr_number"):
            doc.custom_kpws_mr_number = mr


def patch_client_scripts():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    old_method = "kpws_customization.api.kpws_si_unified_flow.get_context"
    new_method = "kpws_customization.api.kpws_si_mr_reference_fix.get_context"

    rows = frappe.get_all(
        "Client Script",
        filters={"dt": "Sales Invoice"},
        fields=["name", "script", "enabled"],
    )

    for row in rows:
        script = row.script or ""

        if old_method in script:
            doc = frappe.get_doc("Client Script", row.name)
            doc.script = script.replace(old_method, new_method)
            doc.enabled = 1 if row.name in CLIENT_SCRIPT_NAMES else row.enabled
            doc.save(ignore_permissions=True)
            print("Patched Client Script:", row.name)

    # If no existing light script was found, create a tiny helper script.
    if not frappe.db.exists("Client Script", "KPWS FINAL MR Reference Sync"):
        script = r'''
frappe.ui.form.on("Sales Invoice", {
    patient(frm) {
        kpws_si_mr_reference_sync(frm);
    },
    custom_kpws_mr_number(frm) {
        kpws_si_mr_reference_sync(frm);
    },
    refresh(frm) {
        kpws_si_mr_reference_sync(frm);
    }
});

function kpws_si_mr_reference_sync(frm) {
    if (frm.doc.custom_is_walkin) return;
    if (!frm.doc.patient && !frm.doc.custom_kpws_mr_number) return;

    frappe.call({
        method: "kpws_customization.api.kpws_si_mr_reference_fix.get_context",
        args: {
            patient: frm.doc.patient || "",
            mr_number: frm.doc.custom_kpws_mr_number || "",
            customer: frm.doc.customer || "",
            is_walkin: 0
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            let updates = {};

            if (d.patient && frm.fields_dict.patient && frm.doc.patient !== d.patient) {
                updates.patient = d.patient;
            }

            if (d.mr_number && frm.fields_dict.custom_kpws_mr_number && frm.doc.custom_kpws_mr_number !== d.mr_number) {
                updates.custom_kpws_mr_number = d.mr_number;
            }

            if (Object.keys(updates).length) {
                frm.set_value(updates);
            }
        }
    });
}
'''
        frappe.get_doc({
            "doctype": "Client Script",
            "name": "KPWS FINAL MR Reference Sync",
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script: KPWS FINAL MR Reference Sync")


def backfill_sales_invoice_mr_numbers():
    if not frappe.get_meta("Sales Invoice").get_field("custom_kpws_mr_number"):
        frappe.throw("Sales Invoice field custom_kpws_mr_number not found.")

    rows = frappe.get_all(
        "Sales Invoice",
        filters={"patient": ["is", "set"]},
        fields=["name", "patient", "custom_kpws_mr_number"],
        limit=100000,
    )

    updated = 0
    skipped = 0

    for row in rows:
        mr = get_patient_mr_number(row.patient)

        if not mr:
            skipped += 1
            continue

        if row.custom_kpws_mr_number != mr:
            frappe.db.set_value(
                "Sales Invoice",
                row.name,
                "custom_kpws_mr_number",
                mr,
                update_modified=False,
            )
            updated += 1

    frappe.db.commit()

    print("Sales Invoice MR backfill completed.")
    print("Updated:", updated)
    print("Skipped no custom_reference_number:", skipped)


def install():
    _patient_reference_field()
    patch_client_scripts()
    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("DONE: Sales Invoice MR Number now uses Patient.custom_reference_number.")
