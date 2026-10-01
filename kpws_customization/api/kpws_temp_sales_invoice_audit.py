import frappe
import os
import re

DT = "Sales Invoice"

KEYWORDS = [
    "patient", "walk", "walkin", "walk-in", "mr", "welfare", "zakat",
    "donation", "panel", "kpws", "pos", "payment", "customer",
    "price", "billing"
]

def line(title):
    print("")
    print("=" * 110)
    print(title)
    print("=" * 110)

def yesno(v):
    return "YES" if v else "NO"

def contains_keyword(*values):
    text = " ".join([str(v or "") for v in values]).lower()
    return any(k in text for k in KEYWORDS)

def print_meta_fields():
    line("1) SALES INVOICE META FIELDS MATCHING PATIENT / PANEL / WELFARE / POS / PAYMENT KEYWORDS")

    meta = frappe.get_meta(DT)
    for df in meta.fields:
        if contains_keyword(df.fieldname, df.label, df.fieldtype, df.options):
            print(
                str(df.idx).rjust(3),
                "| fieldname:", str(df.fieldname).ljust(42),
                "| label:", str(df.label).ljust(35),
                "| type:", str(df.fieldtype).ljust(14),
                "| options:", str(df.options or "").ljust(28),
                "| hidden:", df.hidden,
                "| reqd:", df.reqd,
                "| ro:", df.read_only,
            )

def print_standard_patient_field():
    line("2) STANDARD HEALTHCARE PATIENT FIELD CHECK")

    meta = frappe.get_meta(DT)
    for fname in ["patient", "patient_name", "ref_practitioner", "healthcare_service_unit"]:
        df = meta.get_field(fname)
        if df:
            print(fname, "FOUND", "| label:", df.label, "| type:", df.fieldtype, "| hidden:", df.hidden, "| reqd:", df.reqd, "| read_only:", df.read_only)
        else:
            print(fname, "MISSING")

    print("")
    custom_patient = meta.get_field("custom_patient")
    print("custom_patient duplicate field:", "FOUND" if custom_patient else "NOT FOUND")

def print_custom_fields():
    line("3) SALES INVOICE CUSTOM FIELD RECORDS")

    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": DT},
        fields=[
            "name", "fieldname", "label", "fieldtype", "options",
            "insert_after", "hidden", "reqd", "read_only", "depends_on"
        ],
        order_by="fieldname asc"
    )

    if not rows:
        print("No Custom Field records found for Sales Invoice.")
        return

    for r in rows:
        if contains_keyword(r.fieldname, r.label, r.fieldtype, r.options, r.insert_after):
            print(
                "Custom Field:", r.name,
                "| fieldname:", r.fieldname,
                "| label:", r.label,
                "| type:", r.fieldtype,
                "| options:", r.options,
                "| insert_after:", r.insert_after,
                "| hidden:", r.hidden,
                "| reqd:", r.reqd,
                "| ro:", r.read_only,
                "| depends:", r.depends_on,
            )

def print_property_setters():
    line("4) SALES INVOICE PROPERTY SETTERS")

    rows = frappe.get_all(
        "Property Setter",
        filters={"doc_type": DT},
        fields=[
            "name", "doctype_or_field", "field_name", "property",
            "value", "property_type"
        ],
        order_by="field_name asc"
    )

    if not rows:
        print("No Property Setters found for Sales Invoice.")
        return

    for r in rows:
        if contains_keyword(r.field_name, r.property, r.value):
            print(
                "Property Setter:", r.name,
                "| field:", r.field_name,
                "| property:", r.property,
                "| value:", r.value,
                "| type:", r.property_type,
            )

def print_client_scripts():
    line("5) SALES INVOICE CLIENT SCRIPTS")

    if not frappe.db.exists("DocType", "Client Script"):
        print("Client Script DocType not found.")
        return

    rows = frappe.get_all(
        "Client Script",
        filters={"dt": DT},
        fields=["name", "enabled", "dt", "view", "script"],
        order_by="name asc"
    )

    if not rows:
        print("No Client Scripts found for Sales Invoice.")
        return

    for r in rows:
        script = r.script or ""
        print("")
        print("Client Script:", r.name, "| enabled:", r.enabled, "| view:", r.view)
        matches = []
        for k in KEYWORDS:
            if k in script.lower() or k in (r.name or "").lower():
                matches.append(k)
        print("Matched keywords:", ", ".join(sorted(set(matches))) if matches else "-")

        # Print important lines only
        lines = script.splitlines()
        for i, l in enumerate(lines, start=1):
            if contains_keyword(l):
                print("  L" + str(i).rjust(3), l[:220])

def print_db_columns():
    line("6) SALES INVOICE DATABASE COLUMNS MATCHING KEYWORDS")

    rows = frappe.db.sql("""
        SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'tabSales Invoice'
        ORDER BY ORDINAL_POSITION
    """, as_dict=True)

    for r in rows:
        if contains_keyword(r.COLUMN_NAME):
            print(
                r.COLUMN_NAME.ljust(45),
                "|", str(r.COLUMN_TYPE).ljust(25),
                "| nullable:", r.IS_NULLABLE,
                "| default:", r.COLUMN_DEFAULT,
            )

