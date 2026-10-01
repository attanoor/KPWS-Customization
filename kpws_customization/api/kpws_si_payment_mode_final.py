import frappe

UNIFIED_MODULE = frappe.get_app_path("kpws_customization", "api", "kpws_si_unified_flow.py")
HOOKS_PATH = frappe.get_app_path("kpws_customization", "hooks.py")
CLIENT_SCRIPT_NAME = "KPWS FINAL Unified Sales Invoice Flow"


SERVER_APPEND = r'''

# --- KPWS FINAL payment mode enforcement ---
def _kpws_final_payment_mode(names):
    for name in names:
        if frappe.db.exists("Mode of Payment", name):
            return name

    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=200)
    for row in rows:
        low = row.name.lower()
        for name in names:
            if name.lower() in low:
                return row.name

    return names[0] if names else ""


def _kpws_final_invoice_total(doc):
    return float(doc.get("rounded_total") or doc.get("grand_total") or doc.get("net_total") or 0)


def _kpws_final_latest_welfare_for_invoice(doc):
    patient = doc.get("patient")
    if not patient:
        return {}

    try:
        return _latest_welfare(patient) or {}
    except Exception:
        return {}


def enforce_payment_modes_on_validate(doc, method=None):
    patient_type = doc.get("custom_kpws_billing_type") or ""
    total = _kpws_final_invoice_total(doc)

    if total <= 0:
        return

    cash_mode = _kpws_final_payment_mode(["Cash"])
    card_mode = _kpws_final_payment_mode(["Credit Card", "Card"])
    panel_mode = _kpws_final_payment_mode(["Panel"])
    zakat_mode = _kpws_final_payment_mode(["Zakat"])
    donation_mode = _kpws_final_payment_mode(["Donation"])

    # Cash / Walk-in = Cash + optional Credit Card only.
    if patient_type == "Cash" or doc.get("custom_is_walkin"):
        existing_card_amount = 0

        for row in doc.get("payments") or []:
            mode = str(row.mode_of_payment or "").lower()
            if "card" in mode or "credit" in mode:
                existing_card_amount += float(row.amount or 0)

        if existing_card_amount > total:
            existing_card_amount = 0

        cash_amount = total - existing_card_amount

        doc.set("payments", [])
        doc.append("payments", {
            "mode_of_payment": cash_mode,
            "amount": cash_amount,
        })

        if existing_card_amount > 0:
            doc.append("payments", {
                "mode_of_payment": card_mode,
                "amount": existing_card_amount,
            })

        return

    # Panel = Panel mode only.
    if patient_type == "Panel":
        doc.set("payments", [])
        doc.append("payments", {
            "mode_of_payment": panel_mode,
            "amount": total,
        })
        return

    # Welfare = based on latest Patient Registration Form.
    if patient_type == "Welfare":
        welfare = _kpws_final_latest_welfare_for_invoice(doc)

        welfare_type = (
            doc.get("custom_kpws_welfare_type")
            or welfare.get("type")
            or welfare.get("welfare_type")
            or ""
        )

        percentage = doc.get("custom_kpws_welfare_percentage")
        if percentage in (None, ""):
            percentage = welfare.get("percentage") or welfare.get("welfare_percentage") or 0

        percentage = float(percentage or 0)

        if percentage < 0:
            percentage = 0

        if percentage > 100:
            percentage = 100

        sponsor_amount = total * percentage / 100
        cash_amount = total - sponsor_amount

        sponsor_mode = zakat_mode if "zakat" in str(welfare_type).lower() else donation_mode

        doc.set("payments", [])

        if sponsor_amount > 0:
            doc.append("payments", {
                "mode_of_payment": sponsor_mode,
                "amount": sponsor_amount,
            })

        if cash_amount > 0:
            doc.append("payments", {
                "mode_of_payment": cash_mode,
                "amount": cash_amount,
            })

        return
'''


