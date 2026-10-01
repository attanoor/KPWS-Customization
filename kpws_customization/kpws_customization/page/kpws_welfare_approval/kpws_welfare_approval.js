frappe.pages['kpws-welfare-approval'].on_page_load = function(wrapper) {


    window.kpws_welfare_approval_v80 = new KPWSWelfareApprovalV80(wrapper);
};

class KPWSWelfareApprovalV80 {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.current = null;
        this.panels_loaded = false;

        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: 'KPWS Welfare Approval',
            single_column: true
        });

        this.page.add_button(__('View Report'), () => {
            frappe.set_route('query-report', 'KPWS Welfare Approval Report');
        }, { icon: 'small-line-chart' });

        this.render();
        this.bind();
        this.load_panels();
        this.refresh_counts();
        this.search();
    }

    api(method, args, callback) {
        frappe.call({
            method: 'kpws_customization.api.kpws_welfare_approval_v80.' + method,
            args: args || {},
            freeze: true,
            callback: callback
        });
    }

    render() {
        $(this.page.body).html(`
            <style>
                .kpws-wa {background:#f6f7fb;min-height:calc(100vh - 110px);padding:16px;}
                .kpws-wa-top {display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:12px;margin-bottom:14px;}
                .kpws-wa-stat {background:white;border:1px solid #e5e7eb;border-radius:14px;padding:14px;box-shadow:0 2px 8px rgba(0,0,0,.04);}
                .kpws-wa-stat .n {font-size:24px;font-weight:900;color:#111827;}
                .kpws-wa-stat .l {font-size:12px;font-weight:700;color:#64748b;}
                .kpws-wa-main {display:grid;grid-template-columns:370px 1fr;gap:14px;}
                .kpws-card {background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:14px;box-shadow:0 2px 8px rgba(0,0,0,.04);}
                .kpws-title {font-size:17px;font-weight:900;color:#111827;margin-bottom:10px;}
                .kpws-list {max-height:calc(100vh - 290px);overflow:auto;padding-right:4px;}
                .kpws-row {border:1px solid #e5e7eb;border-radius:12px;padding:10px;margin-bottom:8px;cursor:pointer;background:#fff;}
                .kpws-row:hover {border-color:#2563eb;background:#eff6ff;}
                .kpws-row.active {border-color:#2563eb;background:#dbeafe;}
                .kpws-row .name {font-weight:900;color:#111827;}
                .kpws-row .meta {font-size:12px;color:#64748b;margin-top:2px;}
                .kpws-badge {display:inline-block;padding:4px 9px;border-radius:999px;background:#eef2ff;color:#3730a3;font-weight:800;margin:2px;font-size:12px;}
                .kpws-badge.orange {background:#fff7ed;color:#c2410c;}
                .kpws-badge.green {background:#ecfdf5;color:#047857;}
                .kpws-badge.red {background:#fef2f2;color:#b91c1c;}
                .kpws-grid {display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:12px;}
                .kpws-grid-3 {display:grid;grid-template-columns:repeat(3,minmax(170px,1fr));gap:12px;}
                .kpws-field label {font-size:12px;font-weight:800;color:#374151;margin-bottom:5px;display:block;}
                .kpws-field input,.kpws-field select,.kpws-field textarea {width:100%;border:1px solid #d1d5db;border-radius:9px;padding:8px 10px;min-height:38px;background:#fff;}
                .kpws-field textarea {min-height:70px;}
                .kpws-actions {display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;}
                .hidden {display:none !important;}
                @media(max-width:1050px){.kpws-wa-main{grid-template-columns:1fr}.kpws-grid{grid-template-columns:repeat(2,minmax(150px,1fr));}}
                @media(max-width:650px){.kpws-wa-top,.kpws-grid,.kpws-grid-3{grid-template-columns:1fr;}}
            </style>

            <div class="kpws-wa">
                <div class="kpws-wa-top">
                    <div class="kpws-wa-stat"><div class="n" id="cnt_pending">0</div><div class="l">Pending</div></div>
                    <div class="kpws-wa-stat"><div class="n" id="cnt_approved">0</div><div class="l">Approved</div></div>
                    <div class="kpws-wa-stat"><div class="n" id="cnt_rejected">0</div><div class="l">Rejected</div></div>
                    <div class="kpws-wa-stat"><div class="n" id="cnt_total">0</div><div class="l">Total Requests</div></div>
                </div>

                <div class="kpws-wa-main">
                    <div class="kpws-card">
                        <div class="kpws-title">Requests</div>
                        <div class="kpws-field">
                            <label>Search PRF / Patient / Name / Kiran MR / CNIC</label>
                            <input id="wa_search" placeholder="Search request...">
                        </div>
                        <div class="kpws-grid-3" style="margin-top:8px;grid-template-columns:1fr 100px 90px;">
                            <div class="kpws-field">
                                <select id="wa_status">
                                    <option value="Pending">Pending</option>
                                    <option value="Approved">Approved</option>
                                    <option value="Rejected">Rejected</option>
                                    <option value="All">All</option>
                                </select>
                            </div>
                            <button class="btn btn-primary" id="wa_search_btn">Search</button>
                            <button class="btn btn-default" id="wa_refresh_btn">Refresh</button>
                        </div>
                        <div id="wa_list" class="kpws-list" style="margin-top:12px;"></div>
                    </div>

                    <div class="kpws-card">
                        <div class="kpws-title">Request Review</div>
                        <div id="wa_empty">
                            <span class="kpws-badge">Select a request from the left side</span>
                        </div>

                        <div id="wa_form" class="hidden">
                            <div id="wa_header" style="margin-bottom:12px;"></div>

                            <div class="kpws-title">Patient Details</div>
                            <div class="kpws-grid">
                                <div class="kpws-field"><label>First Name *</label><input id="first_name"></div>
                                <div class="kpws-field"><label>Last Name</label><input id="last_name"></div>
                                <div class="kpws-field"><label>Son of/Daughter of/Wife of</label><input id="relation_name"></div>
                                <div class="kpws-field"><label>CNIC *</label><input id="cnic"></div>

                                <div class="kpws-field"><label>Kiran MR Number</label><input id="mr_number"></div>
                                <div class="kpws-field"><label>Old KPWS Number</label><input id="old_kpws_number"></div>
                                <div class="kpws-field"><label>Religion</label><input id="religion"></div>
                                <div class="kpws-field"><label>Saction</label><input id="sanction"></div>
                                <div class="kpws-field"><label>Nationality</label><input id="nationality"></div>
                                <div class="kpws-field"><label>Age *</label><input id="age" type="number" min="0"></div>
                                <div class="kpws-field">
                                    <label>Gender *</label>
                                    <select id="sex">
                                        <option value="">Select</option>
                                        <option value="Male">Male</option>
                                        <option value="Female">Female</option>
                                        <option value="Other">Other</option>
                                    </select>
                                </div>

                                <div class="kpws-field"><label>Mobile</label><input id="mobile"></div>
                                <div class="kpws-field">
                                    <label>Patient Status</label>
                                    <select id="patient_status">
                                        <option value="SE">SE</option>
                                        <option value="E">E</option>
                                        <option value="NE">NE</option>
                                        <option value="P">P</option>
                                        <option value="PE">PE</option>
                                    </select>
                                </div>
                                <div class="kpws-field"><label>Linked Customer</label><input id="customer" readonly></div>
                                <div class="kpws-field"><label>Patient Type</label><input id="patient_type" readonly value="Welfare"></div>
                            </div>

                            <div class="kpws-title" style="margin-top:14px;">Address</div>
                            <div class="kpws-grid">
                                <div class="kpws-field"><label>Address Line 1</label><input id="address_line1"></div>
                                <div class="kpws-field"><label>Address Line 2</label><input id="address_line2"></div>
                                <div class="kpws-field"><label>Area / Mohalla</label><input id="area_mohalla"></div>
                                <div class="kpws-field"><label>City</label><input id="city"></div>
                                <div class="kpws-field"><label>District</label><input id="district"></div>
                                <div class="kpws-field"><label>Province</label><input id="province"></div>
                                <div class="kpws-field"><label>Postal Code</label><input id="postal_code"></div>
                                <div class="kpws-field"><label>Country</label><input id="country"></div>
                            </div>

                            <div class="kpws-field" style="margin-top:12px;">
                                <label>Patient Notes</label>
                                <textarea id="patient_details"></textarea>
                            </div>

                            <hr>

                            <div class="kpws-title">Welfare Decision</div>
                            <div class="kpws-grid">
                                <div class="kpws-field">
                                    <label>Funding Source *</label>
                                    <select id="funding_source">
                                        <option value="Zakat">Zakat</option>
                                        <option value="Donation">Donation</option>
                                        <option value="Panel">Panel</option>
                                    </select>
                                </div>
                                <div class="kpws-field">
                                    <label>Coverage Percentage</label>
                                    <input id="percentage" type="number" min="0" max="100">
                                </div>
                                <div class="kpws-field" id="panel_wrap">
                                    <label>Panel Customer</label>
                                    <select id="panel_customer"><option value="">Loading panels...</option></select>
                                </div>
                                <div class="kpws-field">
                                    <label>Workflow Status</label>
                                    <input id="workflow_state" readonly>
                                </div>
                            </div>

                            <div class="kpws-actions">
                                <button class="btn btn-primary" id="save_btn">Save / Admin Override</button>
                                <button class="btn btn-success" id="approve_btn">Approve Request</button>
                                <button class="btn btn-danger" id="reject_btn">Reject Request</button>
                                <button class="btn btn-default" id="open_prf_btn">Open PRF</button>
                                <button class="btn btn-default" id="print_prf_btn">Print PRF</button>
                                <button class="btn btn-default" id="open_patient_btn">Open Patient</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `);
    }

    bind() {
        $('#wa_search_btn, #wa_refresh_btn').on('click', () => this.search());
        $('#wa_search').on('keyup', frappe.utils.debounce(() => this.search(), 500));
        $('#wa_status').on('change', () => this.search());
        $('#funding_source').on('change', () => this.toggle_panel());

        $('#save_btn').on('click', () => this.save());
        $('#approve_btn').on('click', () => this.approve());
        $('#reject_btn').on('click', () => this.reject());
        $('#open_prf_btn').on('click', () => this.open_prf());
        $('#print_prf_btn').on('click', () => this.print_prf());
        $('#open_patient_btn').on('click', () => this.open_patient());
    }

    val(id) {
        return ($('#' + id).val() || '').trim();
    }

    set(id, value) {
        $('#' + id).val(value || '');
    }

    refresh_counts() {
        this.api('get_counts', {}, (r) => {
            const c = r.message || {};
            $('#cnt_pending').text(c.pending || 0);
            $('#cnt_approved').text(c.approved || 0);
            $('#cnt_rejected').text(c.rejected || 0);
            $('#cnt_total').text(c.total || 0);
        });
    }

    load_panels(selected) {
        this.api('get_panel_customers', {}, (r) => {
            let html = '<option value="">Select Panel</option>';
            (r.message || []).forEach(row => {
                html += `<option value="${frappe.utils.escape_html(row.value)}">${frappe.utils.escape_html(row.label)}</option>`;
            });
            $('#panel_customer').html(html);
            if (selected) $('#panel_customer').val(selected);
            this.panels_loaded = true;
        });
    }

    search() {
        this.api('search_requests', {
            txt: this.val('wa_search'),
            status: this.val('wa_status') || 'Pending',
            limit: 80
        }, (r) => {
            const rows = r.message || [];
            if (!rows.length) {
                $('#wa_list').html('<div class="text-muted">No requests found.</div>');
                return;
            }

            let html = '';
            rows.forEach(row => {
                const state = row.workflow_state || (row.docstatus === 1 ? 'Submitted' : 'Draft');
                const badge = state === 'Approved' ? 'green' : (state === 'Rejected' ? 'red' : 'orange');
                const name = row.patient_name || [row.first_name, row.last_name].filter(Boolean).join(' ') || row.patient || '';

                html += `
                    <div class="kpws-row" data-name="${row.name}">
                        <div class="name">${row.name}</div>
                        <div>${frappe.utils.escape_html(name)}</div>
                        <div class="meta">Patient: ${row.patient || '-'} | MR: ${row.custom_reference_number || '-'}</div>
                        <span class="kpws-badge ${badge}">${state || '-'}</span>
                        <span class="kpws-badge">${row.funding_source || '-'}</span>
                        <span class="kpws-badge">${flt(row.percentage || 0)}%</span>
                    </div>
                `;
            });

            $('#wa_list').html(html);

            $('.kpws-row').on('click', (e) => {
                $('.kpws-row').removeClass('active');
                $(e.currentTarget).addClass('active');
                this.load($(e.currentTarget).data('name'));
            });
        });

        this.refresh_counts();
    }

    load(name) {
        this.api('get_request', {name}, (r) => {
            this.apply(r.message);
        });
    }

    apply(data) {
        if (!data || !data.request) return;

        this.current = data.request.name;

        const req = data.request;
        const p = data.patient || {};

        $('#wa_empty').addClass('hidden');
        $('#wa_form').removeClass('hidden');

        const state = req.workflow_state || (req.docstatus === 1 ? 'Submitted' : 'Draft');
        $('#wa_header').html(`
            <span class="kpws-badge">PRF: ${req.name}</span>
            <span class="kpws-badge">Patient: ${p.name || '-'}</span>
            <span class="kpws-badge orange">Status: ${state}</span>
        `);

        this.set('first_name', p.first_name);
        this.set('last_name', p.last_name);
        this.set('relation_name', p.relation_name);
        this.set('cnic', p.cnic);
        this.set('mr_number', p.mr_number);
        this.set('old_kpws_number', p.old_kpws_number);
        this.set('religion', p.religion);
        this.set('sanction', p.sanction);
        this.set('nationality', p.nationality);
        this.set('age', p.age);
        this.set('sex', p.sex);
        this.set('mobile', p.mobile);
        this.set('patient_status', p.patient_status || 'SE');
        this.set('customer', p.customer || '');
        this.set('patient_type', 'Welfare');
        this.set('patient_details', p.patient_details || '');
        ['address_line1','address_line2','area_mohalla','city','district','province','postal_code','country'].forEach((f) => this.set(f, p[f] || ''));

        this.set('funding_source', req.funding_source || 'Zakat');
        this.set('percentage', req.percentage || 100);
        this.set('workflow_state', state);

        this.load_panels(req.panel_customer || '');
        setTimeout(() => {
            this.set('panel_customer', req.panel_customer || '');
            this.toggle_panel();
        }, 300);

        if (req.docstatus === 1 || state === 'Approved') {
            // Approved forms can still be updated by Administrator as override.
            $('#save_btn').prop('disabled', false).text('Save / Admin Override');
            $('#approve_btn').prop('disabled', false).text('Save Override + Keep Approved');
            $('#reject_btn').prop('disabled', true);
        } else {
            $('#save_btn').prop('disabled', false).text('Save Changes');
            $('#approve_btn').prop('disabled', false).text('Approve Request');
            $('#reject_btn').prop('disabled', false);
        }
    }

    toggle_panel() {
        const source = this.val('funding_source');
        $('#panel_wrap').toggleClass('hidden', source !== 'Panel');

        if (source !== 'Panel') {
            this.set('panel_customer', '');
        }
    }

    payload() {
        return {
            name: this.current,
            first_name: this.val('first_name'),
            last_name: this.val('last_name'),
            relation_name: this.val('relation_name'),
            cnic: this.val('cnic'),
            mr_number: this.val('mr_number'),
            old_kpws_number: this.val('old_kpws_number'),
            religion: this.val('religion'),
            sanction: this.val('sanction'),
            nationality: this.val('nationality'),
            age: this.val('age'),
            sex: this.val('sex'),
            mobile: this.val('mobile'),
            patient_status: this.val('patient_status') || 'SE',
            patient_details: this.val('patient_details'),
            address_line1: this.val('address_line1'),
            address_line2: this.val('address_line2'),
            area_mohalla: this.val('area_mohalla'),
            city: this.val('city'),
            district: this.val('district'),
            province: this.val('province'),
            postal_code: this.val('postal_code'),
            country: this.val('country'),
            funding_source: this.val('funding_source'),
            percentage: this.val('percentage') || 100,
            panel_customer: this.val('panel_customer')
        };
    }

    save() {
        if (!this.current) return frappe.msgprint('Select a request first.');

        this.api('save_request', {payload: JSON.stringify(this.payload())}, (r) => {
            frappe.show_alert({message: 'Request updated.', indicator: 'green'});
            this.apply(r.message);
            this.search();
        });
    }

    approve() {
        if (!this.current) return frappe.msgprint('Select a request first.');

        frappe.confirm('Approve this welfare registration request?', () => {
            this.api('approve_request', {payload: JSON.stringify(this.payload())}, (r) => {
                frappe.show_alert({message: 'Request approved.', indicator: 'green'});
                this.apply(r.message);
                this.search();
            });
        });
    }

    reject() {
        if (!this.current) return frappe.msgprint('Select a request first.');

        frappe.prompt([
            {fieldname: 'reason', label: 'Rejection Reason', fieldtype: 'Small Text', reqd: 0}
        ], (v) => {
            this.api('reject_request', {name: this.current, reason: v.reason}, (r) => {
                frappe.show_alert({message: 'Request rejected.', indicator: 'orange'});
                this.apply(r.message);
                this.search();
            });
        }, 'Reject Request', 'Reject');
    }

    open_prf() {
        if (!this.current) return;
        frappe.set_route('Form', 'Patient Registration Form', this.current);
    }

    print_prf() {
        if (!this.current) return;
        window.open(`/printview?doctype=Patient%20Registration%20Form&name=${encodeURIComponent(this.current)}&format=Standard&trigger_print=1&no_letterhead=0`, '_blank');
    }

    open_patient() {
        const header = $('#wa_header').text() || '';
        const match = header.match(/Patient:\s*(KPWS-\d+)/);
        if (match) frappe.set_route('Form', 'Patient', match[1]);
    }
}


