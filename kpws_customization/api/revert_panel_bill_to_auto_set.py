import re
import shutil
from pathlib import Path
import frappe
from frappe.utils import now_datetime


def _backup_file(path):
    backup_dir = frappe.get_site_path("private", "backups", "kpws_revert_backups")
    Path(backup_dir).mkdir(parents=True, exist_ok=True)

    backup = Path(backup_dir) / f"{Path(path).name}.before_revert_panel_billto_{now_datetime().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(path, backup)
    return str(backup)


@frappe.whitelist()
def run():
    import kpws_customization

    app_dir = Path(kpws_customization.__file__).parent
    hooks_file = app_dir / "hooks.py"
    invoice_control_file = app_dir / "api" / "kpws_patient_invoice_control.py"

    backups = []

    # 1) Remove the before_validate hook that auto-applied panel customer.
    if hooks_file.exists():
        backups.append(_backup_file(hooks_file))

        hooks = hooks_file.read_text()

        hooks = re.sub(
            r'\n?# KPWS Panel patient must bill to assigned Panel Customer\s*\n'
            r'_kpws_add_si_doc_event\(\s*'
            r'"Sales Invoice",\s*'
            r'"before_validate",\s*'
            r'"kpws_customization\.api\.kpws_patient_invoice_control\.apply_panel_customer_to_sales_invoice"\s*'
            r'\)\s*\n?',
            "\n",
            hooks,
            flags=re.S,
        )

        # Extra safety: remove only that handler call if comment formatting changed.
        hooks = hooks.replace(
            '''_kpws_add_si_doc_event(
    "Sales Invoice",
    "before_validate",
    "kpws_customization.api.kpws_patient_invoice_control.apply_panel_customer_to_sales_invoice"
)
''',
            "",
        )

        hooks_file.write_text(hooks)

    # 2) Make the function a no-op in case any old hook entry is still cached somewhere.
    if invoice_control_file.exists():
        backups.append(_backup_file(invoice_control_file))

        text = invoice_control_file.read_text()

        if "REVERTED_PANEL_BILL_TO_AUTO_SET_NOOP" not in text:
            text += '''

# REVERTED_PANEL_BILL_TO_AUTO_SET_NOOP
def apply_panel_customer_to_sales_invoice(doc, method=None):
    """
    Reverted:
    Do not automatically change Sales Invoice Customer to Panel Customer.
    The UI/status control may still warn users, but it will not auto-set customer.
    """
    return
'''
            invoice_control_file.write_text(text)

    # 3) Remove frontend auto-setting from Sales Invoice client script.
    script_name = "KPWS Sales Invoice Patient Billing Control"
    existing = frappe.db.exists("Client Script", script_name)

    client_script_updated = False

    if existing:
        doc = frappe.get_doc("Client Script", existing)
        script = doc.script or ""

        original_script = script

        # Remove the auto-set alert block added by the last patch.
        script = re.sub(
            r'if\s*\(\s*!data\.blocked\s*&&\s*data\.group\s*===\s*"Panel"\s*&&\s*data\.panel_customer\s*&&\s*frm\.doc\.customer\s*!==\s*data\.panel_customer\s*\)\s*\{\s*'
            r'frm\.set_value\(\s*"customer"\s*,\s*data\.panel_customer\s*\)\s*;\s*'
            r'frappe\.show_alert\(\s*\{[\s\S]*?Bill To Customer set to assigned Panel Customer[\s\S]*?\}\s*,\s*8\s*\)\s*;\s*'
            r'\}',
            '',
            script,
            flags=re.S,
        )

        # If the old manual button is missing, add it back inside the patient status callback.
        if "Set Assigned Panel Customer" not in script and "kpws_si_render_patient_status(frm, data);" in script:
            insert_after = "kpws_si_render_patient_status(frm, data);"
            manual_button = '''
            if (!data.blocked && data.group === "Panel" && data.panel_customer && frm.doc.customer !== data.panel_customer) {
                frm.add_custom_button(__("Set Assigned Panel Customer"), function () {
                    frm.set_value("customer", data.panel_customer);
                }, __("KPWS"));
            }
'''
            script = script.replace(insert_after, insert_after + "\n" + manual_button, 1)

        if script != original_script:
            doc.script = script
            doc.save(ignore_permissions=True)
            client_script_updated = True

    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.commit()

    return {
        "ok": True,
        "message": "Panel bill-to auto-set reverted.",
        "backups": backups,
        "client_script_updated": client_script_updated,
        "what_changed": [
            "Removed Sales Invoice before_validate auto customer assignment hook.",
            "Neutralized apply_panel_customer_to_sales_invoice as no-op.",
            "Removed frontend automatic customer set/alert.",
            "Restored manual Set Assigned Panel Customer button where possible.",
        ],
    }
