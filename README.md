# anayacare

## gov_violations — Government Violations Register (Odoo 19)

Addon `gov_violations/` (19.0.3.0.0): labor office / municipality (Balady) /
other fines, payment status, objection window, EW / EM split, license → branch
map and a Balady import wizard. Arabic labels.

Menu: المخالفات الحكومية → المخالفات / استيراد ملف بلدي / الإعدادات
(التصنيفات، ربط التراخيص بالفروع، الإعدادات العامة).

Business rules:

* **المبلغ المستحق (outstanding exposure)** = unpaid, not a suspected duplicate
  and, for municipal fines, present in the latest Balady file (`in_register`).
* Linked records (مرتبطة بدون غرامة) carry no fine and are excluded from totals.
* Division: branch name `EW…` → EW, `EM…` → EM, company flagged "hotels" →
  hotels, otherwise unallocated.
* Balady import: upsert by violation number; Balady wins for its fields;
  company/branch from the license map; unpaid municipal records missing from a
  full file are flagged and excluded from exposure, never deleted or paid; a
  payment recorded in Odoo is never reverted by the file (flagged instead).
* Date problems are flags (`date_warning`), not blocking errors.
* Daily cron refreshes the date-dependent stored fields and schedules
  objection reminders.

Tests: `odoo-bin -d <db> -i gov_violations --test-tags /gov_violations`.

## tools/ — one-time historical load

Source files and generated payloads must never be committed (public repo).

1. `python3 -I tools/build_dataset.py --data <dir> --out <dir>` — reads the
   Balady master + unified list as text, fixes day/month-swapped dates
   (interpolating violation number → date between verified Balady pairs) and
   writes the payloads, `date_fixes.csv` and `report.txt` (expected tie-out).
   `<dir>/mappings.json` holds the company / branch / license mappings
   (format: `tools/mappings.example.json`).
2. `python3 -I tools/render_load_snippet.py --out <dir>` — writes
   `load_snippet.py`, idempotent; run in `odoo-bin shell` or MCP `execute_orm`.
   Its result is the tie-out from Odoo.
3. Before any install / upgrade: run `tools/backup_snippet.py` and take an
   Odoo.sh backup.
