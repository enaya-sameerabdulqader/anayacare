function GovViolationsPage({ initialData }) {
  const D = initialData || {};
  const [tab, setTab] = useState('sum');
  const [company, setCompany] = useState('all');
  const [authority, setAuthority] = useState('all');

  if (D.denied) {
    return <div className="gv" dir="rtl"><div className="gv-card" style={{ margin: 40 }}>لا تملك صلاحية عرض هذه اللوحة.</div></div>;
  }
  window.__gvToday = D.today;
  const all = D.rows || [];
  const hasOther = all.some((r) => r.a === 'other');
  const scoped = all.filter((r) => (company === 'all' || String(r.c) === company) && (authority === 'all' || r.a === authority));

  const counted = scoped.filter((r) => r.cnt);
  const paid = scoped.filter((r) => r.s === 'paid');
  const cancelled = scoped.filter((r) => r.s === 'cancelled');
  const outOfRegister = scoped.filter((r) => r.s === 'unpaid' && !r.cnt);
  const review = counted.filter((r) => r.rv);

  const ctx = { D, scoped, counted, paid, cancelled, outOfRegister, review, hasOther };
  return (
    <div className="gv" dir="rtl">
      <header className="gv-head">
        <div>
          <h1>المخالفات الحكومية</h1>
          <div className="gv-sub">آخر تحديث {D.now || ''} · {D.user || ''}</div>
        </div>
        <div className="gv-gf">
          <select value={company} onChange={(e) => setCompany(e.target.value)}>
            <option value="all">كل الشركات</option>
            {(D.companies || []).map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
          </select>
          <select value={authority} onChange={(e) => setAuthority(e.target.value)}>
            <option value="all">كل الجهات</option><option value="municipality">بلدي</option><option value="labor">مكتب العمل</option>
            {hasOther ? <option value="other">جهة أخرى</option> : null}
          </select>
        </div>
      </header>
      <nav className="gv-tabs">
        {[['sum', 'الملخص'], ['obj', 'الاعتراضات'], ['all', 'كل المخالفات']].map((t) => (
          <button key={t[0]} className={tab === t[0] ? 'on' : ''} onClick={() => setTab(t[0])}>{t[1]}</button>
        ))}
      </nav>
      <main className="gv-main">
        {tab === 'sum' ? <Summary {...ctx} /> : tab === 'obj' ? <Objections {...ctx} /> : <AllRows {...ctx} />}
        <div className="gv-foot">المصدر: سجل المخالفات الحكومية في Odoo (ملف بلدي + السجل الموحد). السجلات المرتبطة بدون غرامة مستبعدة من المبالغ والأعداد. نافذة الاعتراض محسوبة من تاريخ اليوم.</div>
      </main>
    </div>
  );
}
