from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_ADMIN_SETTINGS_RETURN_PRINT_V20_PATCH"


SERVER_PATCH = r'''

# KPWS_ADMIN_SETTINGS_RETURN_PRINT_V20_PATCH

def _kpws_is_administrator_user():
    return frappe.session.user == "Administrator"


def _kpws_require_administrator_user():
    if not _kpws_is_administrator_user():
        frappe.throw(_("Only Administrator user can access Pharmacy POS Settings."), frappe.PermissionError)


def _kpws_group_return_print_format(settings, group):
    group = group or "Cash"

    if group == "Walk-in":
        return (
            settings.get("walkin_return_print_format")
            or settings.get("cash_return_print_format")
            or settings.get("cash_print_format")
            or settings.get("print_format")
        )

    if group == "Panel":
        return (
            settings.get("panel_return_print_format")
            or settings.get("panel_print_format")
            or settings.get("print_format")
        )

    if group == "Welfare":
        return (
            settings.get("welfare_return_print_format")
            or settings.get("welfare_print_format")
            or settings.get("print_format")
        )

    return (
        settings.get("cash_return_print_format")
        or settings.get("cash_print_format")
        or settings.get("print_format")
    )


def _kpws_get_return_print_format(settings, group):
    return _kpws_group_return_print_format(settings, group)


def _settings_dict(doc=None):
    doc = doc or _ensure_settings_doc()

    fields = [
        "company",
        "pharmacy_warehouse",
        "cash_price_list",
        "welfare_price_list",
        "panel_price_list",

        "default_mode_of_payment",
        "cash_mode_of_payment",
        "card_mode_of_payment",
        "panel_mode_of_payment",
        "zakat_mode_of_payment",
        "donation_mode_of_payment",

        "default_cash_customer",

        "print_format",
        "cash_print_format",
        "welfare_print_format",
        "panel_print_format",

        "cash_return_print_format",
        "welfare_return_print_format",
        "panel_return_print_format",
        "walkin_return_print_format",

        "require_cash_payment",
        "auto_submit_invoice",
        "update_stock",
        "enforce_patient_status",
        "enforce_pharmacy_stock",
        "block_missing_price",
        "apply_registration_percentage_as_discount",
        "allow_manual_rate",
    ]

    out = {field: doc.get(field) for field in fields}
    out["settings_admin"] = 1 if frappe.session.user == "Administrator" else 0
    return out


@frappe.whitelist()
def save_settings(values):
    _kpws_require_administrator_user()

    values = _json(values)
    doc = _ensure_settings_doc()

    allowed = set(_settings_dict(doc).keys())
    allowed.discard("settings_admin")

    for key, value in values.items():
        if key in allowed:
            doc.set(key, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return _settings_dict(doc)


@frappe.whitelist()
def is_settings_admin():
    return {
        "user": frappe.session.user,
        "settings_admin": 1 if frappe.session.user == "Administrator" else 0,
    }
'''


