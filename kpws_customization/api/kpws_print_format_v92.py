# -*- coding: utf-8 -*-
"""
KPWS Print Format V92
Updates Panel Sales and Welfare Sales print formats for audit-safe billing display.

Rules:
- Panel Sales: Bill To is panel/customer, but Patient details are clearly separated.
- Welfare Sales: supports normal Welfare and Welfare Panel.
  Welfare Panel shows selected Panel as Bill To, Zakat/Donation purpose, covered %, patient share.
"""

import json
import os
from pathlib import Path

import frappe


def _css():
    return """
<style>
  .kpws-print { font-family: Arial, sans-serif; color: #111827; font-size: 12px; line-height: 1.35; }
  .kpws-header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1f4e79; padding-bottom: 10px; margin-bottom: 12px; }
  .kpws-title { font-size: 22px; font-weight: 700; color: #1f4e79; margin: 0; }
  .kpws-subtitle { font-size: 12px; color: #4b5563; margin-top: 3px; }
  .kpws-meta { text-align: right; font-size: 11px; }
  .kpws-badge { display: inline-block; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 700; background: #eef6ff; color: #1f4e79; border: 1px solid #c7ddf2; }
  .kpws-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 10px 0 12px; }
  .kpws-box { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; min-height: 82px; }
  .kpws-box-title { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; font-weight: 700; margin-bottom: 6px; }
  .kpws-name { font-size: 15px; font-weight: 700; color: #111827; margin-bottom: 3px; }
  .kpws-line { margin: 2px 0; }
  .kpws-muted { color: #6b7280; }
  .kpws-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  .kpws-table th { background: #f3f4f6; color: #111827; border: 1px solid #d1d5db; padding: 7px 6px; font-weight: 700; text-align: left; }
  .kpws-table td { border: 1px solid #e5e7eb; padding: 6px; vertical-align: top; }
  .kpws-table .right { text-align: right; }
  .kpws-summary { width: 44%; margin-left: auto; margin-top: 12px; border-collapse: collapse; }
  .kpws-summary td { border: 1px solid #d1d5db; padding: 7px; }
  .kpws-summary .label { background: #f9fafb; font-weight: 700; }
  .kpws-summary .grand { font-size: 15px; font-weight: 800; color: #1f4e79; }
  .kpws-note { margin-top: 12px; border-left: 4px solid #1f4e79; background: #f8fafc; padding: 9px 10px; font-size: 11px; color: #374151; }
  .kpws-signatures { display: grid; grid-template-columns: 1fr 1fr; gap: 60px; margin-top: 42px; font-size: 11px; }
  .kpws-sign-line { border-top: 1px solid #111827; padding-top: 5px; text-align: center; }
  @media print { .kpws-box { break-inside: avoid; } .kpws-table { page-break-inside: auto; } tr { page-break-inside: avoid; page-break-after: auto; } }
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
{% set covered_amount = doc.get('custom_kpws_welfare_covered_amount') or doc.grand_total %}

<div class="kpws-print">
  <div class="kpws-header">
    <div>
      <h1 class="kpws-title">Panel Sales Invoice</h1>
      <div class="kpws-subtitle">Panel billing with separate patient identification</div>
    </div>
    <div class="kpws-meta">
      <div class="kpws-badge">{{ billing_mode }}</div>
      <div class="kpws-line"><b>Invoice:</b> {{ doc.name }}</div>
      <div class="kpws-line"><b>Date:</b> {{ doc.get_formatted('posting_date') }}</div>
      <div class="kpws-line"><b>Status:</b> {{ doc.status or '-' }}</div>
    </div>
  </div>

  <div class="kpws-grid">
    <div class="kpws-box">
      <div class="kpws-box-title">Bill To / Panel Customer</div>
      <div class="kpws-name">{{ panel_customer_name or doc.customer_name }}</div>
      <div class="kpws-line"><span class="kpws-muted">Customer ID:</span> {{ panel_customer or doc.customer }}</div>
      <div class="kpws-line"><span class="kpws-muted">Coverage:</span> Fully covered by panel</div>
    </div>
    <div class="kpws-box">
      <div class="kpws-box-title">Patient / Medicine Receiver</div>
      <div class="kpws-name">{{ patient_name or '-' }}</div>
      <div class="kpws-line"><span class="kpws-muted">Patient ID / MR No:</span> {{ mr_no }}</div>
      {% if prf %}<div class="kpws-line"><span class="kpws-muted">PRF:</span> {{ prf }}</div>{% endif %}
      <div class="kpws-line"><span class="kpws-muted">Important:</span> Patient is the beneficiary; panel is the bill-to party.</div>
    </div>
  </div>

  <table class="kpws-table">
    <thead>
      <tr>
        <th style="width: 4%;">#</th>
        <th style="width: 42%;">Item</th>
        <th style="width: 12%;" class="right">Qty</th>
        <th style="width: 12%;" class="right">Rate</th>
        <th style="width: 15%;" class="right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for item in doc.items %}
      <tr>
        <td>{{ item.idx }}</td>
        <td>
          <b>{{ item.item_name or item.item_code }}</b>
          {% if item.description and item.description != item.item_name %}<br><span class="kpws-muted">{{ item.description }}</span>{% endif %}
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
    <tr><td class="label grand">Grand Total</td><td class="right grand">{{ doc.get_formatted('grand_total') }}</td></tr>
    <tr><td class="label">Panel Covered Amount</td><td class="right">{{ frappe.utils.fmt_money(covered_amount, currency=doc.currency) }}</td></tr>
    <tr><td class="label">Patient Payable</td><td class="right">{{ frappe.utils.fmt_money(0, currency=doc.currency) }}</td></tr>
    <tr><td class="label">Outstanding Against Panel</td><td class="right">{{ doc.get_formatted('outstanding_amount') }}</td></tr>
  </table>

  <div class="kpws-note">
    This invoice is billed to the panel customer. The patient named above is the actual beneficiary/medicine receiver and must be used for patient audit and medical reference.
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
  <div class="kpws-header">
    <div>
      <h1 class="kpws-title">Welfare Sales Invoice</h1>
      <div class="kpws-subtitle">
        {% if is_welfare_panel %}Welfare Panel billing under {{ purpose }}{% else %}Welfare billing under {{ purpose }}{% endif %}
      </div>
    </div>
    <div class="kpws-meta">
      <div class="kpws-badge">{% if is_welfare_panel %}Welfare Panel{% else %}{{ billing_mode }}{% endif %}</div>
      <div class="kpws-line"><b>Invoice:</b> {{ doc.name }}</div>
      <div class="kpws-line"><b>Date:</b> {{ doc.get_formatted('posting_date') }}</div>
      <div class="kpws-line"><b>Status:</b> {{ doc.status or '-' }}</div>
    </div>
  </div>

  <div class="kpws-grid">
    <div class="kpws-box">
      <div class="kpws-box-title">Bill To / Covering Party</div>
      {% if is_welfare_panel %}
        <div class="kpws-name">{{ panel_customer_name or panel_customer }}</div>
        <div class="kpws-line"><span class="kpws-muted">Customer ID:</span> {{ panel_customer }}</div>
        <div class="kpws-line"><span class="kpws-muted">Mode:</span> Welfare Panel</div>
      {% else %}
        <div class="kpws-name">{{ doc.customer_name }}</div>
        <div class="kpws-line"><span class="kpws-muted">Customer ID:</span> {{ doc.customer }}</div>
        <div class="kpws-line"><span class="kpws-muted">Mode:</span> Welfare</div>
      {% endif %}
      <div class="kpws-line"><span class="kpws-muted">Purpose:</span> {{ purpose }}</div>
      <div class="kpws-line"><span class="kpws-muted">Approved Coverage:</span> {{ percentage }}%</div>
    </div>

    <div class="kpws-box">
      <div class="kpws-box-title">Patient / Medicine Receiver</div>
      <div class="kpws-name">{{ patient_name or '-' }}</div>
      <div class="kpws-line"><span class="kpws-muted">Patient ID / MR No:</span> {{ mr_no }}</div>
      {% if prf %}<div class="kpws-line"><span class="kpws-muted">PRF:</span> {{ prf }}</div>{% endif %}
      <div class="kpws-line"><span class="kpws-muted">Patient Share:</span> {{ frappe.utils.fmt_money(patient_share, currency=doc.currency) }}</div>
    </div>
  </div>

  <table class="kpws-table">
    <thead>
      <tr>
        <th style="width: 4%;">#</th>
        <th style="width: 42%;">Item</th>
        <th style="width: 12%;" class="right">Qty</th>
        <th style="width: 12%;" class="right">Rate</th>
        <th style="width: 15%;" class="right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for item in doc.items %}
      <tr>
        <td>{{ item.idx }}</td>
        <td>
          <b>{{ item.item_name or item.item_code }}</b>
          {% if item.description and item.description != item.item_name %}<br><span class="kpws-muted">{{ item.description }}</span>{% endif %}
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
    <tr><td class="label grand">Grand Total</td><td class="right grand">{{ doc.get_formatted('grand_total') }}</td></tr>
    <tr><td class="label">{{ purpose }} Covered Amount{% if is_welfare_panel %} by Panel{% endif %}</td><td class="right">{{ frappe.utils.fmt_money(covered_amount, currency=doc.currency) }}</td></tr>
    <tr><td class="label">Patient Share</td><td class="right">{{ frappe.utils.fmt_money(patient_share, currency=doc.currency) }}</td></tr>
    {% if patient_cash %}<tr><td class="label">Patient Cash Paid</td><td class="right">{{ frappe.utils.fmt_money(patient_cash, currency=doc.currency) }}</td></tr>{% endif %}
    {% if patient_card %}<tr><td class="label">Patient Card Paid</td><td class="right">{{ frappe.utils.fmt_money(patient_card, currency=doc.currency) }}</td></tr>{% endif %}
    <tr><td class="label">Outstanding</td><td class="right">{{ doc.get_formatted('outstanding_amount') }}</td></tr>
  </table>

  <div class="kpws-note">
    {% if is_welfare_panel %}
      This is a Welfare Panel invoice. The selected panel is the covering/bill-to party for the approved {{ purpose }} percentage. The patient named above is the actual beneficiary/medicine receiver. No internal KPWS Zakat/Donation disbursement should be inferred from this print.
    {% else %}
      This is a Welfare invoice. Coverage is based on the approved Patient Registration Form purpose and percentage. The patient named above is the actual beneficiary/medicine receiver.
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
    data = doc.as_dict()
    json_path = Path(backup_dir) / f"{name.replace(' ', '_')}.json"
    html_path = Path(backup_dir) / f"{name.replace(' ', '_')}.html"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
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

    return {"name": name, "action": action}


@frappe.whitelist()
def apply(backup_dir=None):
    backup_dir = backup_dir or f"/home/easein/kpws-print-format-backup"

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
            row.update({
                "doc_type": doc.doc_type,
                "custom_format": doc.custom_format,
                "print_format_type": doc.print_format_type,
                "disabled": doc.disabled,
                "html_length": len(doc.html or ""),
            })
        out.append(row)
    return out
