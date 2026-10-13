#!/usr/bin/env python3
"""Render the load script for the importable module (x_gov_violations).

    python3 -I tools/render_x_load_snippet.py --out <folder of build_dataset output>

Writes <out>/x_load_snippet.py: no imports, assigns `result`, so it runs in the
MCP execute_orm sandbox and in `odoo-bin shell`. Idempotent (upsert by
violation number). Order: license map -> history (labor, paid, cancelled,
linked) -> Balady master through the same "process Balady file" server action
users run from the menu -> tie-out.
"""
import argparse
import json
import os

TEMPLATE = r'''
DATA = json.loads(%(payload)r)
Company = env['res.company']
Account = env['account.analytic.account'].with_context(active_test=False)
LicenseMap = env['x_gov_license_map'].with_context(active_test=False)
Violation = env['x_gov_violation'].with_context(active_test=False)
Category = env['x_gov_violation_category']
Line = env['x_gov_balady_line']
problems = []

def company_id(name):
    company = Company.search([('name', '=', name)], limit=1)
    if not company:
        problems.append('company not found: %%s' %% name)
    return company.id

def branch_id(name):
    branch = Account.search([('name', '=', name), ('plan_id.name', '=', 'Location')], limit=1)
    if not branch:
        problems.append('branch not found: %%s' %% name)
    return branch.id

def add_reason(current, reason):
    items = [x for x in (current or '').split('\n') if x.strip()]
    if reason not in items:
        items.append(reason)
    return '\n'.join(items)

categories = Category.search([('x_keywords', '!=', False)], order='x_sequence, id')
fallback = {
    'labor': Category.search([('x_name', '=', 'مكتب العمل - أخرى')], limit=1),
    'municipality': Category.search([('x_name', '=', 'أخرى / غير محدد')], limit=1),
}

def guess(authority, texts):
    for text in texts:
        if not text:
            continue
        low = text.casefold()
        for cat in categories:
            if cat.x_authority and cat.x_authority != authority:
                continue
            for key in cat.x_keywords.split(','):
                key = key.strip()
                if key and key.casefold() in low:
                    return cat
    return fallback[authority]

# 1. License map
for row in DATA['licenses']:
    vals = {'x_name': row['name'], 'x_facility_name': row['facility_name'],
            'x_inferred': row['inferred'], 'x_active': True,
            'x_company_id': company_id(row['company_name']) if row['company_name'] else False,
            'x_branch_id': branch_id(row['branch_name']) if row['branch_name'] else False}
    mapping = LicenseMap.search([('x_name', '=', row['name'])], limit=1)
    if mapping:
        mapping.write(vals)
    else:
        LicenseMap.create(vals)

# 2. History
FIELD_MAP = {
    'authority': 'x_authority', 'source': 'x_source', 'violation_code': 'x_violation_code',
    'violation_date': 'x_violation_date', 'objection_deadline': 'x_objection_deadline',
    'deadline_suggested': 'x_deadline_suggested', 'amount': 'x_amount',
    'sadad_number': 'x_sadad_number', 'offender_ref': 'x_offender_ref',
    'description': 'x_description', 'status': 'x_status', 'invoice_number': 'x_invoice_number',
    'objection_allowed': 'x_objection_allowed', 'reason': 'x_reason',
    'in_register': 'x_in_register', 'suspected_duplicate': 'x_suspected_duplicate',
}
history = {'created': 0, 'updated': 0}
for row in DATA['history']:
    existing = Violation.search([('x_name', '=', row['name'])], limit=1)
    vals = {'x_name': row['name']}
    for key, field in FIELD_MAP.items():
        if key in row:
            vals[field] = row[key] if row[key] is not None else False
    if row.get('company_name'):
        vals['x_company_id'] = company_id(row['company_name'])
    if row.get('branch_name'):
        vals['x_branch_id'] = branch_id(row['branch_name'])
    if row.get('guess_category') and not existing.x_category_id:
        vals['x_category_id'] = guess(row['authority'], [row.get('description'), row.get('reason')]).id
    if row.get('note_append') and row['note_append'] not in (existing.x_note or ''):
        vals['x_note'] = ((existing.x_note or '') + '\n' + row['note_append']).strip()
    if row.get('review_append'):
        review = existing.x_review_reason or ''
        for line in row['review_append'].split('\n'):
            review = add_reason(review, line)
        vals['x_review_reason'] = review
        vals['x_needs_review'] = True
    if existing:
        existing.write(vals)
        history['updated'] += 1
    else:
        vals.setdefault('x_active', True)
        vals.setdefault('x_objection_allowed', True)
        vals.setdefault('x_in_register', True)
        vals.setdefault('x_status', 'unpaid')
        Violation.create(vals)
        history['created'] += 1

# 3. Balady master through the module's own processing action
COLS = ['x_name', 'x_violation_date', 'x_license', 'x_license_type', 'x_municipality',
        'x_establishment', 'x_clause', 'x_repeat_count', 'x_units', 'x_deadline',
        'x_days_left_file', 'x_amount', 'x_invoice', 'x_invoice_status', 'x_main_item',
        'x_inspector_note', 'x_objection_ref', 'x_objection_date', 'x_objection_status',
        'x_decision']
Line.search([]).unlink()
lines = Line.create([{col: (value if value is not None else False) for col, value in zip(COLS, row)}
                     for row in DATA['master']])
notice = env.ref('x_gov_violations.action_process_balady_core').with_context(
    gov_full_register=True, active_model='x_gov_balady_line', active_ids=lines.ids).run()
env.flush_all()

# 4. Tie-out
def total(domain, field='x_amount'):
    rows = Violation.search_read(domain, [field])
    return [len(rows), sum(r[field] for r in rows)]

result = {
    'problems': problems,
    'history': history,
    'master_notice': notice and notice['params']['message'],
    'records': Violation.search_count([]),
    'by_status': {s: total([('x_status', '=', s)]) for s in ('unpaid', 'paid', 'cancelled', 'linked')},
    'exposure_total': total([('x_open_exposure', '>', 0)], 'x_open_exposure'),
    'exposure_by_authority': {a: total([('x_authority', '=', a), ('x_open_exposure', '>', 0)], 'x_open_exposure') for a in ('municipality', 'labor', 'other')},
    'exposure_by_division': {d: total([('x_division', '=', d), ('x_open_exposure', '>', 0)], 'x_open_exposure') for d in ('ew', 'em', 'hotels', 'unalloc')},
    'needs_review_exposure': total([('x_needs_review', '=', True), ('x_open_exposure', '>', 0)], 'x_open_exposure'),
    'needs_review_all': Violation.search_count([('x_needs_review', '=', True)]),
    'not_in_register': Violation.search([('x_in_register', '=', False), ('x_status', '=', 'unpaid')]).mapped('x_name'),
    'objection_state_unpaid': {s: total([('x_status', '=', 'unpaid'), ('x_objection_state', '=', s)]) for s in ('open', 'filed', 'expired', 'not_allowed')},
    'no_category': Violation.search_count([('x_category_id', '=', False), ('x_status', '!=', 'linked')]),
    'date_warning': Violation.search([('x_date_warning', '=', True)]).mapped('x_name'),
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    payload = {}
    for key, filename in (('licenses', 'license_map.json'), ('history', 'history_rows.json'),
                          ('master', 'master_rows.json')):
        with open(os.path.join(args.out, filename), encoding='utf-8') as f:
            payload[key] = json.load(f)
    code = TEMPLATE % {'payload': json.dumps(payload, ensure_ascii=False)}
    path = os.path.join(args.out, 'x_load_snippet.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('%s (%d KB)' % (path, len(code.encode()) // 1024))


if __name__ == '__main__':
    main()
