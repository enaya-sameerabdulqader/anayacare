#!/usr/bin/env python3
"""Build the load payloads for the gov_violations register from the source files.

    python3 -I tools/build_dataset.py --data <folder with the xlsx files> --out <folder>

Inputs (BRIEF section 4), all in --data:
  * mappings.json  company / branch / license mappings (format: tools/mappings.example.json)
  * MASTER_balady_unpaid_municipal.xlsx           Balady export, master for municipal unpaid
  * unified_list_labor_paid_cancelled_linked.xlsx  labor fines + paid / cancelled / linked history

Outputs (never commit them, this repository is public):
  * license_map.json   rows for gov.license.map
  * history_rows.json  rows for gov.violation._gov_upsert (labor + municipal history)
  * master_rows.json   rows for gov.violation._gov_import_balady (20-column layout)
  * date_fixes.csv     every date changed by the day/month swap rule, with the reason
  * report.txt         counts, expected tie-out figures and anomalies to review

Every number-like cell is read as TEXT. Nothing here talks to Odoo.
"""
import argparse
import bisect
import collections
import csv
import datetime
import json
import os
import re

import openpyxl

MASTER_FILE = 'MASTER_balady_unpaid_municipal.xlsx'
HISTORY_FILE = 'unified_list_labor_paid_cancelled_linked.xlsx'

# Company / branch / license mappings live in mappings.json next to the source
# files (see tools/mappings.example.json). They are business data and stay out
# of this public repository.
COMPANIES = BRANCHES = LICENSES = {}
HOTEL_LICENSES = set()
NO_NUMBER_UNPAID = {}
DEFAULT_COMPANY = HOTELS_COMPANY = None

STATUSES = {
    'غير مسددة': 'unpaid',
    'مسددة': 'paid',
    'ملغية': 'cancelled',
    'غير محدد': 'linked',
}


def load_mappings(path):
    global COMPANIES, BRANCHES, LICENSES, HOTEL_LICENSES, NO_NUMBER_UNPAID
    global DEFAULT_COMPANY, HOTELS_COMPANY
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    COMPANIES = data['companies']
    BRANCHES = data['branches']
    LICENSES = data['licenses']
    HOTEL_LICENSES = set(data['hotel_licenses'])
    # Numbers starting with 7 look like establishment unified numbers rather
    # than branch licenses: their mapping is flagged "inferred".
    NO_NUMBER_UNPAID = {int(k): v for k, v in data['no_number_unpaid'].items()}
    DEFAULT_COMPANY = data['default_company']
    HOTELS_COMPANY = data['hotels_company']


SCIENTIFIC_RE = re.compile(r'^\d(\.\d+)?[eE][+-]?\d+$')
SWAP_MAX_NEAR = 35  # swapped date must be within this many days of the prediction
SWAP_MIN_FAR = 60   # ... and the original more than this many days off


