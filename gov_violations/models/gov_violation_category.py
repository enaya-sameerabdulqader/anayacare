from odoo import fields, models

from .gov_violation import AUTHORITY_SELECTION


class GovViolationCategory(models.Model):
    _name = 'gov.violation.category'
    _description = 'تصنيف المخالفة'
    _order = 'sequence, name, id'

    name = fields.Char(string='التصنيف', required=True, translate=True)
    sequence = fields.Integer(string='التسلسل', default=10)
    active = fields.Boolean(string='نشط', default=True)
    authority = fields.Selection(
        selection=AUTHORITY_SELECTION, string='الجهة',
        help='اتركها فارغة إذا كان التصنيف ينطبق على جميع الجهات.',
    )
    keywords = fields.Char(
        string='كلمات مفتاحية',
        help='كلمات مفصولة بفاصلة (,). تُستخدم عند الاستيراد لاقتراح التصنيف من '
             'ملاحظات المراقب ثم بند المخالفة الرئيسي ثم الوصف. '
             'يُعتمد أول تصنيف (حسب التسلسل) تظهر إحدى كلماته في النص.',
    )
    violation_count = fields.Integer(
        string='عدد المخالفات', compute='_compute_violation_count',
    )

    _name_authority_uniq = models.Constraint(
        'UNIQUE(name, authority)',
        'يوجد تصنيف بنفس الاسم لهذه الجهة.',
    )

    def _keyword_list(self):
        self.ensure_one()
        return [k.strip() for k in (self.keywords or '').split(',') if k.strip()]

    def _matches(self, text):
        self.ensure_one()
        text = (text or '').casefold()
        return any(k.casefold() in text for k in self._keyword_list())

    def _compute_violation_count(self):
        data = self.env['gov.violation']._read_group(
            [('category_id', 'in', self.ids)], ['category_id'], ['__count'],
        )
        counts = {category.id: count for category, count in data}
        for category in self:
            category.violation_count = counts.get(category.id, 0)

    def action_view_violations(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'gov_violations.action_gov_violation')
        action['domain'] = [('category_id', '=', self.id)]
        action['context'] = {'default_category_id': self.id}
        return action
