import frappe

CLIENT_SCRIPT_NAME = "KPWS FORCE Patient Panel Customer Only"


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def panel_customer_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT
            name,
            customer_name
        FROM `tabCustomer`
        WHERE
            IFNULL(custom_is_panel, 0) = 1
            AND IFNULL(disabled, 0) = 0
            AND (
                name LIKE %(txt)s
                OR customer_name LIKE %(txt)s
            )
        ORDER BY customer_name, name
        LIMIT %(start)s, %(page_len)s
    """, {
        "txt": f"%{txt or ''}%",
        "start": int(start or 0),
        "page_len": int(page_len or 20),
    })


def customer_is_active_panel(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False

    row = frappe.db.get_value(
        "Customer",
        customer,
        ["custom_is_panel", "disabled", "customer_name"],
        as_dict=True,
    )

    return bool(row and int(row.custom_is_panel or 0) == 1 and int(row.disabled or 0) == 0)


def show_panel_customers():
    print("")
    print("Enabled panel customers:")
    rows = frappe.get_all(
        "Customer",
        filters={"custom_is_panel": 1, "disabled": 0},
        fields=["name", "customer_name", "disabled"],
        order_by="customer_name asc",
        limit=100,
    )

    for row in rows:
        print("-", row.name, "|", row.customer_name, "| disabled:", row.disabled)

    print("")
    print("Disabled panel customers:")
    disabled_rows = frappe.get_all(
        "Customer",
        filters={"custom_is_panel": 1, "disabled": 1},
        fields=["name", "customer_name", "disabled"],
        order_by="customer_name asc",
        limit=100,
    )

    for row in disabled_rows:
        print("-", row.name, "|", row.customer_name, "| disabled:", row.disabled)

    if not rows and not disabled_rows:
        print("No panel customers found.")


def show_customer(customer="TSF-26"):
    if not frappe.db.exists("Customer", customer):
        print("Customer not found:", customer)
        return

    row = frappe.db.get_value(
        "Customer",
        customer,
        ["name", "customer_name", "customer_group", "custom_is_panel", "disabled"],
        as_dict=True,
    )

    print(row)


def enable_customer(customer="TSF-26"):
    if not frappe.db.exists("Customer", customer):
        frappe.throw(f"Customer not found: {customer}")

    frappe.db.set_value("Customer", customer, "disabled", 0, update_modified=True)
    frappe.db.commit()

    print(f"Enabled Customer: {customer}")


def patch_patient_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient", {
    setup(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    onload(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    refresh(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    customer_group(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    custom_patient_billing_type(frm) {
        kpws_force_panel_customer_setup(frm);
    }
});

function kpws_force_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_force_is_panel_patient(frm) {
    let txt = [
        frm.doc.customer_group || "",
        frm.doc.custom_patient_billing_type || ""
    ].join(" ").toLowerCase();

    return txt.includes("panel");
}

function kpws_force_panel_customer_setup(frm) {
    let is_panel = kpws_force_is_panel_patient(frm);

    if (kpws_force_has(frm, "custom_panel_customer")) {
        frm.set_query("custom_panel_customer", function() {
            return {
                query: "kpws_customization.api.kpws_active_panel_customer_fix.panel_customer_query"
            };
        });

        frm.set_df_property("custom_panel_customer", "label", "Panel Name");
        frm.set_df_property("custom_panel_customer", "options", "Customer");
        frm.toggle_display("custom_panel_customer", is_panel);
        frm.toggle_reqd("custom_panel_customer", is_panel);
    }

    if (kpws_force_has(frm, "panel_name")) {
        frm.toggle_display("panel_name", false);
        frm.toggle_reqd("panel_name", false);
    }

    if (!is_panel && kpws_force_has(frm, "custom_panel_customer") && frm.doc.custom_panel_customer) {
        frm.set_value("custom_panel_customer", "");
    }
}
'''

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Patient"
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Patient panel query script")
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Patient",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Patient panel query script")


def install():
    patch_patient_client_script()
    frappe.db.commit()
    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache(doctype="Customer")

    show_customer("TSF-26")
    show_panel_customers()

    print("")
    print("DONE: Patient Panel Name now lists only enabled Customer records with Is Panel checked.")
