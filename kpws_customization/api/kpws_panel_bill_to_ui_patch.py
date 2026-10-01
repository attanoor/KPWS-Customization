import frappe


@frappe.whitelist()
def install():
    name = "KPWS Sales Invoice Patient Billing Control"

    existing = frappe.db.exists("Client Script", name)
    if not existing:
        frappe.throw("Client Script not found: KPWS Sales Invoice Patient Billing Control")

    doc = frappe.get_doc("Client Script", existing)
    script = doc.script or ""

    old = '''
            if (!data.blocked && data.group === "Panel" && data.panel_customer && frm.doc.customer !== data.panel_customer) {
                frm.add_custom_button(__("Set Assigned Panel Customer"), function() {
                    frm.set_value("customer", data.panel_customer);
                }, __("KPWS"));
            }
'''

    new = '''
            if (!data.blocked && data.group === "Panel" && data.panel_customer && frm.doc.customer !== data.panel_customer) {
                frm.set_value("customer", data.panel_customer);

                frappe.show_alert({
                    message: __("Bill To Customer set to assigned Panel Customer: ") + data.panel_customer,
                    indicator: "green"
                }, 8);
            }
'''

    if old in script:
        script = script.replace(old, new)
    elif "Bill To Customer set to assigned Panel Customer" not in script:
        script += new

    doc.script = script
    doc.save(ignore_permissions=True)

    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.commit()

    return "Panel Bill To UI patch installed."
