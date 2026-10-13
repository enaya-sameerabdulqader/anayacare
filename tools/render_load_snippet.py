#!/usr/bin/env python3
"""Render the Odoo-side load script from the payloads built by build_dataset.py.

    python3 -I tools/render_load_snippet.py --out <folder of build_dataset output>

Writes <out>/load_snippet.py. The snippet has no imports, so it runs both in
`odoo-bin shell` and in the MCP `execute_orm` sandbox (it assigns `result`).
It is idempotent: running it twice gives the same register.
"""
import argparse
import json
import os

TEMPLATE = r'''
DATA = json.loads(%(payload)r)
Company = env['res.company']
Account = env['account.analytic.account'].with_context(active_test=False)
LicenseMap = env['gov.license.map'].with_context(active_test=False)
Violation = env['gov.violation'].with_context(active_test=False)
problems = []

# 1. License map
for row in DATA['licenses']:
    vals = {'name': row['name'], 'facility_name': row['facility_name'],
            'inferred': row['inferred'], 'company_id': False, 'branch_id': False}
    if row['company_name']:
        company = Company.search([('name', '=', row['company_name'])], limit=1)
        vals['company_id'] = company.id
        if not company:
            problems.append('company not found: %%s' %% row['company_name'])
    if row['branch_name']:
        branch = Account.search([('name', '=', row['branch_name'])], limit=1)
        vals['branch_id'] = branch.id
        if not branch:
            problems.append('branch not found: %%s' %% row['branch_name'])
    mapping = LicenseMap.search([('name', '=', row['name'])], limit=1)
    if mapping:
        mapping.write(vals)
    else:
        LicenseMap.create(vals)

# 2. History (labor + paid / cancelled / linked), then 3. Balady master
history = Violation._gov_upsert(DATA['history'])
master = Violation._gov_import_balady(DATA['master'], full_register=True)
env.flush_all()

# 4. Tie-out
def group(domain, by):
    out = {}
    for key, count, amount in Violation._read_group(domain, [by], ['__count', 'amount:sum']):
        out[str(key)] = [count, amount]
    return out

def exposure(domain):
    rows = Violation.search_read(domain + [('open_exposure', '>', 0)], ['open_exposure'])
    return [len(rows), sum(r['open_exposure'] for r in rows)]

unpaid_in = [('status', '=', 'unpaid'), ('suspected_duplicate', '=', False), ('in_register', '=', True)]
result = {
    'problems': problems,
    'history': {k: history[k] for k in ('created', 'updated', 'errors')},
    'master': {k: master[k] for k in ('created', 'updated', 'errors', 'missing_from_register', 'new_licenses')},
    'records': Violation.search_count([]),
    'by_status': group([], 'status'),
    'exposure_total': exposure([]),
    'exposure_by_authority': {a: exposure([('authority', '=', a)]) for a in ('municipality', 'labor', 'other')},
    'exposure_by_division': {d: exposure([('division', '=', d)]) for d in ('ew', 'em', 'hotels', 'unalloc')},
    'needs_review': exposure([('needs_review', '=', True)]),
    'needs_review_all': Violation.search_count([('needs_review', '=', True)]),
    'not_in_register': Violation.search([('in_register', '=', False), ('status', '=', 'unpaid')]).mapped('name'),
    'objection_state_unpaid': group([('status', '=', 'unpaid')], 'objection_state'),
    'no_category': Violation.search_count([('category_id', '=', False)]),
    'date_warning': Violation.search([('date_warning', '=', True)]).mapped('name'),
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
    path = os.path.join(args.out, 'load_snippet.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('%s (%d KB)' % (path, len(code.encode()) // 1024))


if __name__ == '__main__':
    main()
