(function () {
  const PANEL_FIELDS = ["panel_name", "custom_panel_customer", "panel_customer", "custom_panel", "panel"];
  const OLD_FIELDS = ["custom_patient_billing_type", "custom_latest_welfare_registration", "custom_welfare_type", "custom_welfare_percentage"];

  function has(frm, f) { return frm.fields_dict && frm.fields_dict[f]; }
  function val(frm, f) { return has(frm, f) ? (frm.doc[f] || "") : ""; }
  function billing(frm) { return String(val(frm, "customer_group") || val(frm, "custom_patient_billing_type") || "").toLowerCase(); }
  function is_panel(frm) { return billing(frm).includes("panel"); }
  function is_welfare(frm) { return billing(frm).includes("welfare"); }

  function set_panel_queries(frm) {
    PANEL_FIELDS.forEach(f => {
      if (has(frm, f)) {
        frm.set_query(f, function () {
          return { query: "kpws_customization.api.kpws_clean_flow.get_panel_customers" };
        });
      }
    });
  }

  function clean_ui(frm) {
    set_panel_queries(frm);
    OLD_FIELDS.forEach(f => { if (has(frm, f)) frm.toggle_display(f, false); });
    PANEL_FIELDS.forEach(f => {
      if (has(frm, f)) {
        frm.toggle_display(f, is_panel(frm));
        frm.toggle_reqd(f, is_panel(frm));
      }
    });
  }

  frappe.ui.form.on("Patient", {
    setup(frm) { set_panel_queries(frm); },
    refresh(frm) {
      clean_ui(frm);
      if (!frm.is_new() && is_welfare(frm)) {
        frm.add_custom_button(__('Open / Create Welfare Registration'), function () {
          frappe.call({
            method: "kpws_customization.api.kpws_clean_flow.create_or_open_welfare_registration",
            args: { patient: frm.doc.name },
            freeze: true,
            callback: function (r) {
              if (r.message && r.message.route) {
                frappe.set_route(r.message.route.replace('/app/', '').split('/'));
              }
            }
          });
        }, __('Welfare'));
      }
    },
    customer_group(frm) { clean_ui(frm); },
    custom_patient_billing_type(frm) { clean_ui(frm); },
    panel_name(frm) { clean_ui(frm); },
    custom_panel_customer(frm) { clean_ui(frm); }
  });
})();
