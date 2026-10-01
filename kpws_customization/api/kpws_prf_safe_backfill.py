import frappe

DT = "Patient Registration Form"


def _clean_date(value):
    if value in (None, "", "0000-00-00"):
        return None
    return value


def _norm(v):
    return " ".join(str(v or "").strip().lower().split())


def _has_field(dt, fieldname):
    return bool(frappe.get_meta(dt).get_field(fieldname))


def _first(doc, fields):
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
    for f in _patient_mr_fields():
        v = frappe.db.get_value("Patient", patient, f)
        if v not in (None, ""):
            return v
    return ""


def _find_patient_by_mr(mr_number):
    if not mr_number:
        return ""

    mr = str(mr_number).strip()

    if frappe.db.exists("Patient", mr):
        return mr

    for f in _patient_mr_fields():
        patient = frappe.db.get_value("Patient", {f: mr}, "name")
        if patient:
            return patient

    return ""


def _billing_type(patient_doc, customer):
    group = _first(patient_doc, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])

    if not group and customer and frappe.db.exists("Customer", customer):
        group = frappe.db.get_value("Customer", customer, "customer_group") or ""

    txt = _norm(group)

    if "panel" in txt:
        return "Panel"
    if "welfare" in txt:
        return "Welfare"
    return "Cash"


def _patient_detail(patient):
    p = frappe.get_doc("Patient", patient)

    customer = _first(p, ["customer", "custom_patient_customer"])

    return {
        "custom_patient": patient,
        "custom_mr_number": _true_patient_mr(patient),
        "custom_patient_name": _first(p, ["patient_name", "first_name"]) or patient,
        "custom_patient_customer": customer,
        "custom_billing_type": _billing_type(p, customer),
        "custom_gender": _first(p, ["sex", "gender"]),
        "custom_dob": _clean_date(_first(p, ["dob", "date_of_birth"])),
        "custom_blood_group": _first(p, ["blood_group", "custom_blood_group"]),
        "custom_cnic": _first(p, ["cnic", "custom_cnic", "national_id", "custom_national_id"]),
        "custom_mobile": _first(p, ["mobile", "mobile_no", "phone", "custom_mobile_no"]),
        "custom_email": _first(p, ["email", "email_id", "custom_email"]),
        "custom_address": _first(p, ["address", "address_line1", "custom_address"]),
        "custom_religion": _first(p, ["religion", "custom_religion"]),
        "custom_sect": _first(p, ["sect", "section", "custom_sect", "custom_section"]),
        "custom_nationality": _first(p, ["nationality", "custom_nationality"]),
        "custom_swo": _first(p, ["swo", "son_of", "father_name", "custom_swo", "custom_father_name"]),
    }


def _patient_indexes():
    indexes = {
        "by_id": {},
        "by_mr": {},
        "by_customer": {},
        "by_name": {},
        "by_cnic": {},
        "by_mobile": {},
    }

    patient_fields = {df.fieldname for df in frappe.get_meta("Patient").fields}

    fields = ["name"]

    for f in [
        "patient_name",
        "first_name",
        "customer",
        "custom_patient_customer",
        "cnic",
        "custom_cnic",
        "mobile",
        "mobile_no",
        "phone",
        "custom_mobile_no",
    ] + _patient_mr_fields():
        if f in patient_fields and f not in fields:
            fields.append(f)

    def add(index, key, patient):
        key = _norm(key)
        if key:
            index.setdefault(key, set()).add(patient)

    for p in frappe.get_all("Patient", fields=fields, limit=100000):
        indexes["by_id"][_norm(p.name)] = p.name

        for f in _patient_mr_fields():
            if f in p:
                add(indexes["by_mr"], p.get(f), p.name)

        for f in ["customer", "custom_patient_customer"]:
            if f in p:
                add(indexes["by_customer"], p.get(f), p.name)

        for f in ["patient_name", "first_name"]:
            if f in p:
                add(indexes["by_name"], p.get(f), p.name)

        for f in ["cnic", "custom_cnic"]:
            if f in p:
                add(indexes["by_cnic"], p.get(f), p.name)

        for f in ["mobile", "mobile_no", "phone", "custom_mobile_no"]:
            if f in p:
                add(indexes["by_mobile"], p.get(f), p.name)

    return indexes