// KPWS_WELFARE_APPROVAL_ZAKAT_DONATION_OPTIONAL_PANEL_UI_V83
(function () {
    function installZakatDonationPanelRule() {
        if (typeof KPWSWelfareApprovalV80 === "undefined") return;

        KPWSWelfareApprovalV80.prototype.toggle_panel = function () {
            const source = this.val('funding_source');

            // Final rule:
            // Zakat    = optional panel
            // Donation = optional panel
            // Panel    = required panel
            const showPanel = ['Zakat', 'Donation', 'Panel'].includes(source);

            $('#panel_wrap').toggleClass('hidden', !showPanel);

            const $label = $('#panel_wrap label');

            if (source === 'Panel') {
                $label.text('Panel Customer *');
            } else if (source === 'Zakat') {
                $label.text('Panel Customer (Optional for Zakat)');
            } else if (source === 'Donation') {
                $label.text('Panel Customer (Optional for Donation)');
            } else {
                $label.text('Panel Customer');
            }
        };

        const oldPayload = KPWSWelfareApprovalV80.prototype.payload;

        KPWSWelfareApprovalV80.prototype.payload = function () {
            const p = oldPayload.call(this);

            // Do not clear panel for Zakat or Donation.
            // Backend will validate if a panel is selected.
            return p;
        };

        if (window.kpws_welfare_approval_v80) {
            window.kpws_welfare_approval_v80.toggle_panel();
        }
    }

    installZakatDonationPanelRule();
    setTimeout(installZakatDonationPanelRule, 1000);
    setTimeout(installZakatDonationPanelRule, 2500);

    $(document).on('change', '#funding_source', function () {
        if (window.kpws_welfare_approval_v80) {
            window.kpws_welfare_approval_v80.toggle_panel();
        }
    });
})();