JS_PATCH = r'''

/* KPWS_ADMIN_SETTINGS_RETURN_PRINT_V20_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Admin settings patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.canShowSettings = function () {
        return frappe.session && frappe.session.user === "Administrator";
    };

    const oldRenderAdminSettingsV20 = KPWSPharmacyBillingPOS.prototype.render;

    KPWSPharmacyBillingPOS.prototype.render = function () {
        oldRenderAdminSettingsV20.apply(this, arguments);

        if (!this.canShowSettings()) {
            this.page.main.find('[data-tab="settings"]').remove();
            this.page.main.find("#kpws-settings-tab").remove();
        }
    };

    KPWSPharmacyBillingPOS.prototype.renderSettings = function () {
        const root = this.page.main.find("#kpws-settings-tab");

        if (!root.length) return;

        if (!this.canShowSettings()) {
            root.html(`
                <div class="kpws-pos-card">
                    <div class="kpws-pos-card-title">Settings Restricted</div>
                    <div class="kpws-pos-warning">
                        Pharmacy POS Settings are available only to the Administrator user.
                    </div>
                </div>
            `);
            return;
        }

        root.html(`
            <div class="kpws-pos-card">
                <div class="kpws-pos-card-title">Pharmacy Billing Settings</div>

                <div class="kpws-pos-grid-2">
                    <div id="kpws-setting-company"></div>
                    <div id="kpws-setting-warehouse"></div>
                    <div id="kpws-setting-cash-customer"></div>
                    <div id="kpws-setting-cash-mop"></div>
                    <div id="kpws-setting-card-mop"></div>
                    <div id="kpws-setting-panel-mop"></div>
                    <div id="kpws-setting-zakat-mop"></div>
                    <div id="kpws-setting-donation-mop"></div>
                    <div id="kpws-setting-cash-pl"></div>
                    <div id="kpws-setting-welfare-pl"></div>
                    <div id="kpws-setting-panel-pl"></div>
                </div>

                <div class="kpws-pos-card-title" style="margin-top:18px;">Billing Print Formats</div>

                <div class="kpws-pos-grid">
                    <div id="kpws-setting-cash-print-format"></div>
                    <div id="kpws-setting-welfare-print-format"></div>
                    <div id="kpws-setting-panel-print-format"></div>
                </div>

                <div class="kpws-pos-card-title" style="margin-top:18px;">Return Print Formats</div>

                <div class="kpws-pos-grid">
                    <div id="kpws-setting-cash-return-print-format"></div>
                    <div id="kpws-setting-welfare-return-print-format"></div>
                    <div id="kpws-setting-panel-return-print-format"></div>
                    <div id="kpws-setting-walkin-return-print-format"></div>
                </div>

                <div class="kpws-pos-warning" style="margin-top:14px;">
                    Return print formats are used when a return invoice is created from Pharmacy POS or Return Requests.
                    If any return format is empty, the system will fall back to the normal billing print format.
                </div>

                <div class="kpws-pos-card-title" style="margin-top:18px;">Controls</div>

                <div class="kpws-pos-grid">
                    ${this.checkboxHTML("require_cash_payment", "Require Cash Payment")}
                    ${this.checkboxHTML("auto_submit_invoice", "Auto Submit Invoice")}
                    ${this.checkboxHTML("update_stock", "Update Stock")}
                    ${this.checkboxHTML("enforce_patient_status", "Block Invalid Patient Status")}
                    ${this.checkboxHTML("enforce_pharmacy_stock", "Block No Stock")}
                    ${this.checkboxHTML("block_missing_price", "Block Missing Price")}
                    ${this.checkboxHTML("allow_manual_rate", "Allow Manual Rate")}
                </div>

                <div style="margin-top:16px;">
                    <button class="kpws-pos-btn success" id="kpws-save-settings">Save Settings</button>
                </div>
            </div>
        `);

        this.makeSettingsControls();
        root.find("#kpws-save-settings").on("click", () => this.saveSettings());
    };

    KPWSPharmacyBillingPOS.prototype.makeSettingsControls = function () {
        const make = (id, label, fieldtype, options, fieldname) => {
            const target = this.page.main.find(id).get(0);
            if (!target) return;

            const control = frappe.ui.form.make_control({
                parent: target,
                df: {
                    label,
                    fieldtype,
                    options,
                    fieldname,
                    get_query: fieldtype === "Link" && options === "Print Format"
                        ? function () {
                            return {
                                filters: {
                                    doc_type: "Sales Invoice"
                                }
                            };
                        }
                        : undefined
                },
                render_input: true
            });

            control.set_value(this.settings[fieldname] || "");
            this[`${fieldname}Control`] = control;
        };

        make("#kpws-setting-company", "Company", "Link", "Company", "company");
        make("#kpws-setting-warehouse", "Pharmacy Warehouse", "Link", "Warehouse", "pharmacy_warehouse");
        make("#kpws-setting-cash-customer", "Default Cash Customer", "Link", "Customer", "default_cash_customer");

        make("#kpws-setting-cash-mop", "Cash Mode of Payment", "Link", "Mode of Payment", "cash_mode_of_payment");
        make("#kpws-setting-card-mop", "Card Mode of Payment", "Link", "Mode of Payment", "card_mode_of_payment");
        make("#kpws-setting-panel-mop", "Panel Mode of Payment", "Link", "Mode of Payment", "panel_mode_of_payment");
        make("#kpws-setting-zakat-mop", "Zakat Mode of Payment", "Link", "Mode of Payment", "zakat_mode_of_payment");
        make("#kpws-setting-donation-mop", "Donation Mode of Payment", "Link", "Mode of Payment", "donation_mode_of_payment");

        make("#kpws-setting-cash-pl", "Cash Price List", "Link", "Price List", "cash_price_list");
        make("#kpws-setting-welfare-pl", "Welfare Price List", "Link", "Price List", "welfare_price_list");
        make("#kpws-setting-panel-pl", "Panel Price List", "Link", "Price List", "panel_price_list");

        make("#kpws-setting-cash-print-format", "Cash Billing Print Format", "Link", "Print Format", "cash_print_format");
        make("#kpws-setting-welfare-print-format", "Welfare Billing Print Format", "Link", "Print Format", "welfare_print_format");
        make("#kpws-setting-panel-print-format", "Panel Billing Print Format", "Link", "Print Format", "panel_print_format");

        make("#kpws-setting-cash-return-print-format", "Cash Return Print Format", "Link", "Print Format", "cash_return_print_format");
        make("#kpws-setting-welfare-return-print-format", "Welfare Return Print Format", "Link", "Print Format", "welfare_return_print_format");
        make("#kpws-setting-panel-return-print-format", "Panel Return Print Format", "Link", "Print Format", "panel_return_print_format");
        make("#kpws-setting-walkin-return-print-format", "Walk-in Return Print Format", "Link", "Print Format", "walkin_return_print_format");
    };

    KPWSPharmacyBillingPOS.prototype.saveSettings = async function () {
        if (!this.canShowSettings()) {
            frappe.msgprint("Only Administrator user can save Pharmacy POS Settings.");
            return;
        }

        const get = (name) => this[`${name}Control`] ? this[`${name}Control`].get_value() : "";

        const values = {
            company: get("company"),
            pharmacy_warehouse: get("pharmacy_warehouse"),
            default_cash_customer: get("default_cash_customer"),

            cash_mode_of_payment: get("cash_mode_of_payment"),
            card_mode_of_payment: get("card_mode_of_payment"),
            panel_mode_of_payment: get("panel_mode_of_payment"),
            zakat_mode_of_payment: get("zakat_mode_of_payment"),
            donation_mode_of_payment: get("donation_mode_of_payment"),

            cash_price_list: get("cash_price_list"),
            welfare_price_list: get("welfare_price_list"),
            panel_price_list: get("panel_price_list"),

            cash_print_format: get("cash_print_format"),
            welfare_print_format: get("welfare_print_format"),
            panel_print_format: get("panel_print_format"),

            cash_return_print_format: get("cash_return_print_format"),
            welfare_return_print_format: get("welfare_return_print_format"),
            panel_return_print_format: get("panel_return_print_format"),
            walkin_return_print_format: get("walkin_return_print_format")
        };

        this.page.main.find("[data-setting-check]").each(function () {
            values[$(this).data("setting-check")] = $(this).is(":checked") ? 1 : 0;
        });

        const r = await this.call("save_settings", {
            values: JSON.stringify(values)
        });

        this.settings = r.message || {};
        frappe.show_alert({ message: "Settings saved.", indicator: "green" }, 8);
        this.renderSettings();
    };
})();
'''


