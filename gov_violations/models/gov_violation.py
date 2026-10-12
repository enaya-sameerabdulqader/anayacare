import re
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

AUTHORITY_SELECTION = [
    ('labor', 'مكتب العمل'),
    ('municipality', 'البلدية'),
    ('other', 'جهة أخرى'),
]

STATUS_SELECTION = [
    ('unpaid', 'غير مسددة'),
    ('paid', 'مسددة'),
    ('cancelled', 'ملغية'),
    ('linked', 'مرتبطة بدون غرامة'),
]

DIVISION_SELECTION = [
    ('ew', 'سيدات (EW)'),
    ('em', 'رجال (EM)'),
    ('hotels', 'الفنادق'),
    ('unalloc', 'غير مرتبط بفرع'),
]

SOURCE_SELECTION = [
    ('balady', 'ملف بلدي'),
    ('history', 'السجل الموحد (تاريخي)'),
    ('manual', 'إدخال يدوي'),
]

# Balady "invoice status" values -> payment status
BALADY_STATUS = {
    'غير مسددة': 'unpaid',
    'مسددة': 'paid',
    'ملغية': 'cancelled',
    'ملغاة': 'cancelled',
}

# Main-item values that carry no information ("1", "1 | 2", ...)
EMPTY_MAIN_ITEM_RE = re.compile(r'^[\d\s|]*$')

MANAGER_GROUP = 'gov_violations.group_gov_violation_manager'

# Fields a non-manager may still edit after a violation is paid or cancelled.
LOCKED_EDITABLE_FIELDS = {
    'note',
    'user_id',
    'objection_filed',
    'objection_filed_date',
    'objection_outcome',
}

# Reasons written by the system into review_reason (kept in one place so the
# import can add / remove them without touching reasons typed by users).
REASON_NOT_IN_REGISTER = 'غير موجودة في آخر ملف بلدي - تحقق من السداد أو الإلغاء'
REASON_UNMAPPED_LICENSE = 'الترخيص غير مربوط بفرع'
REASON_STATUS_CONFLICT = 'بلدي يظهرها غير مسددة بينما حالتها في النظام'


