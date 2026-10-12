# Webapp-level loader (mcp.webapp.data_code) for the gov-violations dashboard.
# Runs on every app load: logs the visit, then returns every violation with
# the objection window computed live from today's date (Riyadh time).
# Records are read with sudo but only for the users the app is shared with.
st = env['mcp.webapp.user.storage'].sudo()
rec = st.search([('webapp_id', '=', mcp_webapp_id), ('user_id', '=', uid)], limit=1)
store = dict(rec.data or {}) if rec else {}
log = list(store.get('_visit_log', []))
log.append({'name': user.name, 'email': user.email or user.login, 'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
store['_visit_log'] = log[-100:]
if rec:
    rec.write({'data': store})
else:
    st.create({'webapp_id': mcp_webapp_id, 'user_id': uid, 'data': store})

app = env['mcp.webapp'].sudo().browse(mcp_webapp_id)
if uid not in app.shared_user_ids.ids:
    result = {'denied': True, 'user': user.name}
else:
    now = datetime.datetime.now() + timedelta(hours=3)
    today = now.date()
    rows = []
    for r in env['x_gov_violation'].sudo().search([], order='x_violation_date desc, id desc'):
        deadline = r.x_objection_deadline
        if not r.x_objection_allowed:
            state = 'not_allowed'
        elif r.x_objection_filed:
            state = 'filed'
        elif not deadline or deadline >= today:
            state = 'open'
        else:
            state = 'expired'
        counted = r.x_status == 'unpaid' and r.x_in_register and not r.x_suspected_duplicate
        rows.append({
            'id': r.id, 'n': r.x_name, 'a': r.x_authority, 'c': r.x_company_id.id,
            'b': r.x_branch_id.name or '', 'dv': r.x_division, 'cat': r.x_category_id.x_name or '',
            'd': str(r.x_violation_date) if r.x_violation_date else '',
            'amt': r.x_amount, 's': r.x_status, 'pd': str(r.x_paid_date) if r.x_paid_date else '',
            'dl': str(deadline) if deadline else '', 'os': state,
            'left': (deadline - today).days if deadline else None,
            'oo': r.x_objection_outcome or '', 'sugg': r.x_deadline_suggested,
            'rv': r.x_needs_review, 'rr': r.x_review_reason or '', 'inr': r.x_in_register,
            'dup': r.x_suspected_duplicate, 'dw': r.x_date_warning, 'cnt': counted,
            'lic': r.x_municipal_license or '', 'mun': r.x_municipality or '',
            'mi': r.x_main_item or '', 'oref': r.x_objection_ref or '',
            'ost': r.x_objection_status_text or '', 'cd': r.x_committee_decision or '',
            'inv': r.x_invoice_number or '', 'sad': r.x_sadad_number or '',
            'desc': (r.x_description or r.x_inspector_note or r.x_reason or '')[:160],
        })
    companies = []
    for c in env['res.company'].sudo().search([], order='id'):
        companies.append({'id': c.id, 'name': c.name})
    result = {'user': user.name, 'today': str(today), 'now': now.strftime('%Y-%m-%d %H:%M'),
              'rows': rows, 'companies': companies}
