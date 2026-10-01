import csv
import frappe
from pathlib import Path

DT = "Patient Registration Form"
OUT = "/tmp/kpws_prf_unlinked_report.csv"


def _norm(v):
    return " ".join(str(v or "").strip().lower().split())


def _meta_fields(dt):
    return {df.fieldname for df in frappe.get_meta(dt).fields}


def _db_columns(table):
    rows = frappe.db.sql("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = %s
    """, table, as_dict=True)
    return {r.COLUMN_NAME for r in rows}


def _first_doc_value(doc, fields):
    for f in fields:
        if doc.meta.get_field(f):
            v = doc.get(f)
            if v not in (None, ""):
                return v
    return ""


def _patient_mr_fields():
    meta = frappe.get_meta("Patient")
    fields = []

    preferred = [
        "custom_mr_number",
        "custom_mr_no",
        "mr_number",
        "mr_no",
        "patient_mr_number",
        "custom_patient_mr_number",
    ]

    for f in preferred:
        if meta.get_field(f) and f not in fields:
            fields.append(f)

    for df in meta.fields:
        label = _norm(df.label)
        fname = df.fieldname
        if not fname or fname in fields:
            continue

        if df.fieldtype in ["Data", "Link", "Int"] and (
            label in ["mr number", "mr no", "mr"]
            or ("mr" in label and ("number" in label or "no" in label))
            or "mr_number" in fname
            or "mr_no" in fname
        ):
            fields.append(fname)

    return fields


def _true_patient_mr(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return ""

    for f in _patient_mr_fields():
        v = frappe.db.get_value("Patient", patient, f)
        if v not in (None, ""):
            return v

    return ""


def _patient_detail(patient):
    p = frappe.get_doc("Patient", patient)
    customer = _first_doc_value(p, ["customer", "custom_patient_customer"])

    group = _first_doc_value(p, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])
    if not group and customer and frappe.db.exists("Customer", customer):
        group = frappe.db.get_value("Customer", customer, "customer_group") or ""

    t = _norm(group)
    if "panel" in t:
        billing_type = "Panel"
    elif "welfare" in t:
        billing_type = "Welfare"
    else:
        billing_type = "Cash"

    return {
        "custom_patient": patient,
        "custom_mr_number": _true_patient_mr(patient),
        "custom_patient_name": _first_doc_value(p, ["patient_name", "first_name"]) or patient,
        "custom_patient_customer": customer,
        "custom_billing_type": billing_type,
        "custom_gender": _first_doc_value(p, ["sex", "gender"]),
        "custom_dob": _first_doc_value(p, ["dob", "date_of_birth"]),
        "custom_blood_group": _first_doc_value(p, ["blood_group", "custom_blood_group"]),
        "custom_cnic": _first_doc_value(p, ["cnic", "custom_cnic", "national_id", "custom_national_id"]),
        "custom_mobile": _first_doc_value(p, ["mobile", "mobile_no", "phone", "custom_mobile_no"]),
        "custom_email": _first_doc_value(p, ["email", "email_id", "custom_email"]),
        "custom_address": _first_doc_value(p, ["address", "address_line1", "custom_address"]),
        "custom_religion": _first_doc_value(p, ["religion", "custom_religion"]),
        "custom_sect": _first_doc_value(p, ["sect", "section", "custom_sect", "custom_section"]),
        "custom_nationality": _first_doc_value(p, ["nationality", "custom_nationality"]),
        "custom_swo": _first_doc_value(p, ["swo", "son_of", "father_name", "custom_swo", "custom_father_name"]),
    }


def _build_patient_indexes():
    patient_fields = _meta_fields("Patient")
    mr_fields = _patient_mr_fields()

    fields = ["name"]
    for f in ["patient_name", "first_name", "customer", "custom_patient_customer", "cnic", "custom_cnic", "mobile", "mobile_no", "phone", "custom_mobile_no"]:
        if f in patient_fields and f not in fields:
            fields.append(f)

    for f in mr_fields:
        if f not in fields:
            fields.append(f)

    patients = frappe.get_all("Patient", fields=fields, limit=100000)

    by_patient_id = {}
    by_mr = {}
    by_customer = {}
    by_name = {}
    by_cnic = {}
    by_mobile = {}

    def add(index, key, patient):
        key = _norm(key)
        if not key:
            return
        index.setdefault(key, set()).add(patient)

    for p in patients:
        by_patient_id[_norm(p.name)] = p.name

        for f in mr_fields:
            add(by_mr, p.get(f), p.name)

        for f in ["customer", "custom_patient_customer"]:
            if f in p:
                add(by_customer, p.get(f), p.name)

        for f in ["patient_name", "first_name"]:
            if f in p:
                add(by_name, p.get(f), p.name)

        for f in ["cnic", "custom_cnic"]:
            if f in p:
                add(by_cnic, p.get(f), p.name)

        for f in ["mobile", "mobile_no", "phone", "custom_mobile_no"]:
            if f in p:
                add(by_mobile, p.get(f), p.name)

    return {
        "by_patient_id": by_patient_id,
        "by_mr": by_mr,
        "by_customer": by_customer,
        "by_name": by_name,
        "by_cnic": by_cnic,
        "by_mobile": by_mobile,
        "mr_fields": mr_fields,
    }


def _one_match(index, key):
    matches = index.get(_norm(key)) or set()
    if len(matches) == 1:
        return list(matches)[0]
    return ""


def _get_prf_rows():
    cols = _db_columns("tabPatient Registration Form")

    wanted = [
        "name",
        "custom_patient",
        "patient",
        "custom_mr_number",
        "mr_number",
        "mr_no",
        "custom_patient_name",
        "patient_name",
        "custom_patient_customer",
        "customer",
        "custom_cnic",
        "cnic",
        "custom_mobile",
        "mobile",
        "modified",
    ]

    select_cols = [c for c in wanted if c in cols]
    if "name" not in select_cols:
        select_cols.insert(0, "name")

    sql = "SELECT {0} FROM `tabPatient Registration Form` ORDER BY modified DESC".format(
        ", ".join([f"`{c}`" for c in select_cols])
    )

    return frappe.db.sql(sql, as_dict=True)


def _resolve_patient(row, indexes):
    existing = row.get("custom_patient") or row.get("patient")
    if existing and frappe.db.exists("Patient", existing):
        return existing, "already_linked"

    for f in ["custom_mr_number", "mr_number", "mr_no"]:
        v = row.get(f)
        if not v:
            continue

        # Old bad value may be Patient ID; use it to link, but later MR is corrected from actual MR field.
        if _norm(v) in indexes["by_patient_id"]:
            return indexes["by_patient_id"][_norm(v)], f"patient_id_in_{f}"

        patient = _one_match(indexes["by_mr"], v)
        if patient:
            return patient, f"mr_match_{f}"

    for f in ["custom_patient_customer", "customer"]:
        patient = _one_match(indexes["by_customer"], row.get(f))
        if patient:
            return patient, f"customer_match_{f}"

    for f in ["custom_cnic", "cnic"]:
        patient = _one_match(indexes["by_cnic"], row.get(f))
        if patient:
            return patient, f"cnic_match_{f}"

    for f in ["custom_mobile", "mobile"]:
        patient = _one_match(indexes["by_mobile"], row.get(f))
        if patient:
            return patient, f"mobile_match_{f}"

    for f in ["custom_patient_name", "patient_name"]:
        patient = _one_match(indexes["by_name"], row.get(f))
        if patient:
            return patient, f"name_match_{f}"

    return "", "unresolved"


def audit():
    indexes = _build_patient_indexes()
    rows = _get_prf_rows()

    counts = {}
    unresolved = []

    for row in rows:
        patient, method = _resolve_patient(row, indexes)
        counts[method] = counts.get(method, 0) + 1

        if not patient:
            unresolved.append(row)

    print("Detected Patient MR fields:", indexes["mr_fields"] or "NOT FOUND")
    print("Total Patient Registration Forms:", len(rows))
    print("")
    print("Match summary:")
    for k in sorted(counts):
        print(k, "=>", counts[k])

    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name",
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_cnic",
            "custom_mobile",
        ])
        writer.writeheader()
        for r in unresolved:
            writer.writerow({
                "name": r.get("name"),
                "custom_patient": r.get("custom_patient"),
                "custom_mr_number": r.get("custom_mr_number"),
                "custom_patient_name": r.get("custom_patient_name"),
                "custom_patient_customer": r.get("custom_patient_customer"),
                "custom_cnic": r.get("custom_cnic"),
                "custom_mobile": r.get("custom_mobile"),
            })

    print("")
    print("Unresolved forms:", len(unresolved))
    print("Unresolved report:", OUT)


def backfill():
    indexes = _build_patient_indexes()
    rows = _get_prf_rows()
    prf_fields = _meta_fields(DT)

    updated = 0
    unresolved = 0
    linked = 0
    corrected_mr = 0

    for row in rows:
        patient, method = _resolve_patient(row, indexes)

        if not patient:
            unresolved += 1
            continue

        data = _patient_detail(patient)
        updates = {}

        # Always write key linkage/basic Patient info.
        for f in [
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_billing_type",
            "custom_gender",
            "custom_dob",
            "custom_blood_group",
        ]:
            if f in prf_fields:
                updates[f] = data.get(f)

        # Contact fields only fill if blank, so admin values are preserved.
        for f in [
            "custom_cnic",
            "custom_mobile",
            "custom_email",
            "custom_address",
            "custom_religion",
            "custom_sect",
            "custom_nationality",
            "custom_swo",
        ]:
            if f in prf_fields and not row.get(f) and data.get(f):
                updates[f] = data.get(f)

        # Sync welfare backend fields.
        if "custom_kpws_welfare_type" in prf_fields:
            purpose = frappe.db.get_value(DT, row.name, "purpose") if "purpose" in prf_fields else ""
            updates["custom_kpws_welfare_type"] = purpose or ""

        if "custom_kpws_welfare_percentage" in prf_fields:
            discount_value = frappe.db.get_value(DT, row.name, "discount_value") if "discount_value" in prf_fields else 0
            updates["custom_kpws_welfare_percentage"] = float(discount_value or 0)

        if "custom_kpws_assigned_panel_customer" in prf_fields:
            panel = frappe.db.get_value(DT, row.name, "custom_panel_customer") if "custom_panel_customer" in prf_fields else ""
            updates["custom_kpws_assigned_panel_customer"] = panel or ""

        if updates:
            if not row.get("custom_patient"):
                linked += 1

            if row.get("custom_mr_number") != updates.get("custom_mr_number"):
                corrected_mr += 1

            frappe.db.set_value(DT, row.name, updates, update_modified=False)
            updated += 1

    frappe.db.commit()

    print("Backfill completed.")
    print("Forms updated:", updated)
    print("Newly linked to Patient:", linked)
    print("MR corrected from actual Patient MR field:", corrected_mr)
    print("Unresolved forms:", unresolved)
    print("")
    print("Run audit again to review remaining unresolved forms:")
    print("bench --site kpws.easeinsolutions.com execute kpws_customization.api.kpws_prf_bulk_patient_linker.audit")


def show_unresolved(limit=50):
    indexes = _build_patient_indexes()
    rows = _get_prf_rows()
    shown = 0

    for row in rows:
        patient, method = _resolve_patient(row, indexes)
        if patient:
            continue

        print(row)
        shown += 1

        if shown >= int(limit):
            break

    print("Shown unresolved:", shown)
