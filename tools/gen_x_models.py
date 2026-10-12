#!/usr/bin/env python3
"""Generate x_gov_violations/data/models.xml (ir.model + ir.model.fields records)."""
from xml.sax.saxutils import escape

SEL = {
 'authority': "[('labor','مكتب العمل'),('municipality','البلدية'),('other','جهة أخرى')]",
 'status': "[('unpaid','غير مسددة'),('paid','مسددة'),('cancelled','ملغية'),('linked','مرتبطة بدون غرامة')]",
 'division': "[('ew','سيدات (EW)'),('em','رجال (EM)'),('hotels','الفنادق'),('unalloc','غير مرتبط بفرع')]",
 'source': "[('balady','ملف بلدي'),('history','السجل الموحد (تاريخي)'),('manual','إدخال يدوي')]",
 'outcome': "[('pending','قيد النظر'),('accepted','مقبول'),('rejected','مرفوض')]",
 'objstate': "[('open','مفتوحة للاعتراض'),('filed','تم الاعتراض'),('expired','انتهت المهلة'),('not_allowed','الاعتراض غير مسموح')]",
}

COMPUTE = {
'x_division': ('x_branch_id,x_company_id', '''for record in self:
    branch = (record.x_branch_id.name or '').strip().upper()
    if branch.startswith('EW'):
        value = 'ew'
    elif branch.startswith('EM'):
        value = 'em'
    elif 'sustainable' in (record.x_company_id.name or '').lower():
        value = 'hotels'
    else:
        value = 'unalloc'
    record['x_division'] = value'''),
'x_objection_state': ('x_objection_allowed,x_objection_filed,x_objection_deadline,x_refresh_stamp', '''today = datetime.date.today()
for record in self:
    if not record.x_objection_allowed:
        value = 'not_allowed'
    elif record.x_objection_filed:
        value = 'filed'
    elif not record.x_objection_deadline or record.x_objection_deadline >= today:
        value = 'open'
    else:
        value = 'expired'
    record['x_objection_state'] = value'''),
'x_days_left': ('x_objection_deadline,x_objection_state', '''today = datetime.date.today()
for record in self:
    if record.x_objection_state == 'open' and record.x_objection_deadline:
        record['x_days_left'] = (record.x_objection_deadline - today).days
    else:
        record['x_days_left'] = 0'''),
'x_open_exposure': ('x_amount,x_status,x_suspected_duplicate,x_in_register', '''for record in self:
    if record.x_status == 'unpaid' and not record.x_suspected_duplicate and record.x_in_register:
        record['x_open_exposure'] = record.x_amount
    else:
        record['x_open_exposure'] = 0.0'''),
'x_date_warning': ('x_violation_date,x_objection_deadline,x_refresh_stamp', '''today = datetime.date.today()
for record in self:
    day = record.x_violation_date
    deadline = record.x_objection_deadline
    record['x_date_warning'] = bool(day and (day > today or (deadline and deadline < day)))'''),
'x_is_mapped': ('x_branch_id,x_company_id', '''for record in self:
    record['x_is_mapped'] = bool(record.x_branch_id or 'sustainable' in (record.x_company_id.name or '').lower())'''),
}

