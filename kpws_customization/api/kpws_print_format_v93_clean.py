# -*- coding: utf-8 -*-
"""
KPWS Print Format V93 Clean
- Updates existing Print Formats: Panel Sales, Welfare Sales
- Removes boxed/block layout for info sections
- Removes Status and Outstanding from printed invoice
- Keeps audit-safe Bill To + Patient separation
"""

import json
from pathlib import Path

import frappe


def _css():
    return r"""
<style>
  .kpws-print {
    font-family: Arial, Helvetica, sans-serif;
    color: #111827;
    font-size: 12px;
    line-height: 1.35;
  }
  .kpws-top {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    border-bottom: 2px solid #111827;
    padding-bottom: 8px;
    margin-bottom: 12px;
  }
  .kpws-title {
    font-size: 20px;
    font-weight: 800;
    margin: 0 0 3px 0;
    letter-spacing: .2px;
  }
  .kpws-subtitle {
    font-size: 11px;
    color: #4b5563;
  }
  .kpws-invoice-meta {
    text-align: right;
    font-size: 11px;
    min-width: 210px;
  }
  .kpws-invoice-meta div { margin-bottom: 2px; }
  .kpws-mode {
    font-weight: 800;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .04em;
  }
  .kpws-info {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 32px;
    row-gap: 8px;
    margin: 10px 0 12px 0;
  }
  .kpws-section-title {
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #374151;
    border-bottom: 1px solid #d1d5db;
    padding-bottom: 3px;
    margin-bottom: 5px;
  }
  .kpws-name {
    font-size: 14px;
    font-weight: 800;
    margin-bottom: 3px;
  }
  .kpws-line { margin: 2px 0; }
  .kpws-label { color: #4b5563; font-weight: 700; }
  .kpws-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
  }
  .kpws-table th {
    border-bottom: 2px solid #111827;
    padding: 6px 5px;
    font-weight: 800;
    text-align: left;
  }
  .kpws-table td {
    border-bottom: 1px solid #e5e7eb;
    padding: 6px 5px;
    vertical-align: top;
  }
  .right { text-align: right; }
  .kpws-summary {
    width: 42%;
    margin-left: auto;
    margin-top: 12px;
    border-collapse: collapse;
  }
  .kpws-summary td {
    padding: 5px 0 5px 10px;
    border-bottom: 1px solid #e5e7eb;
  }
  .kpws-summary .label {
    font-weight: 700;
    color: #374151;
  }
  .kpws-summary .grand td,
  .kpws-summary .grand .label {
    font-size: 14px;
    font-weight: 900;
    color: #111827;
    border-bottom: 2px solid #111827;
  }
  .kpws-note {
    margin-top: 11px;
    padding-top: 7px;
    border-top: 1px solid #d1d5db;
    font-size: 11px;
    color: #374151;
  }
  .kpws-signatures {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 70px;
    margin-top: 42px;
    font-size: 11px;
  }
  .kpws-sign-line {
    border-top: 1px solid #111827;
    padding-top: 5px;
    text-align: center;
  }
  @media print {
    .kpws-info { break-inside: avoid; }
    tr { page-break-inside: avoid; page-break-after: auto; }
  }
</style>
"""


