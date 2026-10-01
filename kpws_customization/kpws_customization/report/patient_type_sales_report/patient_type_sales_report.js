frappe.query_reports["Patient Type Sales Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1,
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: "patient_type",
            label: __("Patient Type"),
            fieldtype: "Select",
            options: "\nCash\nWelfare Zakat\nWelfare Donation\nWelfare Panel\nPanel\nPersonal Advance",
            default: "",
        },
    ],
};