class GovViolation(models.Model):
    """Government violations register (labor office, municipality, other authorities)."""
    _name = 'gov.violation'
    _description = 'مخالفة حكومية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'violation_date desc, id desc'
    _check_company_auto = True
    _rec_names_search = ['name', 'sadad_number', 'invoice_number', 'objection_ref']

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    name = fields.Char(
        string='رقم المخالفة', required=True, tracking=True, index=True,
        copy=False,
    )
    active = fields.Boolean(string='نشط', default=True, tracking=True)
    authority = fields.Selection(
        selection=AUTHORITY_SELECTION, string='الجهة',
        required=True, tracking=True, index=True,
    )
    source = fields.Selection(
        selection=SOURCE_SELECTION, string='المصدر', default='manual',
        required=True, copy=False,
    )
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True, index=True,
        ondelete='restrict', tracking=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='العملة', store=True,
    )
    branch_plan_id = fields.Many2one(
        related='company_id.gov_violation_branch_plan_id',
        string='خطة الفروع',
    )
    branch_id = fields.Many2one(
        'account.analytic.account', string='الفرع', index=True,
        ondelete='set null', tracking=True, check_company=True,
        domain="[('plan_id', '=?', branch_plan_id)]",
    )
    division = fields.Selection(
        selection=DIVISION_SELECTION, string='القسم',
        compute='_compute_division', store=True, index=True,
    )
    category_id = fields.Many2one(
        'gov.violation.category', string='التصنيف', ondelete='restrict',
        tracking=True,
        domain="['|', ('authority', '=', False), ('authority', '=', authority)]",
    )
    violation_code = fields.Char(string='رمز المخالفة')
    reason = fields.Char(string='سبب المخالفة')
    description = fields.Text(string='وصف المخالفة')
    violation_date = fields.Date(
        string='تاريخ المخالفة', index=True, tracking=True,
    )

    # ------------------------------------------------------------------
    # Payment
    # ------------------------------------------------------------------
    amount = fields.Monetary(
        string='قيمة الغرامة (ريال)', tracking=True,
        currency_field='currency_id',
    )
    status = fields.Selection(
        selection=STATUS_SELECTION, string='حالة السداد', required=True,
        default='unpaid', tracking=True, index=True, copy=False,
    )
    paid_date = fields.Date(string='تاريخ السداد', tracking=True, copy=False)
    # Numbers are TEXT on purpose: Excel turns them into scientific notation.
    sadad_number = fields.Char(string='رقم السداد', copy=False)
    invoice_number = fields.Char(string='رقم الفاتورة', copy=False)
    offender_ref = fields.Char(string='رقم المخالف / هوية العامل')

    # ------------------------------------------------------------------
    # Objection
    # ------------------------------------------------------------------
    objection_allowed = fields.Boolean(string='الاعتراض مسموح', default=True)
    objection_deadline = fields.Date(
        string='آخر موعد للاعتراض', tracking=True, index=True,
    )
    deadline_suggested = fields.Boolean(
        string='موعد اعتراض مقترح',
        help='الموعد محسوب تقديرياً وليس من المصدر.',
    )
    objection_filed = fields.Boolean(
        string='تم تقديم اعتراض', tracking=True, copy=False,
    )
    objection_filed_date = fields.Date(string='تاريخ تقديم الاعتراض', copy=False)
    objection_outcome = fields.Selection(
        selection=[
            ('pending', 'قيد النظر'),
            ('accepted', 'مقبول'),
            ('rejected', 'مرفوض'),
        ],
        string='نتيجة الاعتراض', tracking=True, copy=False,
        compute='_compute_objection_filed_values', store=True, readonly=False,
    )
    objection_ref = fields.Char(string='رقم طلب الاعتراض', copy=False, index=True)
    objection_status_text = fields.Char(string='حالة طلب الاعتراض', copy=False)
    committee_decision = fields.Char(string='قرار لجنة الاعتراض', copy=False)
    objection_reminder_sent = fields.Boolean(
        string='تم إرسال تذكير الاعتراض', copy=False, readonly=True,
    )

    # ------------------------------------------------------------------
    # Balady
    # ------------------------------------------------------------------
    municipal_license = fields.Char(string='رقم الترخيص البلدي / الهوية', index=True)
    license_type = fields.Char(string='نوع الترخيص البلدي')
    municipality = fields.Char(string='الأمانة / البلدية', index=True)
    establishment = fields.Char(string='اسم المنشأة')
    regulation_clause = fields.Char(string='بند اللائحة')
    repeat_count = fields.Integer(string='عدد مرات التكرار')
    units = fields.Integer(string='عدد وحدات المخالفة')
    main_item = fields.Char(string='بند المخالفة الرئيسي')
    inspector_note = fields.Text(string='ملاحظات المراقب')

    # ------------------------------------------------------------------
    # Data quality / follow-up
    # ------------------------------------------------------------------
    in_register = fields.Boolean(
        string='موجودة في سجل بلدي', default=True, copy=False,
        help='تُلغى تلقائياً عندما لا تظهر مخالفة بلدية غير مسددة في آخر ملف بلدي '
             'مستورد. المخالفات خارج السجل لا تدخل في المبلغ المستحق حتى يتم التأكيد.',
    )
    needs_review = fields.Boolean(string='يحتاج تأكيد', tracking=True, copy=False)
    review_reason = fields.Text(string='سبب المراجعة', copy=False)
    suspected_duplicate = fields.Boolean(string='مكررة محتملة', tracking=True)
    date_warning = fields.Boolean(
        string='تحذير تاريخ', compute='_compute_date_warning', store=True,
        help='موعد الاعتراض قبل تاريخ المخالفة، أو تاريخ المخالفة في المستقبل.',
    )
    user_id = fields.Many2one(
        'res.users', string='المسؤول عن المتابعة', ondelete='set null',
        tracking=True, index=True, check_company=True,
        default=lambda self: self._default_user_id(),
    )
    note = fields.Text(string='ملاحظات')

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    objection_state = fields.Selection(
        selection=[
            ('open', 'مفتوحة للاعتراض'),
            ('filed', 'تم الاعتراض'),
            ('expired', 'انتهت المهلة'),
            ('not_allowed', 'الاعتراض غير مسموح'),
        ],
        string='نافذة الاعتراض', index=True,
        compute='_compute_objection_state', store=True, copy=False,
    )
    days_left = fields.Integer(
        string='الأيام المتبقية', compute='_compute_days_left',
    )
    open_exposure = fields.Monetary(
        string='المبلغ المستحق', currency_field='currency_id',
        compute='_compute_open_exposure', store=True, copy=False,
    )

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------
    @api.depends('branch_id.name', 'company_id.gov_violation_hotels')
    def _compute_division(self):
        for record in self:
            branch = (record.branch_id.name or '').strip().upper()
            if branch.startswith('EW'):
                record.division = 'ew'
            elif branch.startswith('EM'):
                record.division = 'em'
            elif record.company_id.gov_violation_hotels:
                record.division = 'hotels'
            else:
                record.division = 'unalloc'

    @api.depends('objection_allowed', 'objection_filed', 'objection_deadline')
    def _compute_objection_state(self):
        # Depends on "today" as well: the daily cron re-triggers this
        # compute for records whose deadline has passed.
        today = fields.Date.context_today(self)
        for record in self:
            if not record.objection_allowed:
                record.objection_state = 'not_allowed'
            elif record.objection_filed:
                record.objection_state = 'filed'
            elif not record.objection_deadline or record.objection_deadline >= today:
                record.objection_state = 'open'
            else:
                record.objection_state = 'expired'

    @api.depends('objection_deadline', 'objection_state')
    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.objection_state == 'open' and record.objection_deadline:
                record.days_left = (record.objection_deadline - today).days
            else:
                record.days_left = 0

    @api.depends('amount', 'status', 'suspected_duplicate', 'in_register')
    def _compute_open_exposure(self):
        for record in self:
            if (record.status == 'unpaid' and not record.suspected_duplicate
                    and record.in_register):
                record.open_exposure = record.amount
            else:
                record.open_exposure = 0.0

    @api.depends('violation_date', 'objection_deadline')
    def _compute_date_warning(self):
        # Also depends on "today" (future dates): refreshed by the daily cron.
        today = fields.Date.context_today(self)
        for record in self:
            record.date_warning = bool(record.violation_date and (
                record.violation_date > today
                or (record.objection_deadline
                    and record.objection_deadline < record.violation_date)
            ))

    @api.depends('objection_filed')
    def _compute_objection_filed_values(self):
        for record in self:
            if record.objection_filed:
                record.objection_outcome = record.objection_outcome or 'pending'
            else:
                record.objection_outcome = False

    # ------------------------------------------------------------------
    # Constraints & onchanges
    # ------------------------------------------------------------------
    @api.constrains('amount', 'status')
    def _check_amount(self):
        # Zero is allowed: linked records carry no separate fine, and Balady
        # occasionally lists a violation at 0 SAR.
        for record in self:
            if record.amount < 0:
                raise ValidationError(_('قيمة الغرامة لا يمكن أن تكون سالبة (%s).', record.name))

    @api.onchange('objection_filed')
    def _onchange_objection_filed(self):
        if self.objection_filed and not self.objection_filed_date:
            self.objection_filed_date = fields.Date.context_today(self)
        elif not self.objection_filed:
            self.objection_filed_date = False

    @api.onchange('authority')
    def _onchange_authority(self):
        if (self.category_id.authority
                and self.category_id.authority != self.authority):
            self.category_id = False

    @api.onchange('name')
    def _onchange_check_duplicate(self):
        if not self.name:
            return
        domain = [('name', '=', self.name.strip())]
        if self._origin.id:
            domain.append(('id', '!=', self._origin.id))
        if self.with_context(active_test=False).search_count(domain, limit=1):
            return {'warning': {
                'title': _('مخالفة مكررة محتملة'),
                'message': _(
                    'توجد مخالفة بنفس الرقم. تأكد أنها ليست مكررة، '
                    'أو فعّل خيار "مكررة محتملة".'),
            }}

    # ------------------------------------------------------------------
    # CRUD / access
    # ------------------------------------------------------------------
    @api.model
    def _default_user_id(self):
        # No default responsible when records are created by the system
        # (data files, cron, import): reminders would go to OdooBot.
        if self.env.uid == SUPERUSER_ID or self.env.context.get('gov_violation_import'):
            return False
        return self.env.user

    def _is_violation_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_GROUP)

    def write(self, vals):
        if not self._is_violation_manager():
            self._check_user_write(vals)
        if 'objection_deadline' in vals:
            vals = dict(vals, objection_reminder_sent=False)
        if (vals.get('status') == 'paid' and not vals.get('paid_date')
                and not self.env.context.get('gov_violation_import')):
            # Payment date is required when a violation is marked as paid by
            # hand. Historical records may be paid without a known date.
            missing = self.filtered(lambda v: v.status != 'paid' and not v.paid_date)
            if missing:
                raise ValidationError(_(
                    'تاريخ السداد مطلوب للمخالفة: %s',
                    ', '.join(missing.mapped('name'))))
        return super().write(vals)

    def _check_user_write(self, vals):
        if 'active' in vals:
            raise AccessError(_('الأرشفة والاستعادة للمدير فقط.'))
        if vals.get('status') in ('cancelled', 'linked'):
            raise AccessError(_('الإلغاء والربط للمدير فقط.'))
        business_fields = {
            fname for fname in vals
            if not fname.startswith(('message_', 'activity_'))
        }
        locked = self.filtered(lambda v: v.status != 'unpaid')
        if locked and business_fields - LOCKED_EDITABLE_FIELDS:
            raise UserError(_(
                'المخالفات المسددة أو الملغية يعدّلها المدير فقط: %s',
                ', '.join(locked.mapped('name'))))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_paid(self):
        if self.filtered(lambda v: v.status == 'paid'):
            raise UserError(_('لا يمكن حذف مخالفة مسددة، يمكن أرشفتها بدلاً من ذلك.'))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_mark_paid(self):
        for record in self.filtered(lambda v: v.status == 'unpaid'):
            record.write({
                'status': 'paid',
                'paid_date': record.paid_date or fields.Date.context_today(record),
            })
        return True

    def action_cancel(self):
        if not self._is_violation_manager():
            raise AccessError(_('الإلغاء للمدير فقط.'))
        self.filtered(lambda v: v.status == 'unpaid').write({'status': 'cancelled'})
        return True

    def action_reset_to_unpaid(self):
        if not self._is_violation_manager():
            raise AccessError(_('إعادة الحالة إلى غير مسددة للمدير فقط.'))
        self.filtered(lambda v: v.status != 'unpaid').write({
            'status': 'unpaid',
            'paid_date': False,
        })
        return True

    def action_confirm_review(self):
        """Clear the review flag once the data has been checked."""
        self.write({'needs_review': False, 'review_reason': False})
        return True

    # ------------------------------------------------------------------
    # Review-reason helpers
    # ------------------------------------------------------------------
    @api.model
    def _reason_add(self, current, reason):
        lines = [line for line in (current or '').splitlines() if line.strip()]
        if reason not in lines:
            lines.append(reason)
        return '\n'.join(lines)

    @api.model
    def _reason_remove(self, current, reason):
        lines = [line for line in (current or '').splitlines()
                 if line.strip() and not line.startswith(reason)]
        return '\n'.join(lines) or False

    def _flag_review(self, reason):
        for record in self:
            record.write({
                'needs_review': True,
                'review_reason': self._reason_add(record.review_reason, reason),
            })

    def _unflag_review(self, reason):
        for record in self:
            remaining = self._reason_remove(record.review_reason, reason)
            record.write({
                'review_reason': remaining,
                'needs_review': bool(remaining),
            })

    # ------------------------------------------------------------------
    # Import helpers (used by the import wizard and the data loader)
    # ------------------------------------------------------------------
    @api.model
    def _gov_find_branch(self, branch_name):
        if not branch_name:
            return self.env['account.analytic.account']
        return self.env['account.analytic.account'].with_context(active_test=False).search(
            [('name', '=', branch_name.strip())], limit=1)

    @api.model
    def _gov_guess_category(self, authority, *texts):
        """First category whose keywords appear in the first text that matches.
        Texts are tried in order (inspector note, then main item, then
        description), so the most specific source wins."""
        categories = self.env['gov.violation.category'].search([
            ('keywords', '!=', False),
            '|', ('authority', '=', False), ('authority', '=', authority),
        ])
        for text in texts:
            if not text or EMPTY_MAIN_ITEM_RE.match(text):
                continue
            for category in categories:
                if category._matches(text):
                    return category
        return self.env['gov.violation.category']

    @api.model
    def _gov_upsert(self, rows):
        """Idempotent create-or-update by violation number.

        ``rows`` is a list of dicts of field values. Extra keys:
          * ``branch_name``: name of the analytic account to set as branch
          * ``company_name``: name of the company
          * ``note_append`` / ``review_append``: text appended to the note /
            review reason (never duplicated)
          * ``guess_category``: derive the category when none is set (falls
            back to "other" when no keyword matches)
        Numbers must already be text. Returns a summary dict.
        """
        Violation = self.with_context(
            gov_violation_import=True, tracking_disable=False,
            mail_create_nolog=True,
        ).with_context(active_test=False)
        summary = {'created': 0, 'updated': 0, 'errors': [], 'ids': []}
        for row in rows:
            vals = dict(row)
            name = (vals.get('name') or '').strip()
            if not name:
                summary['errors'].append({'row': row, 'error': 'missing violation number'})
                continue
            vals['name'] = name
            branch_name = vals.pop('branch_name', None)
            company_name = vals.pop('company_name', None)
            if company_name:
                company = self.env['res.company'].search([('name', '=', company_name)], limit=1)
                if not company:
                    summary['errors'].append({'row': name, 'error': 'unknown company %s' % company_name})
                    continue
                vals['company_id'] = company.id
            note_append = vals.pop('note_append', None)
            review_append = vals.pop('review_append', None)
            guess = vals.pop('guess_category', False)
            if branch_name:
                branch = self._gov_find_branch(branch_name)
                if branch:
                    vals['branch_id'] = branch.id
                else:
                    review_append = self._reason_add(
                        review_append, 'فرع غير موجود في الخطة التحليلية: %s' % branch_name)
            existing = Violation.search([('name', '=', name)])
            if len(existing) > 1:
                summary['errors'].append({'row': name, 'error': 'duplicate violation number in register'})
                continue
            authority = vals.get('authority') or existing.authority
            if guess and not existing.category_id and not vals.get('category_id'):
                category = self._gov_guess_category(
                    authority, vals.get('inspector_note'), vals.get('main_item'),
                    vals.get('description') or vals.get('reason'))
                if not category:
                    category = self.env.ref(
                        'gov_violations.cat_labor_other' if authority == 'labor'
                        else 'gov_violations.cat_other', raise_if_not_found=False)
                if category:
                    vals['category_id'] = category.id
            if note_append:
                note = existing.note or ''
                if note_append not in note:
                    vals['note'] = (note + '\n' + note_append).strip()
            if review_append:
                reason = existing.review_reason or ''
                for line in review_append.splitlines():
                    reason = self._reason_add(reason, line)
                vals['review_reason'] = reason
                vals['needs_review'] = True
            if existing:
                existing.write(vals)
                summary['updated'] += 1
                summary['ids'].append(existing.id)
            else:
                record = Violation.create(vals)
                summary['created'] += 1
                summary['ids'].append(record.id)
        return summary

    @api.model
    def _gov_balady_row_vals(self, row):
        """Map one row of the 20-column Balady master to field values.
        Values must already be cleaned (numbers as text, dates as date)."""
        (number, violation_date, license_no, license_type, municipality,
         establishment, clause, repeat_count, units, deadline, _days_left,
         amount, invoice, invoice_status, main_item, inspector_note,
         objection_ref, objection_date, objection_status, decision) = (list(row) + [None] * 20)[:20]
        status = BALADY_STATUS.get((invoice_status or '').strip(), 'unpaid')
        vals = {
            'name': number,
            'authority': 'municipality',
            'source': 'balady',
            'in_register': True,
            'violation_date': violation_date or False,
            'municipal_license': license_no or False,
            'license_type': license_type or False,
            'municipality': municipality or False,
            'establishment': establishment or False,
            'regulation_clause': clause or False,
            'repeat_count': int(repeat_count or 0),
            'units': int(units or 0),
            'objection_deadline': deadline or False,
            'deadline_suggested': False,
            'amount': float(amount or 0.0),
            'invoice_number': invoice or False,
            'status': status,
            'main_item': (main_item if main_item and not EMPTY_MAIN_ITEM_RE.match(main_item)
                          else False),
            'inspector_note': inspector_note or False,
            'objection_ref': objection_ref or False,
            'objection_status_text': objection_status or False,
            'committee_decision': decision or False,
        }
        if objection_ref or decision:
            vals['objection_filed'] = True
            vals['objection_filed_date'] = objection_date or False
            decision_text = decision or ''
            if 'رفض' in decision_text:
                vals['objection_outcome'] = 'rejected'
            elif 'قبول' in decision_text or 'قبل' in decision_text:
                vals['objection_outcome'] = 'accepted'
            else:
                vals['objection_outcome'] = 'pending'
        return vals

    @api.model
    def _gov_import_balady(self, rows, full_register=True):
        """Upsert the rows of a Balady master export.

        * Balady wins for its own fields (dates, deadline, amount, invoice,
          objection, license data).
        * Company / branch come from the license map. Unknown licenses are
          added to the map (without branch) and the violation is flagged.
        * A payment or cancellation recorded in Odoo is never reverted by the
          file: the record is flagged instead.
        * With ``full_register``, unpaid municipal violations missing from the
          file are flagged and excluded from exposure (never deleted or
          marked paid).
        """
        LicenseMap = self.env['gov.license.map'].with_context(active_test=False)
        Violation = self.with_context(active_test=False)
        upsert_rows = []
        names = set()
        new_licenses = set()
        for row in rows:
            vals = self._gov_balady_row_vals(row)
            if not vals['name']:
                continue
            names.add(vals['name'])
            existing = Violation.search([('name', '=', vals['name'])], limit=1)
            review = []
            if existing and existing.status in ('paid', 'cancelled', 'linked') \
                    and vals['status'] == 'unpaid':
                vals.pop('status')
                review.append('%s (%s)' % (
                    REASON_STATUS_CONFLICT,
                    dict(STATUS_SELECTION)[existing.status]))
            license_no = vals.get('municipal_license')
            mapping = LicenseMap.search([('name', '=', license_no)], limit=1) if license_no else LicenseMap
            if license_no and not mapping:
                mapping = LicenseMap.create({
                    'name': license_no,
                    'facility_name': vals.get('establishment'),
                })
                new_licenses.add(license_no)
            if mapping.company_id:
                vals['company_id'] = mapping.company_id.id
            elif not existing:
                vals['company_id'] = self.env.ref('base.main_company').id
            if mapping.branch_id:
                vals['branch_id'] = mapping.branch_id.id
            elif not existing.branch_id and not (mapping.company_id.gov_violation_hotels):
                review.append(REASON_UNMAPPED_LICENSE + (': %s' % license_no if license_no else ''))
            if not existing.description and vals.get('inspector_note'):
                vals['description'] = vals['inspector_note']
            if review:
                vals['review_append'] = '\n'.join(review)
            vals['guess_category'] = True
            upsert_rows.append(vals)
        summary = self._gov_upsert(upsert_rows)
        imported = Violation.browse(summary['ids'])
        # Records back in the register lose the "not in register" reason.
        imported.filtered(
            lambda v: REASON_NOT_IN_REGISTER in (v.review_reason or '')
        )._unflag_review(REASON_NOT_IN_REGISTER)
        missing = Violation.browse()
        if full_register and names:
            missing = Violation.search([
                ('authority', '=', 'municipality'),
                ('status', '=', 'unpaid'),
                ('name', 'not in', list(names)),
            ])
            missing.with_context(gov_violation_import=True).write({'in_register': False})
            missing._flag_review(REASON_NOT_IN_REGISTER)
        summary['missing_from_register'] = missing.mapped('name')
        summary['new_licenses'] = sorted(new_licenses)
        return summary

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_daily(self):
        self._cron_refresh_date_computes()
        self._cron_objection_deadline_reminders()

    @api.model
    def _cron_refresh_date_computes(self):
        """Recompute the stored fields that depend on today's date: open
        objection windows whose deadline has passed become 'expired', and
        date warnings for dates that are no longer in the future."""
        today = fields.Date.context_today(self)
        Violation = self.with_context(active_test=False)
        expired = Violation.search([
            ('objection_state', '=', 'open'),
            ('objection_deadline', '<', today),
        ])
        if expired:
            self.env.add_to_compute(self._fields['objection_state'], expired)
        warned = Violation.search([('date_warning', '=', True)])
        if warned:
            self.env.add_to_compute(self._fields['date_warning'], warned)
        (expired | warned).flush_recordset(['objection_state', 'date_warning'])
        return expired

    @api.model
    def _cron_objection_deadline_reminders(self):
        """Schedule one reminder activity for the responsible user when the
        objection deadline is approaching."""
        try:
            days = int(self.env['ir.config_parameter'].sudo().get_param(
                'gov_violations.reminder_days', 7))
        except (TypeError, ValueError):
            days = 7
        if days <= 0:
            return self.browse()
        today = fields.Date.context_today(self)
        records = self.search([
            ('status', '=', 'unpaid'),
            ('objection_state', '=', 'open'),
            ('objection_deadline', '!=', False),
            ('objection_deadline', '<=', today + timedelta(days=days)),
            ('objection_reminder_sent', '=', False),
            ('user_id', '!=', False),
        ])
        for record in records:
            record.activity_schedule(
                'gov_violations.mail_activity_type_objection_deadline',
                date_deadline=record.objection_deadline,
                summary=_('موعد الاعتراض يقترب'),
                note=_('آخر موعد للاعتراض على المخالفة %(name)s هو %(date)s.',
                       name=record.name, date=record.objection_deadline),
                user_id=record.user_id.id,
            )
        records.write({'objection_reminder_sent': True})
        return records
