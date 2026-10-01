(function () {
  const PATIENT_FIELDS = ["custom_patient", "patient", "patient_name"];
  const WALKIN_NAME_FIELDS = ["custom_walkin_patient_name", "walkin_customer_name"];
  const WALKIN_MR_FIELDS = ["custom_walkin_mr_number", "walkin_mr_number"];

  function has(frm, f) { return frm.fields_dict && frm.fields_dict[f]; }
  function first(frm, arr) { return arr.find(f => has(frm, f)); }
  function get_patient(frm) { const f = first(frm, PATIENT_FIELDS); return f ? frm.doc[f] : ""; }
  function setv(frm, f, v) { return has(frm, f) && frm.doc[f] !== v ? frm.set_value(f, v || "") : Promise.resolve(); }
  function is_walkin(frm) { return !!frm.doc.custom_is_walkin || (!!frm.doc.walkin_customer_name && !get_patient(frm)); }

  function simplify_fields(frm, ctx) {
    const walkin = is_walkin(frm);
    PATIENT_FIELDS.forEach(f => { if (has(frm, f)) frm.toggle_display(f, !walkin); });
    WALKIN_NAME_FIELDS.concat(WALKIN_MR_FIELDS).forEach(f => { if (has(frm, f)) frm.toggle_display(f, walkin); });

    const billing = (ctx && ctx.billing_type) || frm.doc.custom_kpws_billing_type || "";
    ["custom_kpws_panel_customer", "custom_panel_customer", "custom_panel"].forEach(f => { if (has(frm, f)) frm.toggle_display(f, billing === "Panel"); });
    ["custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage", "custom_welfare_registration", "custom_welfare_type", "custom_welfare_percentage"].forEach(f => {
      if (has(frm, f)) frm.toggle_display(f, billing === "Welfare");
    });
  }

  function invoice_total(frm) {
    return flt(frm.doc.rounded_total || frm.doc.grand_total || frm.doc.net_total || 0);
  }

  function apply_welfare_payments(frm, ctx) {
    if (!ctx || ctx.billing_type !== "Welfare" || !ctx.welfare || !has(frm, "payments")) return;
    if (frm.doc.docstatus !== 0) return;
    const total = invoice_total(frm);
    if (!total) return;
    const pct = Math.max(0, Math.min(100, flt(ctx.welfare.coverage_percentage || 0)));
    const covered = flt(total * pct / 100, precision("grand_total", frm.doc));
    const balance = flt(total - covered, precision("grand_total", frm.doc));
    frm.clear_table("payments");
    if (covered > 0) {
      const row = frm.add_child("payments");
      row.mode_of_payment = ctx.welfare.mode_of_payment || ctx.welfare.assistance_type || "Donation";
      row.amount = covered;
      row.base_amount = covered;
    }
    if (balance > 0) {
      const row = frm.add_child("payments");
      row.mode_of_payment = ctx.cash_mode_of_payment || "Cash";
      row.amount = balance;
      row.base_amount = balance;
    }
    frm.refresh_field("payments");
  }

  async function apply_context(frm) {
    if (frm.__kpws_applying || frm.doc.docstatus !== 0) return;
    const patient = get_patient(frm);
    const walkin = is_walkin(frm) ? 1 : 0;
    if (!patient && !walkin && !frm.doc.customer) { simplify_fields(frm, {}); return; }

    frm.__kpws_applying = true;
    try {
      const r = await frappe.call({
        method: "kpws_customization.api.kpws_patient_flow.get_sales_invoice_context",
        args: { patient: patient, customer: frm.doc.customer, is_walkin: walkin }
      });
      const ctx = r.message || {};
      frm.__kpws_context = ctx;

      const tasks = [];
      if (ctx.customer && frm.doc.customer !== ctx.customer) tasks.push(frm.set_value("customer", ctx.customer));
      if (has(frm, "is_pos")) tasks.push(setv(frm, "is_pos", 1));
      if (ctx.pos_profile && has(frm, "pos_profile")) tasks.push(setv(frm, "pos_profile", ctx.pos_profile));
      if (ctx.selling_price_list && has(frm, "selling_price_list")) tasks.push(setv(frm, "selling_price_list", ctx.selling_price_list));
      tasks.push(setv(frm, "custom_kpws_billing_type", ctx.billing_type || "Cash"));
      tasks.push(setv(frm, "custom_kpws_panel_customer", ctx.panel_customer || ""));
      tasks.push(setv(frm, "custom_kpws_welfare_registration", ctx.welfare ? ctx.welfare.registration : ""));
      tasks.push(setv(frm, "custom_kpws_welfare_type", ctx.welfare ? ctx.welfare.assistance_type : ""));
      tasks.push(setv(frm, "custom_kpws_welfare_percentage", ctx.welfare ? ctx.welfare.coverage_percentage : 0));

      await Promise.all(tasks);
      simplify_fields(frm, ctx);
      apply_welfare_payments(frm, ctx);
      frm.refresh_fields();
    } finally {
      frm.__kpws_applying = false;
    }
  }

  function schedule(frm) { clearTimeout(frm.__kpws_timer); frm.__kpws_timer = setTimeout(() => apply_context(frm), 350); }

  frappe.ui.form.on("Sales Invoice", {
    refresh(frm) { simplify_fields(frm, frm.__kpws_context || {}); apply_context(frm); },
    custom_is_walkin(frm) { apply_context(frm); },
    custom_patient(frm) { apply_context(frm); },
    patient(frm) { apply_context(frm); },
    patient_name(frm) { apply_context(frm); },
    customer(frm) { if (!frm.__kpws_applying) apply_context(frm); },
    grand_total(frm) { schedule(frm); },
    rounded_total(frm) { schedule(frm); },
    net_total(frm) { schedule(frm); }
  });

  frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm) { schedule(frm); }, qty(frm) { schedule(frm); }, rate(frm) { schedule(frm); }, amount(frm) { schedule(frm); }
  });
})();
