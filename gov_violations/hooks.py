def post_init_hook(env):
    """Default the analytic plan used for branches and flag the hotels company."""
    plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1)
    for company in env['res.company'].search([]):
        vals = {}
        if plan and not company.gov_violation_branch_plan_id:
            vals['gov_violation_branch_plan_id'] = plan.id
        if 'sustainable' in (company.name or '').lower():
            vals['gov_violation_hotels'] = True
        if vals:
            company.write(vals)