def text(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    value = str(value).strip()
    return value or None


def as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return None


def number_of(name):
    match = re.match(r'^V-(\d+)$', name or '')
    return int(match.group(1)) if match else None


def swap(day):
    if day is None or day.day > 12:
        return None
    try:
        return day.replace(month=day.day, day=day.month)
    except ValueError:
        return None


class DatePredictor:
    """Violation number -> date, interpolated between verified Balady pairs."""

    def __init__(self, pairs):
        pairs = sorted(pairs)
        self.numbers = [n for n, _ in pairs]
        self.days = [d.toordinal() for _, d in pairs]

    def predict(self, number):
        # Interpolation only: outside the verified range the number/date
        # relation is unknown, so no prediction (and no swap).
        if len(self.numbers) < 2 or number is None \
                or not self.numbers[0] <= number <= self.numbers[-1]:
            return None
        i = bisect.bisect_left(self.numbers, number)
        i = min(max(i, 1), len(self.numbers) - 1)
        n0, n1 = self.numbers[i - 1], self.numbers[i]
        d0, d1 = self.days[i - 1], self.days[i]
        if n1 == n0:
            return datetime.date.fromordinal(d0)
        return datetime.date.fromordinal(round(d0 + (d1 - d0) * (number - n0) / (n1 - n0)))


def read_master(path):
    sheet = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows, header = [], False
    for raw in sheet.iter_rows(values_only=True):
        raw = list(raw) + [None] * (20 - len(raw))
        if not header:
            header = text(raw[0]) == 'رقم المخالفة'
            continue
        if not text(raw[0]):
            continue
        row = []
        for index, value in enumerate(raw[:20]):
            if index in (1, 9, 17):
                day = as_date(value)
                row.append(day.isoformat() if day else None)
            elif index in (7, 8, 10, 11):
                row.append(value if isinstance(value, (int, float)) else None)
            else:
                row.append(text(value))
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--mappings', help='default: <data>/mappings.json')
    args = parser.parse_args()
    load_mappings(args.mappings or os.path.join(args.data, 'mappings.json'))
    os.makedirs(args.out, exist_ok=True)
    report = []
    log = report.append

    # ---------------------------------------------------------------- master
    master = read_master(os.path.join(args.data, MASTER_FILE))
    master_by_name = {row[0]: row for row in master}
    log('MASTER: %d rows, %s SAR' % (len(master), f"{sum(r[11] or 0 for r in master):,.0f}"))
    pairs = [(number_of(r[0]), datetime.date.fromisoformat(r[1])) for r in master if r[1]]
    predictor = DatePredictor(pairs)
    inversions = []
    for (n0, d0), (n1, d1) in zip(sorted(pairs), sorted(pairs)[1:]):
        if d1 < d0 - datetime.timedelta(days=30):
            inversions.append('V-%d (%s) > V-%d (%s)' % (n1, d1, n0, d0))
    log('  number/date inversions > 30 days in master: %d %s' % (len(inversions), inversions[:5]))

    # --------------------------------------------------------- license map
    license_rows = []
    master_licenses = collections.Counter(r[2] for r in master if r[2])
    for license_no in sorted(set(LICENSES) | set(master_licenses)):
        branch = LICENSES.get(license_no)
        hotel = license_no in HOTEL_LICENSES
        license_rows.append({
            'name': license_no,
            'company_name': HOTELS_COMPANY if hotel else (DEFAULT_COMPANY if branch else None),
            'branch_name': branch,
            'inferred': bool(branch) and license_no.startswith('7'),
            'facility_name': next((r[5] for r in master if r[2] == license_no and r[5]), None),
        })
    unmapped = [(lic, master_licenses[lic]) for lic in sorted(master_licenses)
                if lic not in LICENSES]
    log('LICENSES: %d (unmapped in master: %s)' % (len(license_rows), unmapped))

    # ------------------------------------------------------------- history
    workbook = openpyxl.load_workbook(os.path.join(args.data, HISTORY_FILE), data_only=True)
    history, fixes, anomalies = [], [], []

    # Labor
    for raw in workbook['مخالفات مكتب العمل'].iter_rows(min_row=5, values_only=True):
        name = text(raw[1])
        if not name or not name.startswith('V-'):
            continue
        sadad = text(raw[6])
        offender = text(raw[7])
        notes = []
        if sadad and SCIENTIFIC_RE.match(sadad):
            notes.append('رقم السداد تالف في ملف المصدر (%s) - يلزم إدخاله من منصة مدد/سداد' % sadad)
            sadad = None
        status = STATUSES.get(text(raw[10]) or '', 'unpaid')
        history.append({
            'name': name, 'authority': 'labor', 'source': 'history',
            'company_name': DEFAULT_COMPANY,
            'violation_code': text(raw[2]),
            'violation_date': as_date(raw[3]).isoformat() if as_date(raw[3]) else None,
            'objection_deadline': as_date(raw[4]).isoformat() if as_date(raw[4]) else None,
            'deadline_suggested': True,
            'amount': float(raw[5] or 0),
            'sadad_number': sadad,
            'offender_ref': offender if offender and offender != '0' else None,
            'description': text(raw[8]),
            'status': status,
            'note_append': '\n'.join(notes) or None,
            'guess_category': True,
        })

    # Municipal history
    seen = collections.Counter()
    no_number_unpaid = {k: list(v) for k, v in NO_NUMBER_UNPAID.items()}
    no_number_seq = 0
    for raw in workbook['مخالفات البلدية'].iter_rows(min_row=5, values_only=True):
        company_ar, branch_ar, name = text(raw[0]), text(raw[1]), text(raw[2])
        amount = float(raw[6] or 0)
        status = STATUSES.get(text(raw[7]) or '')
        if not company_ar and not branch_ar:
            continue  # totals row
        if not status:
            anomalies.append('unknown status %r for %s' % (raw[7], name))
            continue
        review = []
        if not name or not name.startswith('V-'):
            if status == 'unpaid' and no_number_unpaid.get(int(amount)):
                real = no_number_unpaid[int(amount)].pop(0)
                anomalies.append('no-number unpaid %s -> %s (carried by the master)' % (f'{amount:,.0f}', real))
                continue
            no_number_seq += 1
            name = 'بدون رقم-%d' % no_number_seq
            review.append('لا يوجد رقم مخالفة في المصدر')
        seen[name] += 1
        company = COMPANIES.get(company_ar, DEFAULT_COMPANY)
        if branch_ar not in BRANCHES:
            review.append('اسم فرع غير معروف في المصدر: %s' % branch_ar)
        branch = BRANCHES.get(branch_ar)
        deadline_raw = raw[5]
        objection_allowed = not (
            text(raw[8]) == 'غير مسموح بالاعتراض'
            or (isinstance(deadline_raw, str) and 'غير مسموح' in deadline_raw))
        violation_date = as_date(raw[4])
        deadline = as_date(deadline_raw)
        note = []
        if name in master_by_name:
            # The master wins for its fields; history only adds company/branch
            # (used when the license map has no branch for it).
            master_status = 'unpaid'
            if status != master_status:
                anomalies.append('%s: unified list says %s, Balady says unpaid (Balady kept)'
                                 % (name, status))
            history.append({'name': name, 'authority': 'municipality', 'source': 'balady',
                            'company_name': company, 'branch_name': branch})
            continue
        # Day/month swap repair (BRIEF section 4)
        predicted = predictor.predict(number_of(name))
        if violation_date and predicted:
            swapped = swap(violation_date)
            off = abs((violation_date - predicted).days)
            if swapped and off > SWAP_MIN_FAR and abs((swapped - predicted).days) <= SWAP_MAX_NEAR:
                fixes.append([name, 'violation_date', violation_date, swapped, predicted, off])
                note.append('تاريخ المخالفة صُحح من %s إلى %s (تبديل اليوم والشهر، متوقع %s من رقم المخالفة)'
                            % (violation_date, swapped, predicted))
                violation_date = swapped
            elif off > SWAP_MIN_FAR:
                anomalies.append('%s date %s is %d days from predicted %s, no safe swap'
                                 % (name, violation_date, off, predicted))
        if deadline and violation_date and deadline < violation_date:
            swapped = swap(deadline)
            if swapped and violation_date <= swapped <= violation_date + datetime.timedelta(days=120):
                fixes.append([name, 'objection_deadline', deadline, swapped, '', ''])
                note.append('موعد الاعتراض صُحح من %s إلى %s (تبديل اليوم والشهر)' % (deadline, swapped))
                deadline = swapped
        history.append({
            'name': name, 'authority': 'municipality', 'source': 'history',
            'company_name': company,
            'branch_name': branch,
            'invoice_number': text(raw[3]),
            'violation_date': violation_date.isoformat() if violation_date else None,
            'objection_deadline': deadline.isoformat() if deadline else None,
            'objection_allowed': objection_allowed,
            'amount': amount,
            'status': status,
            'reason': text(raw[9]),
            # Not in the Balady unpaid export; only unpaid ones matter for exposure.
            'in_register': status != 'unpaid',
            'note_append': '\n'.join(note) or None,
            'review_append': '\n'.join(review) or None,
            'guess_category': True,
        })
    duplicates = [n for n, c in seen.items() if c > 1]
    log('HISTORY: %d rows (%d company/branch-only rows for master violations; labor %d, municipal %d); duplicates in source: %s' % (
        len(history), sum('status' not in r for r in history), sum(r['authority'] == 'labor' for r in history),
        sum(r['authority'] == 'municipality' for r in history), duplicates))
    for row in history:
        if row['name'] in duplicates:
            row['suspected_duplicate'] = True
    log('DATE FIXES: %d' % len(fixes))

    # ------------------------------------------------- expected tie-out
    expected = collections.defaultdict(lambda: [0, 0.0])
    def add(key, amount):
        expected[key][0] += 1
        expected[key][1] += amount
    for row in history:
        if 'status' not in row:
            continue
        add(('status', row['status']), row['amount'])
        if row['status'] == 'unpaid' and row.get('in_register', True) and not row.get('suspected_duplicate'):
            add(('exposure', row['authority']), row['amount'])
    for row in master:
        add(('status', 'unpaid'), row[11] or 0)
        add(('exposure', 'municipality'), row[11] or 0)
    log('EXPECTED (before Odoo):')
    for key in sorted(expected):
        log('  %-28s %4d  %12s' % ('/'.join(key), expected[key][0], f'{expected[key][1]:,.0f}'))
    log('  records total: %d' % (sum('status' in r for r in history) + len(master)))
    log('ANOMALIES:')
    report.extend('  ' + a for a in anomalies)

    # --------------------------------------------------------------- write
    with open(os.path.join(args.out, 'license_map.json'), 'w', encoding='utf-8') as f:
        json.dump(license_rows, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, 'history_rows.json'), 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, 'master_rows.json'), 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, 'date_fixes.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['violation', 'field', 'source value', 'loaded value', 'predicted', 'days off'])
        writer.writerows(fixes)
    with open(os.path.join(args.out, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(report) + '\n')
    print('\n'.join(report))


if __name__ == '__main__':
    main()
