# Backup of the gov_violations data, run BEFORE any install / upgrade / schema
# change (an earlier module update wiped every record and the group
# memberships). Covers both the addon (gov.*) and the importable module (x_gov_*).
# Paste into the MCP execute_orm tool (or odoo-bin shell) and
# save the returned JSON outside the repository. Also take an Odoo.sh backup.
models = ['gov.violation', 'gov.violation.category', 'gov.license.map',
          'x_gov_violation', 'x_gov_violation_category', 'x_gov_license_map']
backup = {'db': env.cr.dbname, 'taken_at': str(datetime.datetime.now()), 'models': {}}
for name in models:
    if name in env:
        Model = env[name].sudo().with_context(active_test=False)
        fields_list = [f for f, fd in Model._fields.items()
                       if fd.store and fd.type not in ('one2many', 'many2many', 'binary')]
        backup['models'][name] = Model.search_read([], fields_list)
groups = env['res.groups'].sudo().search([('privilege_id.name', 'in', ['المخالفات الحكومية', 'Government Violations'])])
backup['groups'] = {g.full_name: g.user_ids.mapped('login') for g in groups}
result = backup