// KPWS_WELFARE_APPROVAL_ZAKAT_DONATION_OPTIONAL_PANEL_UI_V83
(function () {
    function installZakatDonationPanelRule() {
        if (typeof KPWSWelfareApprovalV80 === "undefined") return;

        KPWSWelfareApprovalV80.prototype.toggle_panel = function () {
            const source = this.val('funding_source');

            // Final rule:
            // Zakat    = optional panel
            // Donation = optional panel
            // Panel    = required panel
            const showPanel = ['Zakat', 'Donation', 'Panel'].includes(source);

            $('#panel_wrap').toggleClass('hidden', !showPanel);

            const $label = $('#panel_wrap label');

            if (source === 'Panel') {
                $label.text('Panel Customer *');
            } else if (source === 'Zakat') {
                $label.text('Panel Customer (Optional for Zakat)');
            } else if (source === 'Donation') {
                $label.text('Panel Customer (Optional for Donation)');
            } else {
                $label.text('Panel Customer');
            }
        };

        const oldPayload = KPWSWelfareApprovalV80.prototype.payload;

        KPWSWelfareApprovalV80.prototype.payload = function () {
            const p = oldPayload.call(this);

            // Do not clear panel for Zakat or Donation.
            // Backend will validate if a panel is selected.
            return p;
        };

        if (window.kpws_welfare_approval_v80) {
            window.kpws_welfare_approval_v80.toggle_panel();
        }
    }

    installZakatDonationPanelRule();
    setTimeout(installZakatDonationPanelRule, 1000);
    setTimeout(installZakatDonationPanelRule, 2500);

    $(document).on('change', '#funding_source', function () {
        if (window.kpws_welfare_approval_v80) {
            window.kpws_welfare_approval_v80.toggle_panel();
        }
    });
})();
