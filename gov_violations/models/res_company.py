from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    gov_violation_branch_plan_id = fields.Many2one(
        'account.analytic.plan', string='خطة الفروع (المخالفات)',
        help='الخطة التحليلية التي تُختار منها فروع المخالفات. '
             'إذا تُركت فارغة تظهر جميع الحسابات التحليلية للشركة.',
    )
    gov_violation_hotels = fields.Boolean(
        string='شركة الفنادق (المخالفات)',
        help='مخالفات هذه الشركة التي ليس لها فرع EW / EM تُصنَّف ضمن قسم الفنادق.',
    )
