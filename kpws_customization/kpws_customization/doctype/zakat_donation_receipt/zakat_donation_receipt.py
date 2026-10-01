# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


INCOME_ACCOUNT_MAPPING = {"Zakat": "Zakat Income", "Donation": "Donation Income"}


def get_default_company():
	comp = frappe.db.get_single_value("Global Defaults", "default_company")
	if not comp:
		frappe.throw(_("Set Default Company in Global Defaults."))
	return comp


def get_income_account(short_name, company):
	acc = frappe.db.get_value("Account", {"company": company, "account_name": short_name, "disabled": 0}, "name")
	if acc:
		return acc
	rows = frappe.get_all("Account", filters={"company": company, "disabled": 0}, fields=["name","account_name"], limit=200)
	for r in rows:
		if (r.account_name or "").strip().lower() == short_name.strip().lower():
			return r.name
	for r in rows:
		if short_name.strip().lower() in (r.account_name or "").lower():
			return r.name
	frappe.throw(_("Income account not found for: {0}").format(short_name))


def get_receivable_account(company):
	acc = frappe.db.get_value("Company", company, "default_receivable_account")
	if acc:
		return acc
	acc = frappe.db.get_value("Account", {"company": company, "account_type": "Receivable", "disabled": 0}, "name")
	if acc:
		return acc
	frappe.throw(_("Set Default Receivable Account in Company."))


class ZakatDonationReceipt(Document):
	def on_submit(self):
		# Main logic
		if self.journal_entry:
			# Journal Entry already exists, skip creation
			return

		if flt(self.amount_in_pkr) <= 0:
			frappe.throw(_("Amount in PKR must be greater than zero."))
		if not self.payment_account:
			frappe.throw(_("Please select Payment Account."))

		try:
			company = self.company or get_default_company()
			amount = flt(self.amount_in_pkr, 2)

			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Journal Entry"
			je.company = company
			je.posting_date = self.receipt_date or nowdate()
			je.user_remark = f"Receipt {self.name} | Donor: {self.received_from or ''} | Patient: {self.received_for or ''} | {self.on_account_of or ''} | {self.purpose or ''}"

			# Debit: Cash/Bank account
			je.append("accounts", {
				"account": self.payment_account,
				"debit": amount,
				"debit_in_account_currency": amount,
			})

			# Credit: Income or Patient Advance
			if not self.received_for:
				# No patient specified - credit to Income account (Zakat/Donation Income)
				if not self.on_account_of:
					frappe.throw(_("Please select On Account Of (Zakat/Donation)."))
				income_acc = get_income_account(INCOME_ACCOUNT_MAPPING.get(self.on_account_of), company)
				je.append("accounts", {
					"account": income_acc,
					"credit": amount,
					"credit_in_account_currency": amount,
				})
			else:
				# Patient specified - credit to Patient's Customer account as advance
				# This ensures the donation is tagged to the patient and shows in patient balance
				patient_customer = frappe.db.get_value("Patient", self.received_for, "customer")
				if not patient_customer:
					frappe.throw(_("Patient is not linked to a Customer. Please link the Patient to a Customer."))
				
				# Get patient name for better tracking
				patient_name = frappe.db.get_value("Patient", self.received_for, "patient_name")
				
				receivable = get_receivable_account(company)
				account_entry = {
					"account": receivable,
					"party_type": "Customer",
					"party": patient_customer,
					"is_advance": "Yes",
					"credit": amount,
					"credit_in_account_currency": amount,
				}
				
				# Add remark to account entry for better tracking
				donation_type = f" ({self.on_account_of})" if self.on_account_of else ""
				account_entry["user_remark"] = f"Donation for Patient: {patient_name or self.received_for}{donation_type} | Receipt: {self.name}"
				
				je.append("accounts", account_entry)

			if getattr(self, "voucher_reference", None):
				je.cheque_no = self.voucher_reference
			if getattr(self, "drawn_on", None):
				je.cheque_no = je.cheque_no or self.drawn_on
				je.cheque_date = self.receipt_date

			je.insert(ignore_permissions=True)
			je.submit()
			
			# Update the receipt with journal entry reference
			frappe.db.set_value(self.doctype, self.name, "journal_entry", je.name)
			frappe.db.commit()
			
			frappe.msgprint(_("Journal Entry {0} created and submitted.").format(je.name))
		except Exception as e:
			frappe.log_error(f"Error creating Journal Entry for {self.doctype} {self.name}: {str(e)}", "Zakat Donation Receipt - Journal Entry Creation")
			frappe.throw(_("Error creating Journal Entry: {0}").format(str(e)))
