# GET visitors — who opened the dashboard (from the loader's _visit_log).
recs = env['mcp.webapp.user.storage'].sudo().search_read([('webapp_id', '=', mcp_webapp_id)], ['user_id', 'data'])
out = []
for r in recs:
    lg = (r['data'] or {}).get('_visit_log', [])
    if lg:
        out.append({'name': lg[-1].get('name'), 'email': lg[-1].get('email'), 'visits': len(lg), 'last_visit': lg[-1].get('ts'), 'user_id': r['user_id'][0] if r['user_id'] else None})
result = out