# (name, label, type, extra)
VIOLATION = [
 ('x_name', 'رقم المخالفة', 'char', {'required': 1, 'tracking': 1, 'index': 1}),
 ('x_active', 'نشط', 'boolean', {'tracking': 1}),
 ('x_authority', 'الجهة', 'selection', {'selection': SEL['authority'], 'required': 1, 'tracking': 1, 'index': 1}),
 ('x_source', 'المصدر', 'selection', {'selection': SEL['source']}),
 ('x_company_id', 'الشركة', 'many2one', {'relation': 'res.company', 'required': 1, 'tracking': 1, 'on_delete': 'restrict', 'index': 1}),
 ('x_branch_id', 'الفرع', 'many2one', {'relation': 'account.analytic.account', 'tracking': 1, 'on_delete': 'set null', 'index': 1}),
 ('x_division', 'القسم', 'selection', {'selection': SEL['division'], 'compute': 1, 'store': 1, 'index': 1}),
 ('x_category_id', 'التصنيف', 'many2one', {'relation': 'x_gov_violation_category', 'tracking': 1, 'on_delete': 'restrict'}),
 ('x_violation_code', 'رمز المخالفة', 'char', {}),
 ('x_reason', 'سبب المخالفة', 'char', {}),
 ('x_description', 'وصف المخالفة', 'text', {}),
 ('x_violation_date', 'تاريخ المخالفة', 'date', {'tracking': 1, 'index': 1}),
 ('x_amount', 'قيمة الغرامة (ريال)', 'float', {'tracking': 1}),
 ('x_status', 'حالة السداد', 'selection', {'selection': SEL['status'], 'required': 1, 'tracking': 1, 'index': 1}),
 ('x_paid_date', 'تاريخ السداد', 'date', {'tracking': 1}),
 ('x_sadad_number', 'رقم السداد', 'char', {}),
 ('x_invoice_number', 'رقم الفاتورة', 'char', {}),
 ('x_offender_ref', 'رقم المخالف / هوية العامل', 'char', {}),
 ('x_objection_allowed', 'الاعتراض مسموح', 'boolean', {}),
 ('x_objection_deadline', 'آخر موعد للاعتراض', 'date', {'tracking': 1, 'index': 1}),
 ('x_deadline_suggested', 'موعد اعتراض مقترح', 'boolean', {}),
 ('x_objection_filed', 'تم تقديم اعتراض', 'boolean', {'tracking': 1}),
 ('x_objection_filed_date', 'تاريخ تقديم الاعتراض', 'date', {}),
 ('x_objection_outcome', 'نتيجة الاعتراض', 'selection', {'selection': SEL['outcome'], 'tracking': 1}),
 ('x_objection_ref', 'رقم طلب الاعتراض', 'char', {'index': 1}),
 ('x_objection_status_text', 'حالة طلب الاعتراض', 'char', {}),
 ('x_committee_decision', 'قرار لجنة الاعتراض', 'char', {}),
 ('x_objection_state', 'نافذة الاعتراض', 'selection', {'selection': SEL['objstate'], 'compute': 1, 'store': 1, 'index': 1}),
 ('x_days_left', 'الأيام المتبقية', 'integer', {'compute': 1}),
 ('x_open_exposure', 'المبلغ المستحق', 'float', {'compute': 1, 'store': 1}),
 ('x_municipal_license', 'رقم الترخيص البلدي / الهوية', 'char', {'index': 1}),
 ('x_license_type', 'نوع الترخيص البلدي', 'char', {}),
 ('x_municipality', 'الأمانة / البلدية', 'char', {'index': 1}),
 ('x_establishment', 'اسم المنشأة', 'char', {}),
 ('x_regulation_clause', 'بند اللائحة', 'char', {}),
 ('x_repeat_count', 'عدد مرات التكرار', 'integer', {}),
 ('x_units', 'عدد وحدات المخالفة', 'integer', {}),
 ('x_main_item', 'بند المخالفة الرئيسي', 'char', {}),
 ('x_inspector_note', 'ملاحظات المراقب', 'text', {}),
 ('x_needs_review', 'يحتاج تأكيد', 'boolean', {'tracking': 1}),
 ('x_review_reason', 'سبب المراجعة', 'text', {}),
 ('x_in_register', 'موجودة في سجل بلدي', 'boolean', {}),
 ('x_suspected_duplicate', 'مكررة محتملة', 'boolean', {'tracking': 1}),
 ('x_date_warning', 'تحذير تاريخ', 'boolean', {'compute': 1, 'store': 1}),
 ('x_user_id', 'المسؤول عن المتابعة', 'many2one', {'relation': 'res.users', 'tracking': 1, 'on_delete': 'set null'}),
 ('x_note', 'ملاحظات', 'text', {}),
 ('x_reminder_sent', 'تم إرسال تذكير الاعتراض', 'boolean', {}),
 ('x_refresh_stamp', 'تحديث تقني', 'datetime', {}),
]
CATEGORY = [
 ('x_name', 'التصنيف', 'char', {'required': 1}),
 ('x_sequence', 'التسلسل', 'integer', {}),
 ('x_active', 'نشط', 'boolean', {}),
 ('x_authority', 'الجهة', 'selection', {'selection': SEL['authority']}),
 ('x_keywords', 'كلمات مفتاحية', 'char', {}),
]
LICENSE = [
 ('x_name', 'رقم الترخيص البلدي / الهوية', 'char', {'required': 1, 'index': 1}),
 ('x_company_id', 'الشركة', 'many2one', {'relation': 'res.company', 'on_delete': 'set null'}),
 ('x_branch_id', 'الفرع', 'many2one', {'relation': 'account.analytic.account', 'on_delete': 'set null'}),
 ('x_facility_name', 'اسم المنشأة', 'char', {}),
 ('x_inferred', 'ربط استنتاجي', 'boolean', {}),
 ('x_note', 'ملاحظة', 'char', {}),
 ('x_is_mapped', 'مربوط', 'boolean', {'compute': 1, 'store': 1}),
 ('x_active', 'نشط', 'boolean', {}),
]
# Labels are the exact Balady headers, so the standard Odoo import maps the
# columns by name.
LINE = [
 ('x_name', 'رقم المخالفة', 'char', {'required': 1}),
 ('x_violation_date', 'تاريخ رصد المخالفة', 'date', {}),
 ('x_license', 'رقم الترخيص البلدي / رقم الهوية', 'char', {}),
 ('x_license_type', 'نوع الترخيص البلدي', 'char', {}),
 ('x_municipality', 'الأمانة / البلدية', 'char', {}),
 ('x_establishment', 'اسم المنشأة', 'char', {}),
 ('x_clause', 'بند اللائحة', 'char', {}),
 ('x_repeat_count', 'عدد مرات تكرار المخالفة', 'integer', {}),
 ('x_units', 'عدد وحدات المخالفة', 'integer', {}),
 ('x_deadline', 'آخر موعد لتقديم الاعتراض', 'date', {}),
 ('x_days_left_file', 'الأيام المتبقية للاعتراض', 'integer', {}),
 ('x_amount', 'قيمة الغرامة (ر.س)', 'float', {}),
 ('x_invoice', 'رقم الفاتورة', 'char', {}),
 ('x_invoice_status', 'حالة فاتورة المخالفة', 'char', {}),
 ('x_main_item', 'بند المخالفة الرئيسي', 'char', {}),
 ('x_inspector_note', 'ملاحظات المراقب', 'text', {}),
 ('x_objection_ref', 'رقم طلب الاعتراض', 'char', {}),
 ('x_objection_date', 'تاريخ طلب الاعتراض', 'date', {}),
 ('x_objection_status', 'حالة طلب الاعتراض', 'char', {}),
 ('x_decision', 'قرار لجنة الاعتراض', 'char', {}),
]
MODELS = [
 ('x_gov_violation_category', 'تصنيف المخالفة', CATEGORY, {}),
 ('x_gov_license_map', 'ربط الترخيص بالفرع', LICENSE, {}),
 ('x_gov_violation', 'مخالفة حكومية', VIOLATION, {'is_mail_thread': 1, 'is_mail_activity': 1, 'order': 'x_violation_date desc, id desc'}),
 ('x_gov_balady_line', 'سطر ملف بلدي', LINE, {}),
]