def print_hooks_file():
    line("7) kpws_customization/hooks.py SALES INVOICE REFERENCES")

    try:
        hooks_path = frappe.get_app_path("kpws_customization", "hooks.py")
    except Exception as e:
        print("Could not find kpws_customization hooks.py:", e)
        return

    print("Hooks path:", hooks_path)

    if not os.path.exists(hooks_path):
        print("hooks.py does not exist.")
        return

    with open(hooks_path, "r") as f:
        lines = f.readlines()

    for i, l in enumerate(lines, start=1):
        if "Sales Invoice" in l or "sales_invoice" in l.lower() or "kpws_sales" in l.lower() or "patient_flow" in l.lower():
            print("L" + str(i).rjust(4), l.rstrip())

def print_code_search():
    line("8) CODE FILES CONTAINING SALES INVOICE / PATIENT FLOW REFERENCES")

    try:
        app_path = frappe.get_app_path("kpws_customization")
    except Exception as e:
        print("Could not find app path:", e)
        return

    matches = []
    for root, dirs, files in os.walk(app_path):
        # skip pycache and node style dirs
        dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "node_modules"]]

        for fn in files:
            if not fn.endswith((".py", ".js")):
                continue

            path = os.path.join(root, fn)
            try:
                text = open(path, "r", errors="ignore").read()
            except Exception:
                continue

            low = text.lower()
            if "sales invoice" in low or "sales_invoice" in low or "custom_patient" in low or "welfare" in low or "panel" in low:
                rel = os.path.relpath(path, app_path)
                score = 0
                for k in ["sales invoice", "sales_invoice", "custom_patient", "welfare", "panel", "patient"]:
                    score += low.count(k)
                matches.append((score, rel))

    for score, rel in sorted(matches, reverse=True)[:80]:
        print(str(score).rjust(4), rel)

def print_reference_master_data():
    line("9) REFERENCE MASTER DATA: POS PROFILES / MODES / PRICE LISTS")

    if frappe.db.exists("DocType", "POS Profile"):
        print("")
        print("POS Profiles:")
        for r in frappe.get_all("POS Profile", fields=["name", "disabled"], order_by="name asc", limit=100):
            if contains_keyword(r.name) or r.name:
                print(" -", r.name, "| disabled:", r.disabled)

    if frappe.db.exists("DocType", "Mode of Payment"):
        print("")
        print("Modes of Payment:")
        for r in frappe.get_all("Mode of Payment", fields=["name", "enabled"], order_by="name asc", limit=100):
            if contains_keyword(r.name) or r.name.lower() in ["cash", "credit card", "card"]:
                print(" -", r.name, "| enabled:", r.enabled)

    if frappe.db.exists("DocType", "Price List"):
        print("")
        print("Price Lists:")
        for r in frappe.get_all("Price List", fields=["name", "enabled"], order_by="name asc", limit=100):
            if contains_keyword(r.name) or r.name.startswith(("SPW", "SPP")):
                print(" -", r.name, "| enabled:", r.enabled)

def print_prf_relevant_fields():
    line("10) PATIENT REGISTRATION FORM FIELDS USED FOR WELFARE LOOKUP")

    dt = "Patient Registration Form"
    if not frappe.db.exists("DocType", dt):
        print(dt, "not found.")
        return

    meta = frappe.get_meta(dt)
    wanted = [
        "patient", "custom_patient",
        "purpose", "discount_value",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ]

    for f in wanted:
        df = meta.get_field(f)
        if df:
            print(f, "FOUND", "| label:", df.label, "| type:", df.fieldtype, "| hidden:", df.hidden, "| reqd:", df.reqd)
        else:
            print(f, "MISSING")

def print_patient_relevant_fields():
    line("11) PATIENT FIELDS USED FOR SALES INVOICE LOOKUP")

    dt = "Patient"
    if not frappe.db.exists("DocType", dt):
        print(dt, "not found.")
        return

    meta = frappe.get_meta(dt)
    wanted = [
        "name", "patient_name", "customer", "customer_group",
        "custom_patient_billing_type",
        "custom_panel_customer", "panel_name",
        "custom_mr_number", "mr_number", "uid", "patient_id",
    ]

    for f in wanted:
        df = meta.get_field(f)
        if df:
            print(f, "FOUND", "| label:", df.label, "| type:", df.fieldtype, "| hidden:", df.hidden, "| reqd:", df.reqd)
        elif f == "name":
            print("name SYSTEM FIELD")
        else:
            print(f, "MISSING")

def run():
    print("KPWS SALES INVOICE READ-ONLY AUDIT")
    print("Site:", frappe.local.site)
    print("DB:", frappe.conf.db_name)

    print_standard_patient_field()
    print_meta_fields()
    print_custom_fields()
    print_property_setters()
    print_client_scripts()
    print_db_columns()
    print_hooks_file()
    print_code_search()
    print_reference_master_data()
    print_prf_relevant_fields()
    print_patient_relevant_fields()

    line("AUDIT COMPLETE")
    print("This script made NO changes.")
