import os
import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Sales Invoice Standard Patient Flow"
MODULE_PATH = frappe.get_app_path("kpws_customization", "api", "kpws_sales_invoice_final.py")
HOOKS_PATH = frappe.get_app_path("kpws_customization", "hooks.py")


NEW_JS_FUNCTION = r'''
function kpws_si_payment_mode_is(mode, keys) {
    mode = (mode || "").toLowerCase();
    return keys.some(function(k) {
        return mode.includes(k);
    });
}

function kpws_si_rebuild_cash_card_payments(frm, total, ctx) {
    let cash_mode = (ctx && ctx.cash_mode) || "Cash";
    let card_mode = (ctx && ctx.card_mode) || "Credit Card";

    let existing_card_amount = 0;
    let has_wrong_mode = false;

    (frm.doc.payments || []).forEach(function(row) {
        let mop = row.mode_of_payment || "";

        if (kpws_si_payment_mode_is(mop, ["card", "credit"])) {
            existing_card_amount += flt(row.amount || 0);
        } else if (!kpws_si_payment_mode_is(mop, ["cash"])) {
            has_wrong_mode = true;
        }
    });

    // If POS profile filled Donation/Zakat/Panel, reset fully to Cash.
    if (has_wrong_mode) {
        existing_card_amount = 0;
    }

    if (existing_card_amount > total) {
        existing_card_amount = 0;
    }

    let cash_amount = flt(total - existing_card_amount);

    frm.clear_table("payments");

    let cash = frm.add_child("payments");
    cash.mode_of_payment = cash_mode;
    cash.amount = cash_amount;

    // Add credit card row with 0 so operator can split manually if needed.
    let card = frm.add_child("payments");
    card.mode_of_payment = card_mode;
    card.amount = existing_card_amount;

    frm.refresh_field("payments");
}

function kpws_si_apply_payment_split(frm) {
    if (!frm.fields_dict.payments) return;

    let patient_type = frm.doc.custom_kpws_billing_type || "";
    let total = kpws_si_total(frm);
    let ctx = frm.__kpws_context || {};

    if (!total || total <= 0) return;

    if (patient_type === "Panel") {
        frm.clear_table("payments");
        frm.refresh_field("payments");
        return;
    }

    if (patient_type === "Welfare") {
        let pct = flt(frm.doc.custom_kpws_welfare_percentage || 0);
        let purpose = (frm.doc.custom_kpws_welfare_type || "").toLowerCase();

        let sponsor_mode = "";
        if (purpose.includes("zakat")) {
            sponsor_mode = ctx.zakat_mode || "Zakat";
        } else if (purpose.includes("donation")) {
            sponsor_mode = ctx.donation_mode || "Donation";
        }

        let sponsor_amount = flt(total * pct / 100);
        let cash_amount = flt(total - sponsor_amount);

        frm.clear_table("payments");

        if (sponsor_amount > 0 && sponsor_mode) {
            let sponsor = frm.add_child("payments");
            sponsor.mode_of_payment = sponsor_mode;
            sponsor.amount = sponsor_amount;
        }

        if (cash_amount > 0) {
            let cash = frm.add_child("payments");
            cash.mode_of_payment = ctx.cash_mode || "Cash";
            cash.amount = cash_amount;
        }

        frm.refresh_field("payments");
        return;
    }

    // Cash and Walk-in should never use Donation/Zakat/Panel payment modes.
    if (patient_type === "Cash" || frm.doc.custom_is_walkin) {
        kpws_si_rebuild_cash_card_payments(frm, total, ctx);
    }
}
'''


