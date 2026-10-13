from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gov_violation_branch_plan_id = fields.Many2one(
        related='company_id.gov_violation_branch_plan_id', readonly=False,
    )
    gov_violation_hotels = fields.Boolean(
        related='company_id.gov_violation_hotels', readonly=False,
    )
    gov_violation_reminder_days = fields.Integer(
        string='تذكير الاعتراض (أيام قبل الموعد)',
        config_parameter='gov_violations.reminder_days',
        default=7,
    )