def _one(index, key):
    matches = index.get(_norm(key)) or set()
    return list(matches)[0] if len(matches) == 1 else ""


def _resolve(row, indexes):
    existing = row.get("custom_patient")
    if existing and frappe.db.exists("Patient", existing):
        return existing, "already_linked"

    mr = row.get("custom_mr_number")
    if mr:
        if _norm(mr) in indexes["by_id"]:
            return indexes["by_id"][_norm(mr)], "patient_id_in_mr"

        p = _one(indexes["by_mr"], mr)
        if p:
            return p, "mr_match"

    for f, idx_name in [
        ("custom_patient_customer", "by_customer"),
        ("custom_cnic", "by_cnic"),
        ("custom_mobile", "by_mobile"),
        ("custom_patient_name", "by_name"),
    ]:
        p = _one(indexes[idx_name], row.get(f))
        if p:
            return p, f"{idx_name}_match"

    return "", "unresolved"


def backfill():
    prf_fields = {df.fieldname for df in frappe.get_meta(DT).fields}
    indexes = _patient_indexes()

    rows = frappe.get_all(
        DT,
        fields=[
            "name",
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_cnic",
            "custom_mobile",
            "purpose",
            "discount_value",
            "custom_panel_customer",
        ],
        limit=100000,
        order_by="modified desc",
    )

    updated = 0
    linked = 0
    corrected_mr = 0
    unresolved = 0
    errors = 0

    for row in rows:
        patient, method = _resolve(row, indexes)

        if not patient:
            unresolved += 1
            continue

        data = _patient_detail(patient)
        updates = {}

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
            if f not in prf_fields:
                continue

            value = data.get(f)

            if f == "custom_dob":
                value = _clean_date(value)

            updates[f] = value

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

        if "custom_kpws_welfare_type" in prf_fields:
            updates["custom_kpws_welfare_type"] = row.get("purpose") or ""

        if "custom_kpws_welfare_percentage" in prf_fields:
            updates["custom_kpws_welfare_percentage"] = float(row.get("discount_value") or 0)

        if "custom_kpws_assigned_panel_customer" in prf_fields:
            updates["custom_kpws_assigned_panel_customer"] = row.get("custom_panel_customer") or ""

        # Remove empty strings for Date fields before DB update.
        if updates.get("custom_dob") in ("", "0000-00-00"):
            updates["custom_dob"] = None

        try:
            frappe.db.set_value(DT, row.name, updates, update_modified=False)
            updated += 1

            if not row.get("custom_patient"):
                linked += 1

            if row.get("custom_mr_number") != updates.get("custom_mr_number"):
                corrected_mr += 1

        except Exception as e:
            errors += 1
            print("ERROR", row.name, "patient", patient, "method", method, "=>", e)

    frappe.db.commit()

    print("Safe backfill completed.")
    print("Forms updated:", updated)
    print("Newly linked to Patient:", linked)
    print("MR corrected:", corrected_mr)
    print("Unresolved:", unresolved)
    print("Errors:", errors)


def audit():
    indexes = _patient_indexes()
    rows = frappe.get_all(
        DT,
        fields=[
            "name",
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_cnic",
            "custom_mobile",
        ],
        limit=100000,
        order_by="modified desc",
    )

    counts = {}
    unresolved = 0

    for row in rows:
        patient, method = _resolve(row, indexes)
        counts[method] = counts.get(method, 0) + 1
        if not patient:
            unresolved += 1

    print("Detected Patient MR fields:", _patient_mr_fields() or "NOT FOUND")
    print("Total PRF:", len(rows))
    print("Unresolved:", unresolved)
    print("")
    for k in sorted(counts):
        print(k, "=>", counts[k])
