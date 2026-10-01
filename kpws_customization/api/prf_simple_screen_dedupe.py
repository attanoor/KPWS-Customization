import frappe


CANDIDATE_DOCTYPES = [
    "Patient Registration Form",
    "Patient Registeration Form",
]


def _get_prf_doctype():
    for dt in CANDIDATE_DOCTYPES:
        if frappe.db.exists("DocType", dt):
            return dt
    frappe.throw("Patient Registration Form DocType not found.")


@frappe.whitelist()
def install():
    doctype = _get_prf_doctype()

    script_name = "KPWS Simple Patient Registration Desk"
    existing = frappe.db.exists("Client Script", script_name)

    if not existing:
        frappe.throw("Client Script not found: KPWS Simple Patient Registration Desk")

    doc = frappe.get_doc("Client Script", existing)
    script = doc.script or ""

    replacements = {
        # Rename the active fields clearly
        'make_select(frm, "Purpose", "purpose", ["Zakat", "Donation"])':
        'make_select(frm, "Purpose / Fund Type", "purpose", ["Zakat", "Donation"])',

        'make_input(frm, "Approved Percentage", "discount_value", "number", false)':
        'make_input(frm, "Approved Coverage Percentage", "discount_value", "number", false)',

        # Remove duplicate hidden mirror fields from visible UI
        '                        ${make_select(frm, "Linked Welfare Type", "custom_kpws_welfare_type", ["Zakat", "Donation"])}\n                        ${make_input(frm, "Linked Welfare Percentage", "custom_kpws_welfare_percentage", "number", false)}':
        '',

        # Remove duplicate percentage from Panel section
        '                        ${make_input(frm, "Panel / Approved Percentage", "discount_value", "number", false)}':
        '',

        # Remove duplicate remarks from Address section
        '                        ${make_input(frm, "General Remarks", "remarks", "textarea", false)}':
        '',

        # Keep remarks only once, with a clearer label
        'make_input(frm, "Internal Remarks", "remarks", "textarea", false)':
        'make_input(frm, "General Remarks", "remarks", "textarea", false)',

        # Update help text
        'Use this section for welfare approval. Percentage will be used as the approved billing discount/coverage percentage.':
        'Use this section to apply Zakat/Donation and approved percentage. These are the active fields used for billing control and Sales Invoice flow.',

        'For Panel patients, assign the panel customer here. The patient master can be updated from the button below.':
        'For Panel patients, assign the Panel Customer here. The same Approved Coverage Percentage above will apply where needed.',
    }

    changes = 0
    for old, new in replacements.items():
        if old in script:
            script = script.replace(old, new)
            changes += 1

    # Add a small note inside Panel section if not already present
    marker = '<div class="kpws-panel-link-control"></div>'
    note = '''
                        <div class="kpws-prf-alert" style="grid-column: span 3;">
                            Panel Customer is assigned here. Approved percentage is entered once above.
                        </div>'''

    if marker in script and "Approved percentage is entered once above" not in script:
        script = script.replace(
            marker,
            marker + note
        )
        changes += 1

    doc.script = script
    doc.dt = doctype

    if doc.meta.has_field("enabled"):
        doc.enabled = 1

    doc.save(ignore_permissions=True)

    frappe.clear_cache(doctype=doctype)
    frappe.db.commit()

    return {
        "ok": True,
        "doctype": doctype,
        "client_script": doc.name,
        "changes_applied": changes,
        "visible_active_fields": [
            "purpose",
            "discount_value",
            "custom_panel_customer",
            "custom_kpws_admin_notes",
            "remarks",
        ],
        "hidden_synced_fields": [
            "custom_kpws_welfare_type",
            "custom_kpws_welfare_percentage",
            "custom_kpws_assigned_panel_customer",
        ],
        "message": "Duplicate Purpose/Percentage/Remarks fields removed from simple PRF UI."
    }