SERVER_APPEND = r'''

# --- KPWS cash/walk-in payment safety patch ---
def _kpws_payment_mode_kind(mode):
    text = str(mode or "").lower()
    if "zakat" in text:
        return "zakat"
    if "donation" in text:
        return "donation"
    if "panel" in text:
        return "panel"
    if "card" in text or "credit" in text:
        return "card"
    if "cash" in text:
        return "cash"
    return "other"


def _kpws_find_mode(names):
    for name in names:
        if frappe.db.exists("Mode of Payment", name):
            return name

    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=100)
    for row in rows:
        text = row.name.lower()
        for name in names:
            if name.lower() in text:
                return row.name

    return names[0]


def before_validate_sales_invoice_payment_cleanup(doc, method=None):
    patient_type = doc.get("custom_kpws_billing_type") or ""

    # For Cash and Walk-in, remove Donation/Zakat/Panel rows.
    if patient_type == "Cash" or doc.get("custom_is_walkin"):
        total = float(doc.get("rounded_total") or doc.get("grand_total") or doc.get("net_total") or 0)
        if total <= 0:
            return

        cash_mode = _kpws_find_mode(["Cash"])
        card_mode = _kpws_find_mode(["Credit Card", "Card"])

        card_amount = 0
        has_wrong_mode = False

        for row in list(doc.get("payments") or []):
            kind = _kpws_payment_mode_kind(row.mode_of_payment)
            if kind == "card":
                card_amount += float(row.amount or 0)
            elif kind != "cash":
                has_wrong_mode = True

        if has_wrong_mode or card_amount > total:
            card_amount = 0

        cash_amount = total - card_amount

        doc.set("payments", [])

        doc.append("payments", {
            "mode_of_payment": cash_mode,
            "amount": cash_amount,
        })

        # Keep Credit Card available only if operator actually entered a card amount.
        if card_amount > 0:
            doc.append("payments", {
                "mode_of_payment": card_mode,
                "amount": card_amount,
            })

    # Welfare should not accidentally keep old POS profile donation rows beyond calculated split.
    if patient_type == "Welfare":
        total = float(doc.get("rounded_total") or doc.get("grand_total") or doc.get("net_total") or 0)
        pct = float(doc.get("custom_kpws_welfare_percentage") or 0)
        purpose = str(doc.get("custom_kpws_welfare_type") or "").lower()

        if total > 0 and pct > 0 and purpose:
            sponsor_mode = _kpws_find_mode(["Zakat"]) if "zakat" in purpose else _kpws_find_mode(["Donation"])
            cash_mode = _kpws_find_mode(["Cash"])

            sponsor_amount = total * pct / 100
            cash_amount = total - sponsor_amount

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
'''


def replace_js_function(script):
    marker = "function kpws_si_apply_payment_split(frm)"
    start = script.find(marker)
    if start == -1:
        return script + "\n\n" + NEW_JS_FUNCTION + "\n"

    brace_start = script.find("{", start)
    if brace_start == -1:
        return script + "\n\n" + NEW_JS_FUNCTION + "\n"

    depth = 0
    end = None

    for i in range(brace_start, len(script)):
        ch = script[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if not end:
        return script + "\n\n" + NEW_JS_FUNCTION + "\n"

    # Also remove old helper if this patch was applied before.
    prefix = script[:start]
    suffix = script[end:]

    helper_marker = "function kpws_si_payment_mode_is(mode, keys)"
    helper_start = prefix.find(helper_marker)
    if helper_start != -1:
        prefix = prefix[:helper_start]

    return prefix.rstrip() + "\n\n" + NEW_JS_FUNCTION + "\n\n" + suffix.lstrip()


def patch_client_script():
    if not frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        raise Exception(f"Client Script not found: {CLIENT_SCRIPT_NAME}")

    doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
    doc.script = replace_js_function(doc.script or "")

    # Add payment cleanup also on POS Profile change because ERPNext may reload payment modes from POS profile.
    if "pos_profile(frm)" not in doc.script:
        doc.script = doc.script.replace(
            "patient(frm) {",
            "pos_profile(frm) {\n        setTimeout(() => kpws_si_apply_payment_split(frm), 700);\n    },\n    patient(frm) {",
        )

    doc.enabled = 1
    doc.save(ignore_permissions=True)
    print("Updated Client Script:", CLIENT_SCRIPT_NAME)


def patch_server_module():
    text = open(MODULE_PATH).read()

    if "before_validate_sales_invoice_payment_cleanup" not in text:
        with open(MODULE_PATH, "a") as f:
            f.write(SERVER_APPEND)
        print("Added server payment cleanup function")
    else:
        print("Server payment cleanup function already exists")


def patch_hooks():
    text = open(HOOKS_PATH).read()
    method = "kpws_customization.api.kpws_sales_invoice_final.before_validate_sales_invoice_payment_cleanup"

    if method not in text:
        text += f"""

# KPWS payment cleanup before save
doc_events = globals().get("doc_events", {{}})
doc_events.setdefault("Sales Invoice", {{}})
doc_events["Sales Invoice"].setdefault("before_validate", [])
if isinstance(doc_events["Sales Invoice"]["before_validate"], str):
    doc_events["Sales Invoice"]["before_validate"] = [doc_events["Sales Invoice"]["before_validate"]]
if "{method}" not in doc_events["Sales Invoice"]["before_validate"]:
    doc_events["Sales Invoice"]["before_validate"].append("{method}")
"""
        open(HOOKS_PATH, "w").write(text)
        print("Added before_validate payment cleanup hook")
    else:
        print("before_validate payment cleanup hook already exists")


def run():
    patch_client_script()
    patch_server_module()
    patch_hooks()
    frappe.db.commit()
    frappe.clear_cache()
    print("")
    print("DONE: Cash/Walk-in payments now restricted to Cash and Credit Card only.")

