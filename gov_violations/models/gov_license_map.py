from odoo import api, fields, models

from .gov_violation import REASON_UNMAPPED_LICENSE


class GovLicenseMap(models.Model):
    """Municipal license -> company / branch.

    The Balady export has no company, branch or EW/EM column, so every row
    imported from it looks its license up here."""
    _name = 'gov.license.map'
    _description = 'ربط الترخيص بالفرع'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='رقم الترخيص البلدي / الهوية', required=True, index=True)
    company_id = fields.Many2one('res.company', string='الشركة', index=True)
    branch_plan_id = fields.Many2one(
        related='company_id.gov_violation_branch_plan_id', string='خطة الفروع',
    )
    branch_id = fields.Many2one(
        'account.analytic.account', string='الفرع', check_company=True,
        domain="[('plan_id', '=?', branch_plan_id)]",
    )
    facility_name = fields.Char(string='اسم المنشأة')
    inferred = fields.Boolean(
        string='ربط استنتاجي',
        help='الربط مستنتج من مخالفات سابقة ولم يُؤكَّد بعد.',
    )
    note = fields.Char(string='ملاحظة')
    active = fields.Boolean(string='نشط', default=True)
    violation_count = fields.Integer(string='عدد المخالفات', compute='_compute_violation_count')
    is_mapped = fields.Boolean(string='مربوط', compute='_compute_is_mapped', store=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'رقم الترخيص مسجل مسبقاً.')

    @api.depends('branch_id', 'company_id.gov_violation_hotels')
    def _compute_is_mapped(self):
        for mapping in self:
            mapping.is_mapped = bool(mapping.branch_id or mapping.company_id.gov_violation_hotels)

    def _compute_violation_count(self):
        data = self.env['gov.violation'].with_context(active_test=False)._read_group(
            [('municipal_license', 'in', self.mapped('name'))],
            ['municipal_license'], ['__count'],
        )
        counts = dict(data)
        for mapping in self:
            mapping.violation_count = counts.get(mapping.name, 0)

    def action_view_violations(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'gov_violations.action_gov_violation')
        action['domain'] = [('municipal_license', '=', self.name)]
        action['context'] = {'active_test': False}
        return action

    def action_apply_to_violations(self):
        """Push company / branch of the mapping to the municipal violations of
        this license and clear their 'unmapped license' review reason."""
        Violation = self.env['gov.violation'].with_context(active_test=False)
        for mapping in self.filtered('is_mapped'):
            violations = Violation.search([('municipal_license', '=', mapping.name)])
            vals = {'branch_id': mapping.branch_id.id}
            if mapping.company_id:
                vals['company_id'] = mapping.company_id.id
            violations.write(vals)
            violations._unflag_review(REASON_UNMAPPED_LICENSE)
        return True
