frappe.query_reports["KPWS Welfare Approval Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nApproved\nPending Approval\nRejected",
            default: "Approved",
        },
        {
            fieldname: "funding_source",
            label: __("Type"),
            fieldtype: "Select",
            options: "\nZakat\nDonation\nPanel",
            default: "",
        },
        {
            fieldname: "patient",
            label: __("Patient"),
            fieldtype: "Link",
            options: "Patient",
            default: "",
        },
        {
            fieldname: "search_text",
            label: __("Search (Name / MR / KPWS Number)"),
            fieldtype: "Data",
            default: "",
        },
    ],
};