PANEL_SALES_HTML = r"""
{{ letter_head or "" }}
{% set billing_mode = doc.get('custom_kpws_billing_type_final') or doc.get('custom_kpws_patient_billing_group') or 'Panel' %}
{% set patient_id = doc.get('patient') or doc.get('custom_patient') or doc.get('healthcare_patient') or doc.get('custom_healthcare_patient') or doc.get('custom_kpws_patient') or doc.get('custom_patient_id') or '' %}
{% set patient_name = doc.get('patient_name') or doc.get('custom_patient_name') or '' %}
{% if patient_id and not patient_name %}
  {% set patient_name = frappe.db.get_value('Patient', patient_id, 'patient_name') or patient_id %}
{% endif %}
{% set mr_no = doc.get('custom_mr_number') or doc.get('custom_reference_number') or doc.get('mr_number') or doc.get('patient_mr_number') or patient_id or '-' %}
{% set panel_customer = doc.get('custom_kpws_panel_customer') or doc.customer %}
{% set panel_customer_name = frappe.db.get_value('Customer', panel_customer, 'customer_name') if panel_customer else doc.customer_name %}
{% set prf = doc.get('custom_kpws_prf') or doc.get('custom_kpws_welfare_registration') or '' %}

<div class="kpws-print">
  <div class="kpws-top">
    <div>
      <h1 class="kpws-title">Panel Sales Invoice</h1>
      <div class="kpws-subtitle">Panel billing with patient identification</div>
    </div>
    <div class="kpws-invoice-meta">
      <div class="kpws-mode">{{ billing_mode }}</div>
      <div><span class="kpws-label">Invoice:</span> {{ doc.name }}</div>
      <div><span class="kpws-label">Date:</span> {{ doc.get_formatted('posting_date') }}</div>
    </div>
  </div>

  <div class="kpws-info">
    <div>
      <div class="kpws-section-title">Bill To / Panel Customer</div>
      <div class="kpws-name">{{ panel_customer_name or doc.customer_name }}</div>
      <div class="kpws-line"><span class="kpws-label">Customer ID:</span> {{ panel_customer or doc.customer }}</div>
      <div class="kpws-line"><span class="kpws-label">Coverage:</span> Fully covered by panel</div>
    </div>
    <div>
      <div class="kpws-section-title">Patient / Medicine Receiver</div>
      <div class="kpws-name">{{ patient_name or '-' }}</div>
      <div class="kpws-line"><span class="kpws-label">Patient ID / MR No:</span> {{ mr_no }}</div>
      {% if prf %}<div class="kpws-line"><span class="kpws-label">PRF:</span> {{ prf }}</div>{% endif %}
    </div>
  </div>

  <table class="kpws-table">
    <thead>
      <tr>
        <th style="width:4%;">#</th>
        <th>Item</th>
        <th style="width:12%;" class="right">Qty</th>
        <th style="width:14%;" class="right">Rate</th>
        <th style="width:16%;" class="right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for item in doc.items %}
      <tr>
        <td>{{ item.idx }}</td>
        <td>
          <b>{{ item.item_name or item.item_code }}</b>
          {% if item.description and item.description != item.item_name %}<br><span style="color:#6b7280;">{{ item.description }}</span>{% endif %}
        </td>
        <td class="right">{{ item.get_formatted('qty') }} {{ item.uom or '' }}</td>
        <td class="right">{{ item.get_formatted('rate') }}</td>
        <td class="right">{{ item.get_formatted('amount') }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <table class="kpws-summary">
    <tr><td class="label">Net Total</td><td class="right">{{ doc.get_formatted('net_total') }}</td></tr>
    {% if doc.total_taxes_and_charges %}<tr><td class="label">Taxes</td><td class="right">{{ doc.get_formatted('total_taxes_and_charges') }}</td></tr>{% endif %}
    <tr class="grand"><td class="label">Grand Total</td><td class="right">{{ doc.get_formatted('grand_total') }}</td></tr>
    <tr><td class="label">Panel Covered Amount</td><td class="right">{{ doc.get_formatted('grand_total') }}</td></tr>
    <tr><td class="label">Patient Payable</td><td class="right">{{ frappe.utils.fmt_money(0, currency=doc.currency) }}</td></tr>
  </table>

  <div class="kpws-note">
    The panel customer shown above is the bill-to party. The patient is the actual medicine receiver and beneficiary.
  </div>

  <div class="kpws-signatures">
    <div class="kpws-sign-line">Prepared / Pharmacy</div>
    <div class="kpws-sign-line">Authorized Signature</div>
  </div>
</div>
"""