def _append_once(path, patch, marker):
    p = Path(path)
    if not p.exists():
        return False

    text = p.read_text()

    if marker in text:
        return False

    p.write_text(text + "\n\n" + patch)
    return True


def _ensure_settings_fields():
    from kpws_customization.api.kpws_pharmacy_billing_desk import SETTINGS_DOCTYPE

    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        from kpws_customization.api.kpws_pharmacy_billing_desk import install
        install()

    dt = frappe.get_doc("DocType", SETTINGS_DOCTYPE)
    existing = {df.fieldname for df in dt.fields}

    new_fields = [
        {
            "fieldname": "cash_return_print_format",
            "label": "Cash Return Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "panel_print_format",
        },
        {
            "fieldname": "welfare_return_print_format",
            "label": "Welfare Return Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "cash_return_print_format",
        },
        {
            "fieldname": "panel_return_print_format",
            "label": "Panel Return Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "welfare_return_print_format",
        },
        {
            "fieldname": "walkin_return_print_format",
            "label": "Walk-in Return Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "panel_return_print_format",
        },
    ]

    added = []

    for field in new_fields:
        if field["fieldname"] not in existing:
            dt.append("fields", field)
            added.append(field["fieldname"])

    if added:
        dt.save(ignore_permissions=True)
        frappe.clear_cache(doctype=SETTINGS_DOCTYPE)

    frappe.db.commit()
    return added


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"
    server_changed = _append_once(api_file, SERVER_PATCH, PATCH_MARKER)

    js_files = [
        app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
        app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
    ]

    js_changed = []

    for js in js_files:
        if _append_once(js, JS_PATCH, PATCH_MARKER):
            js_changed.append(str(js))

    added_fields = _ensure_settings_fields()

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "server_changed": server_changed,
        "js_changed": js_changed,
        "settings_fields_added": added_fields,
        "message": "Admin-only Settings and return print format controls added."
    }
