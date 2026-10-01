(function () {
  const OLD_FIELDS = [
    "custom_patient", "custom_kpws_billing_type", "custom_kpws_panel_customer",
    "custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage",
    "custom_panel_customer", "custom_welfare_registration", "custom_welfare_type", "custom_welfare_percentage"
  ];
  const WALKIN_FIELDS = ["custom_walkin_patient_name", "custom_walkin_mr_number"];

  function has(frm, f) { return frm.fields_dict && frm.fields_dict[f]; }
  function setv(frm, f, v) { return has(frm, f) && frm.doc[f] !== v ? frm.set_value(f, v || "") : Promise.resolve(); }
  function total(frm) { return flt(frm.doc.rounded_total || frm.doc.grand_total || frm.doc.net_total || 0); }
  function is_walkin(frm) { return !!frm.doc.custom_is_walkin; }

  function clean_ui(frm, ctx) {
    OLD_FIELDS.forEach(f => { if (has(frm, f)) frm.toggle_display(f, false); });
    WALKIN_FIELDS.forEach(f => { if (has(frm, f)) frm.toggle_display(f, is_walkin(frm)); });
    if (has(frm, "patient")) frm.toggle_display("patient", !is_walkin(frm));

    const billing = (ctx && ctx.billing_type) || "";
    if (billing) {
      const msg = billing === "Panel"
        ? `Panel billing: ${frappe.utils.escape_html(ctx.panel_customer_name || ctx.panel_customer || '')}`
        : billing === "Welfare" && ctx.welfare
          ? `Welfare: ${ctx.welfare.assistance_type || ''} ${flt(ctx.welfare.coverage_percentage || 0)}%`
          : `Billing Type: ${billing}`;
      frm.dashboard.clear_comment();
      frm.dashboard.add_comment(msg, billing === "Panel" ? "blue" : billing === "Welfare" ? "orange" : "green", true);
    }
  }

  function set_payment_row(row, mode, amount) {
    row.mode_of_payment = mode;
    row.amount = amount;
    row.base_amount = amount;
  }

  function apply_cash_default(frm, ctx) {
    if (!has(frm, "payments") || frm.doc.docstatus !== 0) return;
    if ((frm.doc.payments || []).length) return;
    const amt = total(frm);
    if (!amt) return;
    const row = frm.add_child("payments");
    set_payment_row(row, ctx.cash_mode_of_payment || "Cash", amt);
    frm.refresh_field("payments");
  }

  function apply_welfare_split(frm, ctx) {
    if (!has(frm, "payments") || frm.doc.docstatus !== 0 || !ctx || !ctx.welfare) return;
    const amt = total(frm);
    if (!amt) return;
    const pct = Math.max(0, Math.min(100, flt(ctx.welfare.coverage_percentage || 0)));
    const covered = flt(amt * pct / 100, precision("grand_total", frm.doc));
    const balance = flt(amt - covered, precision("grand_total", frm.doc));
    frm.clear_table("payments");
    if (covered > 0) {
      const row = frm.add_child("payments");
      set_payment_row(row, ctx.welfare.mode_of_payment || ctx.welfare.assistance_type || "Donation", covered);
    }
    if (balance > 0) {
      const row = frm.add_child("payments");
      set_payment_row(row, ctx.cash_mode_of_payment || "Cash", balance);
    }
    frm.refresh_field("payments");
  }

  function clear_payments(frm) {
    if (has(frm, "payments") && frm.doc.docstatus === 0 && (frm.doc.payments || []).length) {
      frm.clear_table("payments");
      frm.refresh_field("payments");
    }
  }

  async function apply_context(frm) {
    if (frm.__kpws_applying || frm.doc.docstatus !== 0) return;
    const patient = has(frm, "patient") ? frm.doc.patient : "";
    const mr = has(frm, "custom_kpws_mr_number") ? frm.doc.custom_kpws_mr_number : "";
    if (!is_walkin(frm) && !patient && !mr && !frm.doc.customer) { clean_ui(frm, {}); return; }

    frm.__kpws_applying = true;
    try {
      const r = await frappe.call({
        method: "kpws_customization.api.kpws_clean_flow.get_sales_invoice_context",
        args: {
          patient: patient,
          mr_number: mr,
          customer: frm.doc.customer,
          is_walkin: is_walkin(frm) ? 1 : 0,
          walkin_name: frm.doc.custom_walkin_patient_name,
          walkin_mr_number: frm.doc.custom_walkin_mr_number
        }
      });
      const ctx = r.message || {};
      frm.__kpws_context = ctx;

      const tasks = [];
      if (ctx.patient && has(frm, "patient") && frm.doc.patient !== ctx.patient) tasks.push(frm.set_value("patient", ctx.patient));
      if (ctx.mr_number && has(frm, "custom_kpws_mr_number") && !is_walkin(frm)) tasks.push(setv(frm, "custom_kpws_mr_number", ctx.mr_number));
      if (ctx.customer && frm.doc.customer !== ctx.customer) tasks.push(frm.set_value("customer", ctx.customer));
      if (ctx.selling_price_list && has(frm, "selling_price_list")) tasks.push(setv(frm, "selling_price_list", ctx.selling_price_list));
      if (has(frm, "is_pos")) tasks.push(setv(frm, "is_pos", ctx.billing_type === "Panel" ? 0 : 1));
      if (ctx.billing_type !== "Panel" && ctx.pos_profile && has(frm, "pos_profile")) tasks.push(setv(frm, "pos_profile", ctx.pos_profile));

      await Promise.all(tasks);
      clean_ui(frm, ctx);

      if (ctx.billing_type === "Welfare") apply_welfare_split(frm, ctx);
      else if (ctx.billing_type === "Panel") clear_payments(frm);
      else apply_cash_default(frm, ctx);
    } finally {
      frm.__kpws_applying = false;
    }
  }

  function schedule(frm) {
    clearTimeout(frm.__kpws_timer);
    frm.__kpws_timer = setTimeout(() => apply_context(frm), 300);
  }

  frappe.ui.form.on("Sales Invoice", {
    refresh(frm) { clean_ui(frm, frm.__kpws_context || {}); schedule(frm); },
    patient(frm) { apply_context(frm); },
    customer(frm) { if (!frm.__kpws_applying) schedule(frm); },
    custom_kpws_mr_number(frm) { apply_context(frm); },
    custom_is_walkin(frm) {
      if (is_walkin(frm)) {
        if (has(frm, "patient")) frm.set_value("patient", "");
        if (has(frm, "custom_kpws_mr_number")) frm.set_value("custom_kpws_mr_number", "");
      }
      apply_context(frm);
    },
    custom_walkin_patient_name(frm) { if (is_walkin(frm)) schedule(frm); },
    custom_walkin_mr_number(frm) { if (is_walkin(frm)) schedule(frm); },
    grand_total(frm) { schedule(frm); },
    rounded_total(frm) { schedule(frm); },
    net_total(frm) { schedule(frm); }
  });

  frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm) { schedule(frm); },
    qty(frm) { schedule(frm); },
    rate(frm) { schedule(frm); },
    amount(frm) { schedule(frm); }
  });
})();