WELFARE_SALES_HTML = r"""
{{ letter_head or "" }}
{% set billing_mode = doc.get('custom_kpws_billing_type_final') or doc.get('custom_kpws_patient_billing_group') or 'Welfare' %}
{% set purpose = doc.get('custom_kpws_purpose') or doc.get('custom_kpws_funding_source') or 'Zakat/Donation' %}
{% set percentage = doc.get('custom_kpws_approved_percentage') or 100 %}
{% set patient_id = doc.get('patient') or doc.get('custom_patient') or doc.get('healthcare_patient') or doc.get('custom_healthcare_patient') or doc.get('custom_kpws_patient') or doc.get('custom_patient_id') or '' %}
{% set patient_name = doc.get('patient_name') or doc.get('custom_patient_name') or '' %}
{% if patient_id and not patient_name %}
  {% set patient_name = frappe.db.get_value('Patient', patient_id, 'patient_name') or patient_id %}
{% endif %}
{% set mr_no = doc.get('custom_mr_number') or doc.get('custom_reference_number') or doc.get('mr_number') or doc.get('patient_mr_number') or patient_id or '-' %}
{% set prf = doc.get('custom_kpws_prf') or doc.get('custom_kpws_welfare_registration') or '' %}
{% set panel_customer = doc.get('custom_kpws_panel_customer') or '' %}
{% set panel_customer_name = frappe.db.get_value('Customer', panel_customer, 'customer_name') if panel_customer else '' %}
{% set is_welfare_panel = 1 if panel_customer else 0 %}
{% set covered_amount = doc.get('custom_kpws_welfare_covered_amount') or 0 %}
{% set patient_share = doc.get('custom_kpws_patient_share_amount') or 0 %}
{% set patient_cash = doc.get('custom_kpws_patient_cash_amount') or 0 %}
{% set patient_card = doc.get('custom_kpws_patient_card_amount') or 0 %}
{% if not covered_amount and percentage %}
  {% set covered_amount = frappe.utils.flt(doc.grand_total) * frappe.utils.flt(percentage) / 100 %}
{% endif %}
{% if not patient_share %}
  {% set patient_share = frappe.utils.flt(doc.grand_total) - frappe.utils.flt(covered_amount) %}
{% endif %}

<div class="kpws-print">
  <div class="kpws-top">
    <div>
      <h1 class="kpws-title">Welfare Sales Invoice</h1>
      <div class="kpws-subtitle">{% if is_welfare_panel %}Welfare Panel under {{ purpose }}{% else %}Welfare under {{ purpose }}{% endif %}</div>
    </div>
    <div class="kpws-invoice-meta">
      <div class="kpws-mode">{% if is_welfare_panel %}Welfare Panel{% else %}{{ billing_mode }}{% endif %}</div>
      <div><span class="kpws-label">Invoice:</span> {{ doc.name }}</div>
      <div><span class="kpws-label">Date:</span> {{ doc.get_formatted('posting_date') }}</div>
    </div>
  </div>

  <div class="kpws-info">
    <div>
      <div class="kpws-section-title">Bill To / Covering Party</div>
      {% if is_welfare_panel %}
        <div class="kpws-name">{{ panel_customer_name or panel_customer }}</div>
        <div class="kpws-line"><span class="kpws-label">Customer ID:</span> {{ panel_customer }}</div>
        <div class="kpws-line"><span class="kpws-label">Mode:</span> Welfare Panel</div>
      {% else %}
        <div class="kpws-name">{{ doc.customer_name }}</div>
        <div class="kpws-line"><span class="kpws-label">Customer ID:</span> {{ doc.customer }}</div>
        <div class="kpws-line"><span class="kpws-label">Mode:</span> Welfare</div>
      {% endif %}
      <div class="kpws-line"><span class="kpws-label">Purpose:</span> {{ purpose }}</div>
      <div class="kpws-line"><span class="kpws-label">Approved Coverage:</span> {{ percentage }}%</div>
    </div>

    <div>
      <div class="kpws-section-title">Patient / Medicine Receiver</div>
      <div class="kpws-name">{{ patient_name or '-' }}</div>
      <div class="kpws-line"><span class="kpws-label">Patient ID / MR No:</span> {{ mr_no }}</div>
      {% if prf %}<div class="kpws-line"><span class="kpws-label">PRF:</span> {{ prf }}</div>{% endif %}
      <div class="kpws-line"><span class="kpws-label">Patient Share:</span> {{ frappe.utils.fmt_money(patient_share, currency=doc.currency) }}</div>
    </div>
  </div>

  <table class="kpws-table">
    <thead>
      <tr>
        <th style="width:4%;">#</th>
        <th>Item</th>
        <th style="width:12%;" class="right">Qty</th>
        <th style="width:14%;" class="right">Rate</th>
        <th style="width:16%;" class="right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for item in doc.items %}
      <tr>
        <td>{{ item.idx }}</td>
        <td>
          <b>{{ item.item_name or item.item_code }}</b>
          {% if item.description and item.description != item.item_name %}<br><span style="color:#6b7280;">{{ item.description }}</span>{% endif %}
        </td>
        <td class="right">{{ item.get_formatted('qty') }} {{ item.uom or '' }}</td>
        <td class="right">{{ item.get_formatted('rate') }}</td>
        <td class="right">{{ item.get_formatted('amount') }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <table class="kpws-summary">
    <tr><td class="label">Net Total</td><td class="right">{{ doc.get_formatted('net_total') }}</td></tr>
    {% if doc.total_taxes_and_charges %}<tr><td class="label">Taxes</td><td class="right">{{ doc.get_formatted('total_taxes_and_charges') }}</td></tr>{% endif %}
    <tr class="grand"><td class="label">Grand Total</td><td class="right">{{ doc.get_formatted('grand_total') }}</td></tr>
    <tr><td class="label">{{ purpose }} Covered Amount{% if is_welfare_panel %} by Panel{% endif %}</td><td class="right">{{ frappe.utils.fmt_money(covered_amount, currency=doc.currency) }}</td></tr>
    <tr><td class="label">Patient Share</td><td class="right">{{ frappe.utils.fmt_money(patient_share, currency=doc.currency) }}</td></tr>
    {% if patient_cash %}<tr><td class="label">Patient Cash Paid</td><td class="right">{{ frappe.utils.fmt_money(patient_cash, currency=doc.currency) }}</td></tr>{% endif %}
    {% if patient_card %}<tr><td class="label">Patient Card Paid</td><td class="right">{{ frappe.utils.fmt_money(patient_card, currency=doc.currency) }}</td></tr>{% endif %}
  </table>

  <div class="kpws-note">
    {% if is_welfare_panel %}
      The selected panel is the covering party for the approved {{ purpose }} percentage. The patient is the actual medicine receiver and beneficiary.
    {% else %}
      Welfare coverage is based on the approved Patient Registration Form purpose and percentage. The patient is the actual medicine receiver and beneficiary.
    {% endif %}
  </div>

  <div class="kpws-signatures">
    <div class="kpws-sign-line">Prepared / Pharmacy</div>
    <div class="kpws-sign-line">Authorized Signature</div>
  </div>
</div>
"""