def model_xmlid(model):
    return 'model_' + model


def main():
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<odoo>']
    for model, label, fields, opts in MODELS:
        out.append('    <record id="%s" model="ir.model">' % model_xmlid(model))
        out.append('        <field name="name">%s</field>' % escape(label))
        out.append('        <field name="model">%s</field>' % model)
        for key in ('is_mail_thread', 'is_mail_activity'):
            if opts.get(key):
                out.append('        <field name="%s" eval="True"/>' % key)
        out.append('    </record>')
    order = list(COMPUTE)
    for model, label, fields, opts in MODELS:
        # Plain fields first, computed fields after their dependencies.
        fields = ([f for f in fields if not f[3].get('compute')]
                  + sorted([f for f in fields if f[3].get('compute')], key=lambda f: order.index(f[0])))
        for name, flabel, ttype, extra in fields:
            out.append('    <record id="field_%s__%s" model="ir.model.fields">' % (model, name))
            out.append('        <field name="model_id" ref="%s"/>' % model_xmlid(model))
            out.append('        <field name="name">%s</field>' % name)
            out.append('        <field name="field_description">%s</field>' % escape(flabel))
            out.append('        <field name="ttype">%s</field>' % ttype)
            if extra.get('selection'):
                out.append('        <field name="selection">%s</field>' % escape(extra['selection']))
            if extra.get('relation'):
                out.append('        <field name="relation">%s</field>' % extra['relation'])
            if extra.get('on_delete'):
                out.append('        <field name="on_delete">%s</field>' % extra['on_delete'])
            for flag in ('required', 'index'):
                if extra.get(flag):
                    out.append('        <field name="%s" eval="True"/>' % flag)
            if extra.get('tracking'):
                out.append('        <field name="tracking" eval="1"/>')
            if extra.get('compute'):
                deps, code = COMPUTE[name]
                out.append('        <field name="depends">%s</field>' % deps)
                out.append('        <field name="compute"><![CDATA[%s]]></field>' % code)
                out.append('        <field name="store" eval="%s"/>' % bool(extra.get('store')))
                out.append('        <field name="readonly" eval="True"/>')
            out.append('    </record>')
    # Ordering can only reference fields once they exist.
    for model, label, fields, opts in MODELS:
        if opts.get('order'):
            out.append('    <record id="%s" model="ir.model">' % model_xmlid(model))
            out.append('        <field name="order">%s</field>' % opts['order'])
            out.append('    </record>')
    out.append('</odoo>')
    with open('x_gov_violations/data/models.xml', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')

    # Saved import mappings: the standard import splits headers on "/", so
    # Balady headers such as "الأمانة / البلدية" would not match by label.
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<odoo>']
    for name, flabel, ttype, extra in LINE:
        out.append('    <record id="import_mapping_%s" model="base_import.mapping">' % name)
        out.append('        <field name="res_model">x_gov_balady_line</field>')
        out.append('        <field name="column_name">%s</field>' % escape(flabel))
        out.append('        <field name="field_name">%s</field>' % name)
        out.append('    </record>')
    out.append('</odoo>')
    with open('x_gov_violations/data/import_mappings.xml', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