CLIENT_PAYMENT_FUNCTION = r'''
function kpws_unified_apply_payments(frm) {
    if (!kpws_unified_has(frm, "payments")) return;

    let total = kpws_unified_total(frm);
    if (!total || total <= 0) return;

    let ctx = frm.__kpws_unified_context || {};
    let patient_type = frm.doc.custom_kpws_billing_type || "";

    let cash_mode = ctx.cash_mode || "Cash";
    let card_mode = ctx.card_mode || "Credit Card";
    let panel_mode = ctx.panel_mode || "Panel";
    let zakat_mode = ctx.zakat_mode || "Zakat";
    let donation_mode = ctx.donation_mode || "Donation";

    // Cash / Walk-in: only Cash + Credit Card.
    if (patient_type === "Cash" || frm.doc.custom_is_walkin) {
        let card_amount = 0;

        (frm.doc.payments || []).forEach(function(row) {
            let mop = (row.mode_of_payment || "").toLowerCase();
            if (mop.includes("card") || mop.includes("credit")) {
                card_amount += flt(row.amount || 0);
            }
        });

        if (card_amount > total) {
            card_amount = 0;
        }

        frm.clear_table("payments");

        let cash = frm.add_child("payments");
        cash.mode_of_payment = cash_mode;
        cash.amount = flt(total - card_amount);

        let card = frm.add_child("payments");
        card.mode_of_payment = card_mode;
        card.amount = card_amount;

        frm.refresh_field("payments");
        return;
    }

    // Panel: only Panel mode.
    if (patient_type === "Panel") {
        frm.clear_table("payments");

        let panel = frm.add_child("payments");
        panel.mode_of_payment = panel_mode;
        panel.amount = total;

        frm.refresh_field("payments");
        return;
    }

    // Welfare: split according to Patient Registration Form.
    if (patient_type === "Welfare") {
        let pct = flt(frm.doc.custom_kpws_welfare_percentage || 0);
        let welfare_type = (frm.doc.custom_kpws_welfare_type || "").toLowerCase();

        if (pct < 0) pct = 0;
        if (pct > 100) pct = 100;

        let sponsor_mode = welfare_type.includes("zakat") ? zakat_mode : donation_mode;
        let sponsor_amount = flt(total * pct / 100);
        let cash_amount = flt(total - sponsor_amount);

        frm.clear_table("payments");

        if (sponsor_amount > 0) {
            let sponsor = frm.add_child("payments");
            sponsor.mode_of_payment = sponsor_mode;
            sponsor.amount = sponsor_amount;
        }

        if (cash_amount > 0) {
            let cash = frm.add_child("payments");
            cash.mode_of_payment = cash_mode;
            cash.amount = cash_amount;
        }

        frm.refresh_field("payments");
        return;
    }
}
'''


def replace_js_function(script, function_name, replacement):
    marker = f"function {function_name}"
    start = script.find(marker)

    if start == -1:
        return script.rstrip() + "\n\n" + replacement + "\n"

    brace_start = script.find("{", start)
    if brace_start == -1:
        return script.rstrip() + "\n\n" + replacement + "\n"

    depth = 0
    end = None

    for i in range(brace_start, len(script)):
        char = script[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if not end:
        return script.rstrip() + "\n\n" + replacement + "\n"

    return script[:start].rstrip() + "\n\n" + replacement + "\n\n" + script[end:].lstrip()


def patch_unified_server_module():
    text = open(UNIFIED_MODULE).read()

    marker = "# --- KPWS FINAL payment mode enforcement ---"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n\n" + SERVER_APPEND
        print("Replaced existing payment enforcement block.")
    else:
        text = text.rstrip() + "\n\n" + SERVER_APPEND
        print("Added payment enforcement block.")

    open(UNIFIED_MODULE, "w").write(text)


def patch_unified_client_script():
    if not frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        frappe.throw(f"Client Script not found: {CLIENT_SCRIPT_NAME}")

    doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
    script = doc.script or ""

    script = replace_js_function(
        script,
        "kpws_unified_apply_payments(frm)",
        CLIENT_PAYMENT_FUNCTION,
    )

    # Make sure payment recalculates when payment-relevant fields change.
    needed_events = [
        "custom_kpws_welfare_type(frm)",
        "custom_kpws_welfare_percentage(frm)",
        "pos_profile(frm)",
    ]

    for event in needed_events:
        if event not in script:
            script = script.replace(
                "grand_total(frm) {",
                f"""{event} {{
        kpws_unified_payment_later(frm);
    }},
    grand_total(frm) {{""",
                )

    doc.script = script
    doc.enabled = 1
    doc.save(ignore_permissions=True)

    print("Updated unified client payment function.")


def patch_hooks():
    text = open(HOOKS_PATH).read()
    method = "kpws_customization.api.kpws_si_unified_flow.enforce_payment_modes_on_validate"

    block = f'''

# KPWS final Sales Invoice payment mode enforcement
doc_events = globals().get("doc_events", {{}})
doc_events.setdefault("Sales Invoice", {{}})
doc_events["Sales Invoice"].setdefault("before_validate", [])
if isinstance(doc_events["Sales Invoice"]["before_validate"], str):
    doc_events["Sales Invoice"]["before_validate"] = [doc_events["Sales Invoice"]["before_validate"]]
if "{method}" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("{method}")
'''

    if method not in text:
        open(HOOKS_PATH, "w").write(text.rstrip() + "\n" + block + "\n")
        print("Added before_validate payment hook.")
    else:
        print("Payment hook already exists.")


def install():
    patch_unified_server_module()
    patch_unified_client_script()
    patch_hooks()

    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("DONE: Mode of Payment rules installed.")
    print("Cash => Cash + Credit Card")
    print("Panel => Panel")
    print("Welfare => Zakat/Donation percentage + Cash balance")