def _full_html(body):
    return _css() + "\n" + body


def _backup_print_format(name, backup_dir):
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    if not frappe.db.exists("Print Format", name):
        return {"name": name, "exists": False}

    doc = frappe.get_doc("Print Format", name)
    safe_name = name.replace(" ", "_")
    json_path = Path(backup_dir) / f"{safe_name}.json"
    html_path = Path(backup_dir) / f"{safe_name}.html"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(doc.as_dict(), f, indent=2, default=str)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc.html or "")

    return {"name": name, "exists": True, "json": str(json_path), "html": str(html_path)}


def _upsert_print_format(name, html):
    if frappe.db.exists("Print Format", name):
        doc = frappe.get_doc("Print Format", name)
        action = "updated"
    else:
        doc = frappe.new_doc("Print Format")
        doc.name = name
        doc.print_format_name = name
        action = "created"

    doc.doc_type = "Sales Invoice"
    doc.module = "KPWS Customization" if frappe.db.exists("Module Def", "KPWS Customization") else "Accounts"
    doc.standard = "No"
    doc.custom_format = 1
    doc.print_format_type = "Jinja"
    doc.disabled = 0
    doc.html = html

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return {"name": name, "action": action, "html_length": len(html)}


@frappe.whitelist()
def apply(backup_dir=None):
    backup_dir = backup_dir or "/home/easein/kpws-print-format-clean-v93-backup"

    backups = [
        _backup_print_format("Panel Sales", backup_dir),
        _backup_print_format("Welfare Sales", backup_dir),
    ]

    results = [
        _upsert_print_format("Panel Sales", _full_html(PANEL_SALES_HTML)),
        _upsert_print_format("Welfare Sales", _full_html(WELFARE_SALES_HTML)),
    ]

    frappe.db.commit()
    frappe.clear_cache(doctype="Print Format")
    frappe.clear_cache(doctype="Sales Invoice")
    frappe.clear_cache()

    return {"ok": True, "backup_dir": backup_dir, "backups": backups, "results": results}


@frappe.whitelist()
def audit():
    out = []
    for name in ("Panel Sales", "Welfare Sales"):
        exists = frappe.db.exists("Print Format", name)
        row = {"name": name, "exists": bool(exists)}
        if exists:
            doc = frappe.get_doc("Print Format", name)
            html = doc.html or ""
            row.update({
                "doc_type": doc.doc_type,
                "custom_format": doc.custom_format,
                "print_format_type": doc.print_format_type,
                "disabled": doc.disabled,
                "html_length": len(html),
                "contains_status_word": "Status" in html or "status" in html,
                "contains_outstanding_word": "Outstanding" in html or "outstanding" in html,
                "contains_box_class": "kpws-box" in html,
            })
        out.append(row)
    return out
