// Shared components for the gov-violations dashboard (mcp.webapp.shared_components).
const GV_C = { navy: '#1F2D3D', blue: '#96CCED', lav: '#CFB0D4', car: '#FCD98F', grey: '#78787A', ink: '#1F2D3D', mut: '#6B6B6E', line: '#E6E7EB', bg: '#F5F6F8', red: '#C0392B', amber: '#B7791F', green: '#2F855A' };
const AUTH = { municipality: 'بلدي', labor: 'مكتب العمل', other: 'جهة أخرى' };
const STATUS = { unpaid: 'غير مسددة', paid: 'مسددة', cancelled: 'ملغية', linked: 'مرتبطة بدون غرامة' };
const OSTATE = { open: 'مفتوحة للاعتراض', filed: 'تم الاعتراض', expired: 'انتهت المهلة', not_allowed: 'الاعتراض غير مسموح' };
const OUTCOME = { pending: 'قيد النظر', accepted: 'مقبول', rejected: 'مرفوض' };
const DIV = { ew: 'سيدات', em: 'رجال', other: 'غير مرتبط بفرع' };


const divOf = (r) => (r.dv === 'ew' || r.dv === 'em' ? r.dv : 'other');
const byDiv = (rows, d) => rows.filter((r) => divOf(r) === d);
const fmt = (n) => Math.round(n || 0).toLocaleString('en-US');
const sum = (rows) => rows.reduce((t, r) => t + (r.amt || 0), 0);
const fd = (s) => (s ? s.split('-').reverse().join('/') : '—');
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0) + '%';
const openUrl = (r) => '/odoo/action-x_gov_violations.action_violation/' + r.id;


function csv(name, headers, rows, today) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const text = '﻿' + [headers.map(esc).join(',')].concat(rows.map((r) => r.map(esc).join(','))).join('\r\n');
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name + '_' + (today || window.__gvToday || '') + '.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const BASIC_H = ['رقم المخالفة', 'الجهة', 'الفرع', 'القسم', 'التصنيف', 'تاريخ المخالفة', 'المبلغ', 'حالة السداد', 'آخر موعد للاعتراض', 'نافذة الاعتراض', 'ملاحظة'];
const basicRow = (r) => [r.n, AUTH[r.a], r.b, DIV[divOf(r)], r.cat, r.d, r.amt, STATUS[r.s], r.dl, OSTATE[r.os], r.rr];
const FULL_H = BASIC_H.concat(['نتيجة الاعتراض', 'رقم الترخيص', 'الأمانة / البلدية', 'البند الرئيسي', 'رقم طلب الاعتراض', 'حالة طلب الاعتراض', 'قرار اللجنة', 'رقم الفاتورة', 'رقم السداد', 'تاريخ السداد', 'الوصف']);
const fullRow = (r) => basicRow(r).concat([OUTCOME[r.oo] || '', r.lic, r.mun, r.mi, r.oref, r.ost, r.cd, r.inv, r.sad, r.pd, r.desc]);


