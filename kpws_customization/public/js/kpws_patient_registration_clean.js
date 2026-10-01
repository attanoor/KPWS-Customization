(function () {
  const PATIENT_FIELDS = ["patient", "custom_patient", "patient_id", "kpws_patient"];
  const MR_FIELDS = ["mr_no", "mr_number", "custom_mr_number", "custom_reference_number", "reference_number"];
  const NAME_FIELDS = ["patient_full_name", "patient_name", "custom_patient_name", "full_name"];
  const ADMIN_FIELDS = ["custom_kpws_welfare_type", "custom_kpws_welfare_percentage", "custom_kpws_assigned_panel_customer", "custom_kpws_admin_notes"];
  const OLD_FIELDS = ["custom_patient_customer", "custom_billing_type", "custom_assistance_type", "custom_coverage_percentage", "custom_panel_customer", "custom_review_status", "custom_approval_remarks", "custom_panel", "custom_assigned_panel"];

  function has(frm, f) { return frm.fields_dict && frm.fields_dict[f]; }
  function first(frm, arr) { return arr.find(f => has(frm, f)); }
  function get_patient(frm) { const f = first(frm, PATIENT_FIELDS); return f ? frm.doc[f] : ""; }
  function is_admin() {
    const roles = frappe.user_roles || [];
    return roles.includes("Administrator") || roles.includes("System Manager") || roles.includes("Healthcare Manager") || roles.includes("Accounts Manager");
  }
  function set_if(frm, fields, value) {
    const f = first(frm, fields);
    if (f && value !== undefined && frm.doc[f] !== value) return frm.set_value(f, value || "");
    return Promise.resolve();
  }

  function panel_query(frm) {
    if (has(frm, "custom_kpws_assigned_panel_customer")) {
      frm.set_query("custom_kpws_assigned_panel_customer", function () {
        return { query: "kpws_customization.api.kpws_clean_flow.get_panel_customers" };
      });
    }
  }

  function render_snapshot(frm, data) {
    if (!has(frm, "custom_kpws_patient_snapshot_html")) return;
    if (!data || !data.patient) {
      frm.set_df_property("custom_kpws_patient_snapshot_html", "options", "<div class='text-muted'>Select Patient to load details.</div>");
      return;
    }
    const esc = frappe.utils.escape_html;
    const html = `
      <div style="border:1px solid #e5e7eb;border-radius:10px;padding:12px;background:#fafafa;margin-bottom:8px">
        <div style="font-weight:700;font-size:15px;margin-bottom:8px">Patient Information</div>
        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;font-size:13px">
          <div><b>Patient:</b> ${esc(data.patient_name || '')}</div>
          <div><b>MR No:</b> ${esc(data.mr_number || '')}</div>
          <div><b>Customer:</b> ${esc(data.customer || '')}</div>
          <div><b>Customer Group:</b> ${esc(data.customer_group || '')}</div>
          <div><b>Mobile:</b> ${esc(data.mobile || '')}</div>
          <div><b>CNIC:</b> ${esc(data.cnic || '')}</div>
          <div style="grid-column:1 / -1"><b>Address:</b> ${esc(data.address || '')}</div>
        </div>
      </div>`;
    frm.set_df_property("custom_kpws_patient_snapshot_html", "options", html);
  }

  async function load_patient(frm) {
    const patient = get_patient(frm);
    if (!patient || frm.__kpws_loading_patient) return;
    frm.__kpws_loading_patient = true;
    try {
      const r = await frappe.call({ method: "kpws_customization.api.kpws_clean_flow.get_patient_snapshot", args: { patient: patient } });
      const data = r.message || {};
      render_snapshot(frm, data);
      await set_if(frm, MR_FIELDS, data.mr_number);
      await set_if(frm, NAME_FIELDS, data.patient_name);
    } finally {
      frm.__kpws_loading_patient = false;
    }
  }

  function clean_ui(frm) {
    panel_query(frm);
    OLD_FIELDS.forEach(f => { if (has(frm, f)) frm.toggle_display(f, false); });
    ADMIN_FIELDS.forEach(f => {
      if (has(frm, f)) {
        frm.toggle_display(f, true);
        frm.set_df_property(f, "read_only", !is_admin());
      }
    });
    MR_FIELDS.concat(NAME_FIELDS).forEach(f => { if (has(frm, f)) frm.set_df_property(f, "read_only", 1); });
  }

  const handlers = {
    setup(frm) { panel_query(frm); },
    refresh(frm) { clean_ui(frm); load_patient(frm); },
    validate(frm) {
      if (has(frm, "custom_kpws_welfare_percentage")) {
        const pct = flt(frm.doc.custom_kpws_welfare_percentage || 0);
        if (pct < 0 || pct > 100) frappe.throw(__('Percentage must be between 0 and 100.'));
      }
    }
  };
  PATIENT_FIELDS.forEach(f => { handlers[f] = function(frm) { load_patient(frm); }; });
  frappe.ui.form.on("Patient Registration Form", handlers);
})();
