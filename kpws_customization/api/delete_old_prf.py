import json
import os
import traceback
import frappe
from frappe.utils import now_datetime


def run():
    doctype = "Patient Registration Form"

    if not frappe.db.exists("DocType", doctype):
        return {
            "ok": False,
            "message": f"DocType not found: {doctype}"
        }

    backup_dir = frappe.get_site_path(
        "private",
        "backups",
        "kpws_patient_registration_form_backups"
    )
    os.makedirs(backup_dir, exist_ok=True)

    backup_file = os.path.join(
        backup_dir,
        f"PRF_backup_before_delete_{now_datetime().strftime('%Y%m%d_%H%M%S')}.json"
    )

    names = frappe.get_all(
        doctype,
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )

    backup_data = []
    for name in names:
        try:
            backup_data.append(frappe.get_doc(doctype, name).as_dict())
        except Exception:
            backup_data.append({
                "name": name,
                "backup_error": traceback.format_exc()
            })

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, default=str, ensure_ascii=False)

    deleted = 0
    failed = []

    for name in names:
        try:
            # Force reset submitted docs to cancelled before delete
            docstatus = frappe.db.get_value(doctype, name, "docstatus")
            if docstatus == 1:
                frappe.db.set_value(
                    doctype,
                    name,
                    "docstatus",
                    2,
                    update_modified=False
                )

            frappe.delete_doc(
                doctype,
                name,
                force=1,
                ignore_permissions=True,
                ignore_on_trash=True
            )

            deleted += 1

            if deleted % 100 == 0:
                frappe.db.commit()
                print(f"Deleted {deleted} / {len(names)}")

        except Exception:
            frappe.db.rollback()
            failed.append({
                "name": name,
                "error": traceback.format_exc()
            })
            print(f"FAILED: {name}")

    frappe.db.commit()

    failed_file = None
    if failed:
        failed_file = os.path.join(
            backup_dir,
            f"PRF_delete_failed_{now_datetime().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(failed_file, "w", encoding="utf-8") as f:
            json.dump(failed, f, indent=2, default=str, ensure_ascii=False)

    remaining = frappe.db.count(doctype)

    return {
        "ok": True,
        "doctype": doctype,
        "found_before_delete": len(names),
        "deleted": deleted,
        "failed": len(failed),
        "remaining": remaining,
        "backup_file": backup_file,
        "failed_file": failed_file,
    }