function Chip({ d }) {
  const k = divOf({ dv: d });
  const bg = k === 'ew' ? GV_C.lav : k === 'em' ? GV_C.blue : '#E2E3E7';
  return <span className="gv-chip" style={{ background: bg }}>{k === 'ew' ? 'EW' : k === 'em' ? 'EM' : '—'}</span>;
}
function StateChip({ r }) {
  if (r.s !== 'unpaid') return <span className="gv-muted">—</span>;
  const map = { open: ['#E6F4EA', GV_C.green], filed: ['#E8F1FB', '#2B6CB0'], expired: ['#F1F1F3', GV_C.mut], not_allowed: ['#F1F1F3', GV_C.mut] };
  const c = map[r.os] || map.expired;
  let label = OSTATE[r.os];
  if (r.os === 'filed' && r.oo) label += ' · ' + OUTCOME[r.oo];
  return <span className="gv-chip" style={{ background: c[0], color: c[1] }}>{label}</span>;
}
function Box({ title, amount, count, note, color, onClick, active }) {
  return (
    <div className={'gv-box' + (onClick ? ' gv-click' : '') + (active ? ' gv-active' : '')} onClick={onClick} style={{ borderTopColor: color || GV_C.blue }}>
      <div className="gv-box-t">{title}</div>
      <div className="gv-box-v">{fmt(amount)} <small>ريال</small></div>
      <div className="gv-box-n">{count} مخالفة</div>
      {note ? <div className="gv-box-note">{note}</div> : null}
    </div>
  );
}
function Section({ title, onCsv, children, extra }) {
  return (
    <section className="gv-card">
      <div className="gv-sec-h">
        <h3>{title}</h3>
        <div className="gv-sec-a">
          {extra}
          {onCsv ? <button className="gv-btn" onClick={onCsv}>تحميل CSV</button> : null}
        </div>
      </div>
      {children}
    </section>
  );
}
function Table({ rows, cols, empty }) {
  if (!rows.length) return <div className="gv-empty">{empty || 'لا توجد بيانات'}</div>;
  return (
    <div className="gv-tw">
      <table className="gv-t">
        <thead><tr>{cols.map((c) => <th key={c[0]}>{c[0]}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => <tr key={(r.id || i) + '-' + i}>{cols.map((c) => <td key={c[0]}>{c[1](r)}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}
const numCell = (r) => <a href={openUrl(r)} target="_blank" rel="noreferrer">{r.n}</a>;
const amtCell = (r) => <b>{fmt(r.amt)}</b>;


function Summary({ D, scoped, counted, paid, cancelled, outOfRegister, review, hasOther }) {
  const [more, setMore] = useState({ paid: false, cancelled: false, branches: false, action: false });
  const toggle = (k) => setMore(Object.assign({}, more, { [k]: !more[k] }));
  const gross = counted.concat(outOfRegister, paid, cancelled);
  const reasons = [];
  counted.forEach((r) => {
    let why = '';
    if (r.os === 'open' && r.dl && r.left !== null && r.left <= 7) why = 'تنتهي مهلة الاعتراض خلال ' + r.left + ' يوم';
    else if (r.os === 'expired' && r.left !== null && r.left >= -14) why = 'انتهت مهلة الاعتراض قبل ' + -r.left + ' يوم';
    else if (r.os === 'open' && !r.dl) why = 'موعد الاعتراض غير معروف';
    else if (r.os === 'filed' && r.oo === 'pending') why = 'اعتراض قيد النظر - تابع النتيجة';
    if (why) reasons.push(Object.assign({}, r, { why: why }));
  });
  reasons.sort((x, y) => (x.left === null ? 999 : x.left) - (y.left === null ? 999 : y.left));
  const branches = {};
  counted.filter((r) => r.b).forEach((r) => {
    branches[r.b] = branches[r.b] || { b: r.b, dv: r.dv, amt: 0, n: 0 };
    branches[r.b].amt += r.amt;
    branches[r.b].n += 1;
  });
  const brList = Object.values(branches).sort((x, y) => y.amt - x.amt);
  const latest = (rows) => rows.slice().sort((x, y) => (y.pd || y.d || '').localeCompare(x.pd || x.d || ''));
  function SplitCard({ title, rows, k }) {
    const list = latest(rows);
    return (
      <Section title={title} onCsv={() => csv(k, BASIC_H.concat(['تاريخ السداد']), list.map((r) => basicRow(r).concat([r.pd])))}
        extra={<span className="gv-muted">{rows.length} مخالفة · {fmt(sum(rows))} ريال</span>}>
        <div className="gv-split">
          {['ew', 'em', 'other'].map((d) => <div key={d}><Chip d={d} /> {DIV[d]}: <b>{fmt(sum(byDiv(rows, d)))}</b> <span className="gv-muted">({byDiv(rows, d).length})</span></div>)}
        </div>
        <Table rows={more[k] ? list : list.slice(0, 8)} cols={[['رقم المخالفة', numCell], ['الفرع', (r) => <span><Chip d={r.dv} /> {r.b || AUTH[r.a]}</span>], ['التاريخ', (r) => fd(r.pd || r.d)], ['المبلغ', amtCell]]} />
        {list.length > 8 ? <button className="gv-link" onClick={() => toggle(k)}>{more[k] ? 'عرض أقل' : 'عرض الكل (' + list.length + ')'}</button> : null}
      </Section>
    );
  }
  return (
    <div>
      <div className="gv-hero">
        <div>
          <div className="gv-hero-t">المبلغ المستحق (غير مسدد)</div>
          <div className="gv-hero-v">{fmt(sum(counted))} <small>ريال</small></div>
          <div className="gv-hero-n">{counted.length} مخالفة غير مسددة</div>
        </div>
        {outOfRegister.length ? <div className="gv-hero-note">لا يشمل {outOfRegister.length} مخالفة بلدية غير موجودة في آخر ملف بلدي ({fmt(sum(outOfRegister))} ريال) بانتظار التأكيد</div> : null}
      </div>
      <div className="gv-grid4">
        <Box title="مسددة" amount={sum(paid)} count={paid.length} color={GV_C.green} />
        <Box title="ملغية" amount={sum(cancelled)} count={cancelled.length} color={GV_C.grey} />
        <Box title="إجمالي الغرامات" amount={sum(gross)} count={gross.length} color={GV_C.blue} note="غير مسددة + مسددة + ملغية (بدون السجلات المرتبطة)" />
        <Box title="يحتاج تأكيد" amount={sum(review)} count={review.length} color={GV_C.car} note={pct(sum(review), sum(counted)) + ' من المبلغ المستحق'} />
      </div>
      <div className="gv-grid3">
        <Box title="سيدات (EW)" amount={sum(byDiv(counted, 'ew'))} count={byDiv(counted, 'ew').length} color={GV_C.lav} />
        <Box title="رجال (EM)" amount={sum(byDiv(counted, 'em'))} count={byDiv(counted, 'em').length} color={GV_C.blue} />
        <Box title="غير مرتبط بفرع" amount={sum(byDiv(counted, 'other'))} count={byDiv(counted, 'other').length} color={GV_C.grey}
          note={'مكتب العمل ' + fmt(sum(byDiv(counted, 'other').filter((r) => r.a === 'labor'))) + ' · الفنادق ' + fmt(sum(counted.filter((r) => r.dv === 'hotels'))) + ' · بلدي بدون فرع ' + fmt(sum(counted.filter((r) => r.dv === 'unalloc' && r.a !== 'labor')))} />
      </div>
      <Section title="يحتاج تصرف الآن" onCsv={() => csv('action_now', ['السبب'].concat(BASIC_H), reasons.map((r) => [r.why].concat(basicRow(r))))}
        extra={<span className="gv-muted">{reasons.length} مخالفة · {fmt(sum(reasons))} ريال</span>}>
        <Table rows={more.action ? reasons : reasons.slice(0, 12)} empty="لا يوجد ما يحتاج تصرفاً عاجلاً"
          cols={[['السبب', (r) => <b>{r.why}</b>], ['رقم المخالفة', numCell], ['الفرع', (r) => <span><Chip d={r.dv} /> {r.b || AUTH[r.a]}</span>], ['آخر موعد', (r) => fd(r.dl)], ['المبلغ', amtCell]]} />
        {reasons.length > 12 ? <button className="gv-link" onClick={() => toggle('action')}>{more.action ? 'عرض أقل' : 'عرض الكل (' + reasons.length + ')'}</button> : null}
      </Section>
      <Section title="أعلى الفروع في المبلغ المستحق" onCsv={() => csv('branches', ['الفرع', 'القسم', 'عدد المخالفات', 'المبلغ المستحق'], brList.map((b) => [b.b, DIV[divOf(b)], b.n, b.amt]))}>
        <Table rows={more.branches ? brList : brList.slice(0, 5)}
          cols={[['الفرع', (b) => <span><Chip d={b.dv} /> {b.b}</span>], ['عدد المخالفات', (b) => b.n], ['المبلغ المستحق', (b) => <b>{fmt(b.amt)}</b>], ['', (b) => <div className="gv-bar"><span style={{ width: (100 * b.amt) / (brList[0] ? brList[0].amt : 1) + '%', background: divOf(b) === 'ew' ? GV_C.lav : GV_C.blue }} /></div>]]} />
        {brList.length > 5 ? <button className="gv-link" onClick={() => toggle('branches')}>{more.branches ? 'عرض أقل' : 'عرض كل الفروع (' + brList.length + ')'}</button> : null}
      </Section>
      <div className="gv-grid2">
        <SplitCard title="المخالفات المسددة" rows={paid} k="paid" />
        <SplitCard title="المخالفات الملغية" rows={cancelled} k="cancelled" />
      </div>
    </div>
  );
}


function Objections({ D, scoped, counted, paid, cancelled, outOfRegister, review, hasOther }) {
  const [box, setBox] = useState('');
  const [q, setQ] = useState('');
  const [auth, setAuth] = useState('all');
  const [dv, setDv] = useState('all');
  const [br, setBr] = useState('all');
  const groups = {
    open_dl: counted.filter((r) => r.os === 'open' && r.dl),
    open_nodl: counted.filter((r) => r.os === 'open' && !r.dl),
    expired: counted.filter((r) => r.os === 'expired'),
    not_allowed: counted.filter((r) => r.os === 'not_allowed'),
    filed: counted.filter((r) => r.os === 'filed'),
  };
  const closing = groups.open_dl.filter((r) => r.left !== null && r.left <= 7);
  const maybeOpen = groups.expired.filter((r) => r.dw || r.sugg);
  const pending = groups.filed.filter((r) => r.oo === 'pending');
  const rejected = groups.filed.filter((r) => r.oo === 'rejected');
  const pick = (k) => setBox(box === k ? '' : k);
  const branchesList = Array.from(new Set(counted.map((r) => r.b).filter(Boolean))).sort();
  const ql = q.trim().toLowerCase();
  let list = box ? groups[box] : counted;
  list = list.filter((r) => (auth === 'all' || r.a === auth) && (dv === 'all' || divOf(r) === dv) && (br === 'all' || r.b === br)
    && (!ql || [r.n, r.b, r.lic, r.mun, r.oref].some((v) => (v || '').toLowerCase().indexOf(ql) >= 0)));
  list = list.slice().sort((x, y) => (x.dl || '9999').localeCompare(y.dl || '9999'));
  const warn = (r) => {
    const w = [];
    if (r.dw) w.push('تحذير تاريخ');
    if (r.sugg) w.push('موعد مقدّر');
    if (r.rv) w.push('يحتاج تأكيد');
    return w.join(' · ');
  };
  const total = Object.values(groups).reduce((t, g) => t + sum(g), 0);
  return (
    <div>
      <div className="gv-muted" style={{ marginBottom: 8 }}>الخانات الخمس مجموعها = المبلغ المستحق ({fmt(total)} ريال). اضغط على خانة لتصفية القائمة.</div>
      <div className="gv-grid5">
        <Box title="مفتوحة بموعد معروف" amount={sum(groups.open_dl)} count={groups.open_dl.length} color={GV_C.green} onClick={() => pick('open_dl')} active={box === 'open_dl'}
          note={'تنتهي خلال 7 أيام: ' + fmt(sum(closing)) + ' (' + closing.length + ')'} />
        <Box title="بدون موعد معروف" amount={sum(groups.open_nodl)} count={groups.open_nodl.length} color={GV_C.car} onClick={() => pick('open_nodl')} active={box === 'open_nodl'} />
        <Box title="انتهت المهلة" amount={sum(groups.expired)} count={groups.expired.length} color={GV_C.red} onClick={() => pick('expired')} active={box === 'expired'}
          note={'قد تكون مفتوحة إذا صُحّحت التواريخ: ' + fmt(sum(maybeOpen)) + ' (' + maybeOpen.length + ')'} />
        <Box title="الاعتراض غير مسموح" amount={sum(groups.not_allowed)} count={groups.not_allowed.length} color={GV_C.grey} onClick={() => pick('not_allowed')} active={box === 'not_allowed'} />
        <Box title="تم الاعتراض" amount={sum(groups.filed)} count={groups.filed.length} color="#2B6CB0" onClick={() => pick('filed')} active={box === 'filed'}
          note={'قيد النظر ' + fmt(sum(pending)) + ' (' + pending.length + ') · مرفوض ' + fmt(sum(rejected)) + ' (' + rejected.length + ')'} />
      </div>
      <div className="gv-grid2">
        <Box title="مسددة (خارج المجموع)" amount={sum(paid)} count={paid.length} color={GV_C.green} />
        <Box title="ملغية (خارج المجموع)" amount={sum(cancelled)} count={cancelled.length} color={GV_C.grey} />
      </div>
      <Section title={'المخالفات غير المسددة' + (box ? ' — ' + { open_dl: 'مفتوحة بموعد', open_nodl: 'بدون موعد', expired: 'انتهت المهلة', not_allowed: 'غير مسموح', filed: 'تم الاعتراض' }[box] : '')}
        onCsv={() => csv('objections', BASIC_H.concat(['الأيام المتبقية', 'نتيجة الاعتراض', 'رقم الترخيص', 'الأمانة / البلدية', 'رقم طلب الاعتراض', 'تنبيه']), list.map((r) => basicRow(r).concat([r.left, OUTCOME[r.oo] || '', r.lic, r.mun, r.oref, warn(r)])))}
        extra={<span className="gv-muted">{list.length} مخالفة · {fmt(sum(list))} ريال</span>}>
        <div className="gv-filters">
          <input placeholder="بحث: رقم، فرع، ترخيص، بلدية، رقم اعتراض" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={auth} onChange={(e) => setAuth(e.target.value)}>
            <option value="all">كل الجهات</option><option value="municipality">بلدي</option><option value="labor">مكتب العمل</option>
            {hasOther ? <option value="other">جهة أخرى</option> : null}
          </select>
          <select value={dv} onChange={(e) => setDv(e.target.value)}>
            <option value="all">EW / EM / أخرى</option><option value="ew">سيدات (EW)</option><option value="em">رجال (EM)</option><option value="other">غير مرتبط بفرع</option>
          </select>
          <select value={br} onChange={(e) => setBr(e.target.value)}>
            <option value="all">كل الفروع</option>
            {branchesList.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
          {box ? <button className="gv-link" onClick={() => setBox('')}>إلغاء تصفية الخانة</button> : null}
        </div>
        <Table rows={list}
          cols={[['رقم المخالفة', numCell], ['الجهة', (r) => AUTH[r.a]], ['الفرع', (r) => <span><Chip d={r.dv} /> {r.b || '—'}</span>],
            ['آخر يوم للاعتراض', (r) => fd(r.dl)], ['المتبقي', (r) => (r.os === 'open' && r.left !== null ? r.left + ' يوم' : '—')],
            ['الحالة', (r) => <StateChip r={r} />], ['المبلغ', amtCell], ['تنبيه', (r) => <span className="gv-warn">{warn(r)}</span>]]} />
      </Section>
    </div>
  );
}


function AllRows({ D, scoped, counted, paid, cancelled, outOfRegister, review, hasOther }) {
  const [q, setQ] = useState('');
  const [st, setSt] = useState('all');
  const [dv, setDv] = useState('all');
  const ql = q.trim().toLowerCase();
  const list = scoped.filter((r) => (st === 'all' || r.s === st) && (dv === 'all' || divOf(r) === dv)
    && (!ql || [r.n, r.b, r.lic, r.mun, r.oref, r.cat, r.mi].some((v) => (v || '').toLowerCase().indexOf(ql) >= 0)));
  return (
    <Section title="كل المخالفات" onCsv={() => csv('all_violations', FULL_H, list.map(fullRow))}
      extra={<span className="gv-muted">{list.length} سجل · {fmt(sum(list))} ريال</span>}>
      <div className="gv-filters">
        <input placeholder="بحث: رقم، فرع، ترخيص، بلدية، رقم اعتراض، تصنيف" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={st} onChange={(e) => setSt(e.target.value)}>
          <option value="all">كل الحالات</option>
          {Object.keys(STATUS).map((k) => <option key={k} value={k}>{STATUS[k]}</option>)}
        </select>
        <select value={dv} onChange={(e) => setDv(e.target.value)}>
          <option value="all">EW / EM / أخرى</option><option value="ew">سيدات (EW)</option><option value="em">رجال (EM)</option><option value="other">غير مرتبط بفرع</option>
        </select>
      </div>
      <Table rows={list}
        cols={[['رقم المخالفة', numCell], ['الجهة', (r) => AUTH[r.a]], ['الفرع', (r) => <span><Chip d={r.dv} /> {r.b || '—'}</span>], ['التصنيف', (r) => r.cat],
          ['التاريخ', (r) => fd(r.d)], ['المبلغ', amtCell], ['الحالة', (r) => STATUS[r.s]], ['نافذة الاعتراض', (r) => <StateChip r={r} />],
          ['الترخيص', (r) => r.lic], ['البلدية', (r) => r.mun], ['تنبيه', (r) => <span className="gv-warn">{[r.rv ? 'يحتاج تأكيد' : '', r.dw ? 'تحذير تاريخ' : '', !r.inr && r.s === 'unpaid' ? 'خارج سجل بلدي' : ''].filter(Boolean).join(' · ')}</span>]]} />
    </Section>
  );
}


