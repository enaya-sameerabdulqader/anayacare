from datetime import date, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.gov_violation import REASON_NOT_IN_REGISTER, REASON_UNMAPPED_LICENSE


def balady_row(number, license_no, amount=1000.0, status='غير مسددة', deadline=None,
               note=None, main_item=None, objection_ref=None, decision=None):
    deadline = deadline or (fields.Date.today() + timedelta(days=20))
    return [number, date(2026, 8, 1), license_no, 'رخصة تجارية', 'أمانة محافظة جدة',
            'عناية', '1/1/1', 1, 1, deadline, 20, amount, '1234567890123', status,
            main_item, note, objection_ref, None, None, decision]


@tagged('post_install', '-at_install')
class TestGovViolation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Violation = cls.env['gov.violation']
        cls.company = cls.env.ref('base.main_company')
        cls.plan = cls.env['account.analytic.plan'].create({'name': 'Location Test'})
        cls.company.gov_violation_branch_plan_id = cls.plan
        cls.branch_ew = cls.env['account.analytic.account'].create({
            'name': 'EW - Test Branch', 'plan_id': cls.plan.id, 'company_id': cls.company.id})
        cls.branch_em = cls.env['account.analytic.account'].create({
            'name': 'EM - Test Branch', 'plan_id': cls.plan.id, 'company_id': cls.company.id})
        cls.env['gov.license.map'].create({
            'name': '111', 'company_id': cls.company.id, 'branch_id': cls.branch_ew.id})

    def _create(self, **vals):
        base = {'name': 'V-TEST', 'authority': 'municipality', 'amount': 1000.0}
        base.update(vals)
        return self.Violation.create(base)

    def test_division(self):
        self.assertEqual(self._create(branch_id=self.branch_ew.id).division, 'ew')
        self.assertEqual(self._create(name='V-2', branch_id=self.branch_em.id).division, 'em')
        self.assertEqual(self._create(name='V-3', authority='labor').division, 'unalloc')
        self.company.gov_violation_hotels = True
        self.assertEqual(self._create(name='V-4').division, 'hotels')

    def test_objection_state(self):
        today = fields.Date.today()
        self.assertEqual(self._create(objection_deadline=today + timedelta(days=3)).objection_state, 'open')
        self.assertEqual(self._create(name='V-2', objection_deadline=today - timedelta(days=1)).objection_state, 'expired')
        self.assertEqual(self._create(name='V-3').objection_state, 'open')
        self.assertEqual(self._create(name='V-4', objection_allowed=False).objection_state, 'not_allowed')
        filed = self._create(name='V-5', objection_filed=True)
        self.assertEqual(filed.objection_state, 'filed')
        self.assertEqual(filed.objection_outcome, 'pending')

    def test_exposure(self):
        self.assertEqual(self._create().open_exposure, 1000.0)
        self.assertEqual(self._create(name='V-2', status='paid').open_exposure, 0.0)
        self.assertEqual(self._create(name='V-3', suspected_duplicate=True).open_exposure, 0.0)
        self.assertEqual(self._create(name='V-4', in_register=False).open_exposure, 0.0)
        linked = self._create(name='V-5', status='linked', amount=0.0)
        self.assertEqual(linked.open_exposure, 0.0)

    def test_date_warning_is_flag_not_error(self):
        record = self._create(violation_date=date(2026, 6, 7),
                              objection_deadline=date(2026, 5, 9))
        self.assertTrue(record.date_warning)
        future = self._create(name='V-2', violation_date=fields.Date.today() + timedelta(days=30))
        self.assertTrue(future.date_warning)

    def test_upsert_is_idempotent_and_keeps_text(self):
        rows = [{'name': 'V-1', 'authority': 'labor', 'amount': 20000.0,
                 'sadad_number': '2608040000000001', 'branch_name': 'EM - Test Branch'}]
        first = self.Violation._gov_upsert(rows)
        second = self.Violation._gov_upsert(rows)
        self.assertEqual((first['created'], second['created'], second['updated']), (1, 0, 1))
        record = self.Violation.search([('name', '=', 'V-1')])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.sadad_number, '2608040000000001')
        self.assertEqual(record.branch_id, self.branch_em)

    def test_balady_import(self):
        old = self._create(name='V-OLD', amount=1600.0)
        paid = self._create(name='V-PAID', status='paid', paid_date=date(2026, 9, 1))
        summary = self.Violation._gov_import_balady([
            balady_row('V-NEW', '111', note='عاملة بدون كرت صحي'),
            balady_row('V-UNMAPPED', '999', main_item='1 | 2'),
            balady_row('V-PAID', '111'),
            balady_row('V-OBJ', '111', objection_ref='OBJ-1', decision='رفض طلب الاعتراض'),
        ])
        self.assertEqual(summary['created'], 3)
        new = self.Violation.search([('name', '=', 'V-NEW')])
        self.assertEqual(new.branch_id, self.branch_ew)
        self.assertEqual(new.division, 'ew')
        self.assertEqual(new.category_id, self.env.ref('gov_violations.cat_health_cert'))
        self.assertEqual(new.invoice_number, '1234567890123')
        unmapped = self.Violation.search([('name', '=', 'V-UNMAPPED')])
        self.assertTrue(unmapped.needs_review)
        self.assertIn(REASON_UNMAPPED_LICENSE, unmapped.review_reason)
        self.assertFalse(unmapped.main_item)
        self.assertEqual(unmapped.category_id, self.env.ref('gov_violations.cat_other'))
        self.assertIn('999', summary['new_licenses'])
        # A payment recorded in Odoo is not reverted by the file.
        self.assertEqual(paid.status, 'paid')
        self.assertTrue(paid.needs_review)
        obj = self.Violation.search([('name', '=', 'V-OBJ')])
        self.assertEqual((obj.objection_state, obj.objection_outcome), ('filed', 'rejected'))
        # Unpaid municipal record missing from the file: flagged, out of exposure.
        self.assertFalse(old.in_register)
        self.assertEqual(old.open_exposure, 0.0)
        self.assertEqual(old.status, 'unpaid')
        self.assertIn(REASON_NOT_IN_REGISTER, old.review_reason)
        self.assertIn('V-OLD', summary['missing_from_register'])

    def test_balady_reimport_restores_register(self):
        self._create(name='V-BACK')
        self.Violation._gov_import_balady([balady_row('V-X', '111')])
        record = self.Violation.search([('name', '=', 'V-BACK')])
        self.assertFalse(record.in_register)
        self.Violation._gov_import_balady([balady_row('V-X', '111'), balady_row('V-BACK', '111')])
        self.assertTrue(record.in_register)
        self.assertFalse(record.needs_review)
        self.assertEqual(record.open_exposure, 1000.0)

    def test_license_map_apply(self):
        self.Violation._gov_import_balady([balady_row('V-L', '555')], full_register=False)
        record = self.Violation.search([('name', '=', 'V-L')])
        self.assertTrue(record.needs_review)
        mapping = self.env['gov.license.map'].search([('name', '=', '555')])
        mapping.write({'company_id': self.company.id, 'branch_id': self.branch_em.id})
        mapping.action_apply_to_violations()
        self.assertEqual(record.division, 'em')
        self.assertFalse(record.needs_review)

    def test_cron_expires_window(self):
        record = self._create(objection_deadline=fields.Date.today() + timedelta(days=1))
        self.env.cr.execute(
            "UPDATE gov_violation SET objection_deadline = %s WHERE id = %s",
            (fields.Date.today() - timedelta(days=1), record.id))
        record.invalidate_recordset()
        self.assertEqual(record.objection_state, 'open')
        self.Violation._cron_refresh_date_computes()
        record.invalidate_recordset()
        self.assertEqual(record.objection_state, 'expired')
