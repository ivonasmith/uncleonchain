/* Alpha 雷达前端：评估器（#alpha-app[data-mode=eval]）与案例库（data-mode=cases）。
   数据：/data/alpha/framework.json（框架，单一来源）、cases.json（历史案例 + 回溯评分）、case_metrics.json（接口算出的结果）、case_series.json（周线）。
   规则都在 framework.json 里；这里只做计算和渲染，别在这里改口径。 */
(function () {
  'use strict';
  const EN = (document.documentElement.lang || '').startsWith('en');
  const T = (z, e) => (EN && e ? e : z);
  const app = document.getElementById('alpha-app');
  if (!app) return;
  const MODE = app.dataset.mode;
  const V = app.dataset.v || '';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const J = p => fetch(p + (V ? '?v=' + V : '')).then(r => { if (!r.ok) throw new Error(p + ' ' + r.status); return r.json(); });
  const med = a => { const s = a.filter(x => x != null && isFinite(x)).sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const usd = v => v == null ? '—' : v >= 1e9 ? '$' + (v / 1e9).toFixed(v >= 1e10 ? 0 : 1) + 'B' : v >= 1e6 ? '$' + (v / 1e6).toFixed(v >= 1e8 ? 0 : 1) + 'M' : v >= 1e3 ? '$' + (v / 1e3).toFixed(0) + 'K' : '$' + v.toFixed(0);
  const mx = v => v == null ? '—' : v >= 100 ? '×' + Math.round(v).toLocaleString() : '×' + v.toFixed(v >= 10 ? 0 : 1);
  const dd = v => v == null ? '—' : v + T(' 天', 'd');

  let FW, CASES, MET, SER;

  /* ---------- 公共：案例结果（主代币） ---------- */
  function outcome(c) {
    const m = (MET.cases || {})[c.id] || {};
    const t = (m.tokens || []).find(x => x.role === 'main') || null;
    return { tok: t, fees: m.fees || null, tvl: m.tvl || null, errors: m.errors || [] };
  }
  function tierOf(v) {
    if (v == null) return null;
    const tiers = FW.outcomes.dims.find(d => d.k === 'val_peak').tiers;
    for (const [cut, name] of tiers) if (v >= cut) return name;
    return null;
  }
  const BIZ = () => Object.fromEntries(FW.classes.business.opts.map(o => [o.k, o.name]));
  const RIGHT = () => Object.fromEntries(FW.classes.right.opts.map(o => [o.k, o.name]));
  const OPP = () => Object.fromEntries(FW.classes.opportunity.opts.map(o => [o.k, o.name]));

  /* ---------- 公共：区间与覆盖（附录一 D / E） ---------- */
  function interval(vals, max) {
    const ap = vals.filter(v => v !== 'NA');
    const m = ap.length;
    if (!m) return null;
    const known = ap.filter(v => v !== 'U' && v !== '' && v != null).map(Number);
    const s = known.reduce((a, b) => a + b, 0);
    const u = m - known.length;
    return { lo: Math.round(100 * s / (max * m)), hi: Math.round(100 * (s + max * u) / (max * m)), cov: known.length / m, n: m, u };
  }

  /* ---------- 公共：相似度（第十五节 match） ---------- */
  const NUM = ['M', 'E', 'V', 'D'];
  function similar(q, c) {
    let d = 0, w = 0, used = [];
    for (const k of ['business', 'right', 'opportunity']) {
      if (q[k] && c.classes[k]) { w += 2; if (q[k] !== c.classes[k]) d += 2; else used.push(k); }
    }
    for (const k of NUM) {
      const a = q.scores[k], b = c.scores[k];
      if (a !== '' && a != null && a !== 'U' && b !== 'U' && b != null) { w += 4; d += Math.abs(Number(a) - Number(b)); used.push(k); }
    }
    if (used.length < 3 && w < 12) return null;   // 至少比 3 项（类别一致或分数都已知）才比较
    let n = 0; for (const k of ['business', 'right', 'opportunity']) if (q[k] && c.classes[k]) n++; for (const k of NUM) { const a = q.scores[k], b = c.scores[k]; if (a !== '' && a != null && a !== 'U' && b !== 'U' && b != null) n++; }
    if (n < 3) return null;
    return { sim: 1 - d / w, n };
  }

  /* ====================================================================== 评估器 */
  const KEY = 'alpha-eval-v1';
  function blank() {
    return { name: '', chain: '', asset: '', role: '', asof: new Date().toISOString().slice(0, 10), stage: '', attribute: '', mode: 'research',
             business: '', right: '', opportunity: '', capture_case: '', path: [], q: {}, qn: {}, gates: {}, gn: {},
             scores: { M: '', A: '', F: '', E: '', V: '', G: '', P: '', D: '', L: '', T: '' }, token: {}, deep: {}, six: {}, counter: '', refl: {}, review: '' };
  }
  let S = blank();
  function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* 隐私模式 */ } }
  function loadSaved() { try { const x = JSON.parse(localStorage.getItem(KEY) || 'null'); if (x && x.scores) S = Object.assign(blank(), x); } catch (e) { /* 忽略 */ } }

  function optPills(name, opts, multi) {
    const cur = multi ? (S[name] || []) : S[name];
    return '<div class="opts">' + opts.map(o => {
      const on = multi ? cur.includes(o.k) : cur === o.k;
      return `<label class="opt${on ? ' on' : ''}${o.out_of_scope ? ' oos' : ''}" title="${esc(o.why || o.basis || o.source || o.then || '')}"><input type="${multi ? 'checkbox' : 'radio'}" name="${name}" value="${o.k}"${on ? ' checked' : ''}${o.out_of_scope ? ' disabled' : ''}>${esc(o.name)}${o.out_of_scope ? T('（本板块不做）', ' (out of scope)') : ''}</label>`;
    }).join('') + '</div>';
  }
  function anchorRow(group, it, max, cur, allowNA) {
    const btn = (v, label, cls) => `<button type="button" data-g="${group}" data-k="${it.k}" data-v="${v}" class="${cls || ''}${String(cur) === String(v) ? ' on' : ''}">${label}</button>`;
    return `<div class="sc-item"><div class="sc-head"><b>${esc(it.k.length <= 2 ? it.k + ' · ' : '')}${esc(it.name)}</b>${it.q ? `<span class="q">${esc(it.q)}</span>` : ''}${it.private ? `<span class="tag">${T('执行相关', 'execution')}</span>` : ''}</div>
      <div class="anc">${it.anchors.map((a, i) => btn(i, `<span class="n">${i}</span>${esc(a)}`)).join('')}${btn('U', `<span class="n">U</span>${T('未知', 'unknown')}`, 'u')}${allowNA ? btn('NA', `<span class="n">NA</span>${T('不适用', 'n/a')}`, 'u') : ''}</div></div>`;
  }
  function stateSel(name, k, states, cur) {
    return `<select data-${name}="${k}"><option value="">—</option>${states.map(s => `<option${cur === s ? ' selected' : ''}>${esc(s)}</option>`).join('')}</select>`;
  }

  function renderForm() {
    const f = FW, c = f.classes;
    const presetOpts = CASES.cases.map(x => `<option value="${x.id}">${esc(x.name)}${x.control ? T('（对照组）', ' (control)') : ''}</option>`).join('');
    let h = `<div class="btns"><select id="ax-preset" style="max-width:260px"><option value="">${T('从历史案例载入（练手 / 校准）…', 'Load a historical case…')}</option>${presetOpts}</select>
      <button type="button" class="btn" id="ax-new">${T('清空', 'Clear')}</button><button type="button" class="btn" id="ax-export">${T('导出 JSON', 'Export JSON')}</button>
      <label class="btn" style="cursor:pointer">${T('导入 JSON', 'Import JSON')}<input type="file" id="ax-import" accept=".json,application/json" hidden></label></div>
      <p class="small muted">${T('填的内容只存在你这台浏览器里（自动保存）。要登记进候选池，导出 JSON 发给大叔 / Claude。', 'Entries stay in this browser (auto-saved). Export JSON to register a candidate.')}</p>`;
    // 1 对象
    h += `<fieldset><legend>1 · ${T('研究对象', 'Object')}<span class="sec">${esc(f.unit.sec)}</span></legend>
      <p class="small muted" style="margin:0 0 8px">${esc(f.unit.text)}</p>
      ${[['name', T('协议 / 版本', 'Protocol / version')], ['chain', T('链', 'Chain')], ['asset', T('资产 / 合约', 'Asset / contract')], ['role', T('参与角色与动作', 'Role & action')], ['asof', T('观察时点', 'As of')]]
        .map(([k, l]) => `<div class="row"><label>${l}</label><input type="text" data-f="${k}" value="${esc(S[k])}"></div>`).join('')}
      <div class="row"><label>${esc(c.stage.name)}</label>${optPills('stage', c.stage.opts)}</div>
      <div class="row"><label>${esc(c.attribute.name)}</label>${optPills('attribute', c.attribute.opts)}</div>
    </fieldset>`;
    // 2 价值来源
    h += `<fieldset><legend>2 · ${T('价值来源', 'Value source')}<span class="sec">${T('二.3–二.5 · 一.2 · 四.3', '')}</span></legend>
      <div class="row"><label>${esc(c.business.name)}</label>${optPills('business', c.business.opts)}<div class="hint">${esc(c.business.rule)}</div></div>
      <div class="row"><label>${esc(c.right.name)}</label>${optPills('right', c.right.opts)}<div class="hint">${esc(c.right.rule)}</div></div>
      <div class="row"><label>${esc(c.capture_case.name)}</label>${optPills('capture_case', c.capture_case.opts)}</div>
      <div class="row"><label>${esc(c.opportunity.name)}</label>${optPills('opportunity', c.opportunity.opts)}<div class="hint">${esc(c.opportunity.rule)}</div></div>
      <div class="row"><label>${esc(c.path.name)}</label>${optPills('path', c.path.opts, true)}<div class="hint">${esc(c.path.rule)}</div></div>
    </fieldset>`;
    // 3 四问
    h += `<fieldset><legend>3 · ${esc(f.questions.name)}<span class="sec">${esc(f.questions.sec)}</span></legend>
      ${f.questions.items.map(q => `<div class="row"><label>${esc(q.axis)}</label><div>${stateSel('q', q.k, f.questions.states, S.q[q.k])}<div class="hint" style="margin:4px 0">${esc(q.name)} ${esc(q.hint)}</div><textarea data-qn="${q.k}" placeholder="${T('证据 / 下一步查什么', 'evidence / next check')}">${esc(S.qn[q.k] || '')}</textarea></div></div>`).join('')}
    </fieldset>`;
    // 4 门槛
    h += `<fieldset><legend>4 · ${esc(f.gates.name)}<span class="sec">${esc(f.gates.sec)}</span></legend>
      <p class="small muted" style="margin:0 0 8px">${esc(f.gates.state_rule)}</p>
      ${f.gates.items.map(g => `<div class="row"><label>${esc(g.name)}${g.private ? `<span class="tag">${T('执行相关', 'execution')}</span>` : ''}</label><div>${stateSel('g', g.k, f.gates.states, S.gates[g.k])}
        <ul class="why">${g.checks.map(x => `<li>${esc(x)}</li>`).join('')}</ul><div class="hint" style="margin:4px 0">${esc(g.unknown_rule)}</div>
        <textarea data-gn="${g.k}" placeholder="${T('证据', 'evidence')}">${esc(S.gn[g.k] || '')}</textarea></div></div>`).join('')}
    </fieldset>`;
    // 5 评分
    const sc = f.scores;
    h += `<fieldset><legend>5 · ${T('评分', 'Scores')}<span class="sec">${T('附录一', 'App. 1')}</span></legend><p class="small muted" style="margin:0 0 8px">${esc(sc.rule)}</p>
      <h4 style="margin:6px 0 2px">${esc(sc.mech.name)} <span class="muted small">${esc(sc.mech.applies)}</span></h4>
      ${sc.mech.items.map(it => anchorRow('s', it, 4, S.scores[it.k])).join('')}
      <h4 style="margin:12px 0 2px">${esc(sc.part.name)} <span class="muted small">${esc(sc.part.applies)}</span></h4>
      ${sc.part.items.map(it => anchorRow('s', it, 4, S.scores[it.k])).join('')}
      <h4 style="margin:12px 0 2px">${esc(sc.token.name)} <span class="muted small">${esc(sc.token.applies)}</span></h4>
      ${sc.invest ? `<h4 style="margin:12px 0 2px">${esc(sc.invest.name)} <span class="muted small">${esc(sc.invest.applies)} · 0–3</span></h4>${sc.invest.items.map(it => anchorRow('t', it, 3, S.token[it.k], true)).join('')}` : ''}
      ${S.right === 'none' ? `<p class="small muted">${T('资产权利选了「暂无代币」：七项不评。', 'No token: the seven token modules are skipped.')}</p>` : sc.token.items.map(it => anchorRow('t', it, 3, S.token[it.k], true)).join('')}
    </fieldset>`;
    // 6 深度判断 + 六句话
    h += `<fieldset><legend>6 · ${esc(f.deep.name)}<span class="sec">${esc(f.deep.sec)}</span></legend>
      ${f.deep.items.map(d => `<div class="row"><label>${esc(d.name)}</label><div><div class="hint" style="margin:0 0 4px">${esc(d.prompt)}</div><textarea data-deep="${d.k}">${esc(S.deep[d.k] || '')}</textarea></div></div>`).join('')}
    </fieldset>
    <fieldset><legend>7 · ${esc(f.six.name)}<span class="sec">${esc(f.six.sec)}</span></legend>
      ${f.six.items.map(d => `<div class="row"><label>${esc(d.name)}</label><div><div class="hint" style="margin:0 0 4px">${esc(d.need)}</div><textarea data-six="${d.k}">${esc(S.six[d.k] || '')}</textarea></div></div>`).join('')}
      <div class="row"><label>${T('最强反方', 'Strongest counter')}</label><div><div class="hint" style="margin:0 0 4px">${esc(f.six.counter)}</div><textarea data-f="counter">${esc(S.counter || '')}</textarea></div></div>
      <div class="row"><label>${T('复查日', 'Review date')}</label><input type="text" data-f="review" value="${esc(S.review || '')}" placeholder="YYYY-MM-DD"></div>
    </fieldset>`;
    // 反身性（选了反身性路径或叙事权利才出现）
    if ((S.path || []).includes('reflexive') || S.right === 'narrative') {
      const r = f.reflexive;
      h += `<fieldset><legend>8 · ${esc(r.name)}<span class="sec">${esc(r.sec)}</span></legend><p class="small muted" style="margin:0 0 6px">${esc(r.loop)}</p><p class="small" style="margin:0 0 8px"><b>${T('核心比较：', 'Core test: ')}</b>${esc(r.core)}</p>
        ${r.items.map(it => `<div class="row"><label>${esc(it.name)}</label><div><select data-refl="${it.k}"><option value="">—</option>${[T('正常', 'ok'), T('出现转折迹象', 'turning'), T('未知', 'unknown')].map(s => `<option${S.refl[it.k] === s ? ' selected' : ''}>${s}</option>`).join('')}</select><div class="hint" style="margin:4px 0">${T('观测：', 'Watch: ')}${esc(it.watch)}；${T('转折：', 'Turn: ')}${esc(it.turn)}</div></div></div>`).join('')}
        <p class="small muted">${T('三个压力情景：', 'Stress: ')}${r.stress.map(esc).join(' / ')}</p></fieldset>`;
    }
    document.getElementById('ax-form').innerHTML = h;
  }

  function suggest() {
    const why = [];
    const G = S.gates || {};
    if (Object.values(G).includes('否决')) return { st: T('拒绝或停止假设', 'Rejected'), cls: 'no', why: [T('有门槛被否决：高分不能抵消（四.2）', 'A gate failed; scores cannot offset it (4.2)')] };
    if (!S.name) why.push(T('还没写研究对象', 'No object yet'));
    if (!(S.path || []).length) why.push(T('还没写出可证伪路径（四.3）', 'No falsifiable path (4.3)'));
    if (!(S.six || {}).falsify) why.push(T('还没写「什么会推翻判断」', 'No falsification condition'));
    if (!S.name || !(S.path || []).length) return { st: T('原始线索', 'Raw lead'), cls: 'wait', why };
    // 框架 states.infer：门槛待核验不阻挡研究观察，只阻挡执行评估（四.1 研究观察的条件是「尚无已证实否决项」）
    const pend = [];
    if (G.safety !== '通过') pend.push(T('安全门槛未通过：不挡研究观察，但挡执行评估', 'safety gate open (blocks execution, not watching)'));
    if (G.data !== '通过') pend.push(T('数据门槛未通过：不挡研究观察，但挡执行评估', 'data gate open (blocks execution, not watching)'));
    const qs = FW.questions.items.filter(q => (S.q || {})[q.k] !== '已证实').map(q => q.axis);
    const allOpen = qs.length === FW.questions.items.length;
    if (!(S.six || {}).falsify || allOpen) return { st: T('待核验', 'To verify'), cls: 'wait', why: why.concat(allOpen ? [T('四个问题一个都没证实', 'None of the four questions confirmed')] : [], pend) };
    return { st: T('研究观察', 'Watching'), cls: 'ok', why: [T('对象明确、有可证伪路径、门槛无否决（四.1）。要升「优先研究」需要出现独立证据改善且窗口有时效，由研究者判断。', 'Clear object, falsifiable path, no veto (4.1). Promotion to priority needs independent new evidence and a time-bound window.')].concat(qs.length ? [T('仍未证实：', 'Still open: ') + qs.join('、')] : [], pend) };
  }

  function renderPanel() {
    const f = FW, sc = f.scores;
    const iv = {
      mech: interval(sc.mech.items.map(i => S.scores[i.k] === '' ? 'U' : S.scores[i.k]), 4),
      part: interval(sc.part.items.map(i => S.scores[i.k] === '' ? 'U' : S.scores[i.k]), 4),
      token: S.right === 'none' ? null : interval(sc.token.items.map(i => S.token[i.k] == null || S.token[i.k] === '' ? 'U' : S.token[i.k]), 3),
      inv: sc.invest ? interval(sc.invest.items.map(i => S.token[i.k] == null || S.token[i.k] === '' ? 'U' : S.token[i.k]), 3) : null,
    };
    const bar = x => x ? `<div class="meter"><i style="left:0;width:${x.lo}%"></i><i class="span" style="left:${x.lo}%;width:${x.hi - x.lo}%"></i></div><div class="kv"><span>${T('区间', 'Range')} <b>${x.lo}–${x.hi}</b></span><span>${T('覆盖', 'Coverage')} <b>${Math.round(x.cov * 100)}%</b></span></div>` : `<div class="small muted">${T('不适用', 'n/a')}</div>`;
    const sug = suggest();
    const promo = [];
    if (iv.mech && iv.mech.lo >= 60 && iv.mech.cov >= 0.8) promo.push(sc.promote[0].name);
    const P = S.scores.P, L = S.scores.L;
    if (iv.part && iv.part.lo >= 60 && iv.part.cov >= 0.8 && P !== '' && P !== 'U' && L !== '' && L !== 'U' && +P >= 2 && +L >= 2) promo.push(sc.promote[1].name);
    // 估值
    const rt = f.classes.right.opts.find(o => o.k === S.right);
    const bizVal = { trading: 'trading', realworld: 'payment', infra: 'resource' }[S.business];
    const vrows = f.valuation.rows.filter(r => (rt && r.k === rt.val) || r.k === bizVal);
    const cc = f.classes.capture_case.opts.find(o => o.k === S.capture_case);
    // 监控计划
    const want = new Set(['mech', 'safety', 'data']);
    if (['cashflow', 'governance'].includes(S.right)) want.add('capture');
    if (S.opportunity === 'genesis' || (S.path || []).includes('reflexive') || S.right === 'narrative') want.add('reflexive');
    if (S.right && S.right !== 'none') { want.add('supply'); want.add('structure'); }
    if (['community', 'mixed'].includes(S.attribute)) want.add('community');
    const planes = f.monitor.planes.filter(p => want.has(p.k));
    // 相似案例
    const q = { business: S.business, right: S.right === 'none' ? '' : S.right, opportunity: S.opportunity, scores: S.scores };
    const sims = CASES.cases.map(c => ({ c, s: similar(q, c), o: outcome(c) })).filter(x => x.s).sort((a, b) => b.s.sim - a.s.sim).slice(0, 6);
    const withOut = sims.filter(x => x.o.tok);
    const rng = (arr, fmt) => { const v = arr.filter(x => x != null && isFinite(x)).sort((a, b) => a - b); if (!v.length) return '—'; return `<span class="range">${fmt(v[0])} · <span class="md">${fmt(med(v))}</span> · ${fmt(v[v.length - 1])}</span>`; };

    let h = `<div class="card"><div class="kv" style="align-items:center"><span>${T('建议状态', 'Suggested state')}</span><span class="st ${sug.cls}">${esc(sug.st)}</span></div>${sug.why.length ? `<ul class="why">${sug.why.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
      <p class="small muted" style="margin:8px 0 0">${T('状态按四.1 / 四.2 自动推断，只是提示；「优先研究」「执行评估」由研究者定，网站不公开执行评估。', 'Inferred from 4.1 / 4.2 as a hint only.')}</p></div>`;
    h += `<div class="card" style="margin-top:12px"><b>${esc(sc.mech.name)}</b>${bar(iv.mech)}<b style="display:block;margin-top:8px">${esc(sc.part.name)}</b>${bar(iv.part)}<b style="display:block;margin-top:8px">${esc(sc.token.name)}</b>${bar(iv.token)}${sc.invest ? `<b style="display:block;margin-top:8px">${esc(sc.invest.name)}</b>${bar(iv.inv)}` : ''}
      <p class="small muted" style="margin:8px 0 0">${esc(sc.formula.interval)}</p>
      <p class="small" style="margin:6px 0 0">${promo.length ? T('达到工作阈值：', 'Meets working threshold: ') + promo.map(esc).join('、') : T('未达到任何晋级工作阈值', 'Below all working thresholds')} <span class="muted">（${esc(sc.promote[0].note)}）</span></p></div>`;
    h += `<div class="card" style="margin-top:12px"><b>${T('估值该用什么', 'Valuation to use')}</b> <span class="muted small">${esc(f.valuation.sec)}</span>
      ${cc ? `<p class="small" style="margin:6px 0">${esc(cc.name)} → ${esc(cc.then)}</p>` : ''}
      ${vrows.length ? vrows.map(r => `<p class="small" style="margin:6px 0"><b>${esc(r.name)}</b><br>${T('用：', 'Use: ')}${esc(r.use)}<br><span style="color:var(--dn)">${T('别：', 'Avoid: ')}</span>${esc(r.avoid)}</p>`).join('') : `<p class="small muted">${T('先选需求来源和资产权利', 'Pick demand source and asset right first')}</p>`}</div>`;
    h += `<div class="card" style="margin-top:12px"><b>${T('历史量级对照（预期管理）', 'Historical analogs (expectation management)')}</b>
      ${sims.length ? `<div class="tw" style="margin-top:8px"><table><thead><tr><th class="l">${T('最相近的案例', 'Closest cases')}</th><th>${T('相似', 'Sim')}</th><th>${T('估值峰值', 'Peak val.')}</th><th>${T('首周后倍数', 'From wk-1')}</th><th>${T('到峰', 'To peak')}</th></tr></thead><tbody>
        ${sims.map(x => `<tr><td class="l">${esc(x.c.name)}${x.c.control ? `<span class="tag ctl">${T('对照', 'control')}</span>` : ''}</td><td>${Math.round(x.s.sim * 100)}% <span class="muted">(${x.s.n}/7)</span></td><td>${x.o.tok ? usd(x.o.tok.val_peak) : '—'}</td><td>${x.o.tok ? mx(x.o.tok.mult_p7) : '—'}</td><td>${x.o.tok ? dd(x.o.tok.days_to_peak) : '—'}</td></tr>`).join('')}</tbody></table></div>
        <div class="kv" style="margin-top:8px"><span>${T('有结果数据的', 'With outcome data')}</span><b>${withOut.length} / ${sims.length}</b></div>
        <div class="kv"><span>${T('估值峰值（最低 · 中位 · 最高）', 'Peak valuation (min · median · max)')}</span>${rng(withOut.map(x => x.o.tok.val_peak), usd)}</div>
        <div class="kv"><span>${T('首周后最高倍数', 'Max multiple from week 1')}</span>${rng(withOut.map(x => x.o.tok.mult_p7), mx)}</div>
        <div class="kv"><span>${T('相对 BTC（首周后）', 'Vs BTC (from week 1)')}</span>${rng(withOut.map(x => x.o.tok.rel_btc_peak_p7), mx)}</div>
        <div class="kv"><span>${T('到峰值天数', 'Days to peak')}</span>${rng(withOut.map(x => x.o.tok.days_to_peak), v => Math.round(v))}</div>
        <div class="kv"><span>${T('一年内收盘 ≥ 2×P0 的天数', 'Days ≥ 2× P0 in year 1')}</span>${rng(withOut.map(x => x.o.tok.days_ge2x_365), v => Math.round(v))}</div>
        <div class="kv"><span>${T('手续费热度天数', 'Fee hot days')}</span>${rng(sims.map(x => x.o.fees && !x.o.fees.late ? x.o.fees.hot_days : null), v => Math.round(v))}</div>`
        : `<p class="small muted">${T('至少选两类信息（需求来源 / 资产权利 / 机会类型 / M E V D）才找相似案例。', 'Pick at least two of: demand source, asset right, opportunity, M E V D.')}</p>`}
      <ul class="cav">${f.outcomes.caveats.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
      <a class="small" href="${EN ? '/en' : ''}/alpha/cases/">${T('看全部案例和口径 →', 'All cases & definitions →')}</a></div>`;
    h += `<div class="card" style="margin-top:12px"><b>${T('监控计划', 'Monitoring plan')}</b> <span class="muted small">${esc(f.monitor.sec)}</span>
      ${planes.map(p => `<p class="small" style="margin:6px 0"><b>${esc(p.name)}</b> · ${T('触发：', 'Trigger: ')}${esc(p.trigger)}<br><span class="muted">${T('输出：', 'Output: ')}${esc(p.out)}</span></p>`).join('')}
      <p class="small muted" style="margin:6px 0 0">${esc(f.monitor.rule)}</p>${S.review ? `<p class="small">${T('复查日：', 'Review: ')}<b>${esc(S.review)}</b></p>` : ''}</div>`;
    document.getElementById('ax-panel').innerHTML = h;
  }

  function bindForm() {
    const form = document.getElementById('ax-form');
    form.addEventListener('click', e => {
      const b = e.target.closest('button[data-g]');
      if (!b) return;
      const tgt = b.dataset.g === 's' ? S.scores : S.token;
      const v = b.dataset.v;
      tgt[b.dataset.k] = (tgt[b.dataset.k] === v || String(tgt[b.dataset.k]) === v) ? '' : (v === 'U' || v === 'NA' ? v : Number(v));
      b.parentElement.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b && tgt[b.dataset.k] !== ''));
      save(); renderPanel();
    });
    form.addEventListener('change', e => {
      const t = e.target;
      if (t.type === 'radio') { S[t.name] = S[t.name] === t.value ? '' : t.value; save(); renderForm(); renderPanel(); return; }
      if (t.type === 'checkbox') { const a = new Set(S[t.name] || []); t.checked ? a.add(t.value) : a.delete(t.value); S[t.name] = [...a]; save(); renderForm(); renderPanel(); return; }
      if (t.dataset.q) S.q[t.dataset.q] = t.value;
      if (t.dataset.g) S.gates[t.dataset.g] = t.value;
      if (t.dataset.refl) S.refl[t.dataset.refl] = t.value;
      save(); renderPanel();
    });
    form.addEventListener('input', e => {
      const t = e.target;
      for (const [attr, obj] of [['f', null], ['qn', 'qn'], ['gn', 'gn'], ['deep', 'deep'], ['six', 'six']]) {
        if (t.dataset[attr] != null) { if (obj) S[obj][t.dataset[attr]] = t.value; else S[t.dataset.f] = t.value; }
      }
      save(); clearTimeout(bindForm.t); bindForm.t = setTimeout(renderPanel, 250);
    });
  }

  function bindTools() {
    document.addEventListener('change', e => {
      if (e.target.id === 'ax-preset' && e.target.value) {
        const c = CASES.cases.find(x => x.id === e.target.value);
        S = blank();
        Object.assign(S, { name: c.name, asof: c.period, business: c.classes.business, right: c.classes.right, opportunity: c.classes.opportunity, attribute: c.classes.attribute });
        for (const k of 'MAFEVD') S.scores[k] = c.scores[k] === 'U' ? 'U' : c.scores[k];
        save(); renderForm(); renderPanel();
      }
      if (e.target.id === 'ax-import' && e.target.files[0]) {
        e.target.files[0].text().then(t => { try { S = Object.assign(blank(), JSON.parse(t)); save(); renderForm(); renderPanel(); } catch (err) { alert(T('不是有效的 JSON', 'Invalid JSON')); } });
      }
    });
    document.addEventListener('click', e => {
      if (e.target.id === 'ax-new') { if (confirm(T('清空当前填写？', 'Clear the form?'))) { S = blank(); save(); renderForm(); renderPanel(); } }
      if (e.target.id === 'ax-export') {
        const card = Object.assign({ framework: FW.version, exported: new Date().toISOString() }, S);
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([JSON.stringify(card, null, 1)], { type: 'application/json' }));
        a.download = 'alpha-card-' + (S.name || 'draft').replace(/[^\w一-龥-]+/g, '_') + '.json';
        a.click();
      }
    });
  }

  function initEval() {
    loadSaved();
    app.innerHTML = `<div class="grid2"><div id="ax-form"></div><div class="sticky" id="ax-panel"></div></div>`;
    renderForm(); renderPanel(); bindForm(); bindTools();
  }

  /* ====================================================================== 公共：卡片零件（和宏观仪表盘同一套：.glass.hero 大数字卡、站点走势图组件、ⓘ 提示） */
  const SRC = { auto: ['系统', 'auto'], research: ['研究', 'research'], retro: ['回溯', 'retro'] };
  const srcTag = s => s && SRC[s] ? `<span class="tag">${T(SRC[s][0], SRC[s][1])}</span>` : '';
  const STC = { '研究观察': 'up', '优先研究': 'up', '待核验': 'warn', '原始线索': 'neutral', '拒绝': 'dn' };
  const ENTRY = () => Object.fromEntries(FW.entry.opts.map(o => [o.k, o.name]));
  const tip = t => t ? `<button type="button" class="info" data-tip="${esc(t)}">i</button>` : '';
  const chip = (txt, tone) => `<span class="chip t-${tone || 'neutral'}"><i></i>${esc(txt)}</span>`;
  const logo = (src, name, size) => { const ini = esc(String(name || '?').replace(/[^A-Za-z0-9\u4e00-\u9fa5]/g, '').slice(0, 1).toUpperCase() || '?');
    return `<span class="ax-logo" style="width:${size || 22}px;height:${size || 22}px">${src ? `<img src="${esc(src)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}<b>${ini}</b></span>`; };
  const links = (url, tw, slug) => [url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${T('官网', 'Website')} ↗</a>` : '',
    tw ? `<a href="https://x.com/${esc(tw)}" target="_blank" rel="noopener">X ↗</a>` : '', slug ? `<a href="https://defillama.com/protocol/${esc(slug)}" target="_blank" rel="noopener">DefiLlama ↗</a>` : ''].filter(Boolean).join('');
  const pct = v => v == null ? '' : `<span class="t-${v >= 0 ? 'up' : 'dn'}">${v >= 0 ? '+' : ''}${Math.round(v)}%</span>`;
  function sparkSvg(vals, tone, w, h) {
    const v = (vals || []).filter(x => x != null);
    if (v.length < 3) return '';
    w = w || 90; h = h || 26;
    const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
    const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - 2 - (x - lo) / r * (h - 4)).toFixed(1)}`).join(' ');
    return `<svg class="ax-spark t-${tone || 'up'}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><polyline points="${pts}"/></svg>`;
  }
  function cardIntervals(card) {
    const val = k => { const s = card.scores[k]; return s == null || s.v === '' || s.v == null ? 'U' : s.v; };
    return { mech: interval(FW.scores.mech.items.map(i => val(i.k)), 4), part: interval(FW.scores.part.items.filter(i => !i.private).map(i => val(i.k)), 4),
             inv: FW.scores.invest ? interval(FW.scores.invest.items.map(i => val(i.k)), 3) : null };
  }
  const meter = x => x ? `<div class="meter"><i style="left:0;width:${x.lo}%"></i><i class="span" style="left:${x.lo}%;width:${x.hi - x.lo}%"></i></div>` : '';
  function analogs(card, k) {
    const q = { business: card.classes.business.v === 'U' ? '' : card.classes.business.v, right: card.classes.right.v === 'none' ? '' : card.classes.right.v,
                opportunity: card.classes.opportunity.v, scores: Object.fromEntries(Object.entries(card.scores).map(([a, b]) => [a, b.v])) };
    return CASES.cases.filter(c => c.id !== card.caseId).map(c => ({ c, s: similar(q, c), o: outcome(c) })).filter(x => x.s).sort((a, b) => b.s.sim - a.s.sim).slice(0, k || 5);
  }
  const ANALOG_TIP = T('按需求来源、资产权利、机会类型和 M / E / V / D 找最像的历史案例（括号里是真正比上的项数，越少越不可靠）。历史对照不是预测：样本 25 个、大多是后来成功的项目，案例分数是事后回溯打的。',
    'Closest historical cases by demand source, asset right, opportunity type and M / E / V / D (brackets: dimensions actually compared). Not a forecast: 25 mostly successful cases with retrospective scores.');
  function analogTable(sims) {
    return `<div class="tw"><table><thead><tr><th class="l">${T('案例', 'Case')}</th><th>${T('相似', 'Sim')}</th><th>${T('估值峰值', 'Peak val.')}</th><th>${T('首周后倍数', '×wk-1')}</th><th>${T('到峰', 'To peak')}</th></tr></thead><tbody>
      ${sims.map(x => `<tr class="go" data-case="${x.c.id}"><td class="l">${esc(x.c.name)}${x.c.control ? ` <span class="tag ctl">${T('对照', 'control')}</span>` : ''}</td><td>${Math.round(x.s.sim * 100)}% <span class="muted">(${x.s.n})</span></td><td>${x.o.tok ? usd(x.o.tok.val_peak) : '—'}</td><td>${x.o.tok ? mx(x.o.tok.mult_p7) : '—'}</td><td>${x.o.tok ? dd(x.o.tok.days_to_peak) : '—'}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function scoreTable(card, grp, max) {
    const g = FW.scores[grp];
    return `<div class="tw"><table><tbody>${g.items.filter(i => !i.private).map(it => { const s = card.scores[it.k] || {}; const v = s.v; const known = v !== 'U' && v !== 'NA' && v != null && v !== '';
      return `<tr><td class="l" style="width:34%"><b>${it.k}</b> ${esc(it.name)}<div class="small muted">${esc(it.q || '')}</div></td><td style="width:44px">${known ? `<b>${v}</b><span class="muted">/${max}</span>` : `<span class="muted">${v === 'NA' ? 'NA' : 'U'}</span>`}</td><td class="l small wrapc">${known ? esc(it.anchors[v]) : `<span class="muted">${v === 'NA' ? T('不适用', 'n/a') : T('待研究补证', 'pending research')}</span>`}${s.why ? `<div class="muted">${esc(s.why)}</div>` : ''}</td><td class="l" style="width:52px">${srcTag(s.src)}</td></tr>`; }).join('')}</tbody></table></div>`;
  }
  function classRows(card) {
    const A = Object.fromEntries(FW.classes.attribute.opts.map(o => [o.k, o.name]));
    return `<dl class="ax-dl">${[['business', BIZ(), T('需求来源', 'Demand')], ['right', RIGHT(), T('资产权利', 'Right')], ['opportunity', OPP(), T('机会类型', 'Opportunity')], ['attribute', A, T('研究属性', 'Attribute')]]
      .map(([k, m, l]) => { const c = card.classes[k] || {}; return `<dt>${l}</dt><dd>${esc(m[c.v] || (c.v === 'U' ? T('尚未判明', 'unknown') : c.v || '—'))} ${srcTag(c.src)}${c.why ? ` <span class="muted">${esc(c.why)}</span>` : ''}</dd>`; }).join('')}</dl>`;
  }
  function rangeRows(w) {
    const rng = (arr, fmt) => { const v = arr.filter(x => x != null && isFinite(x)).sort((a, b) => a - b); return v.length ? `${fmt(v[0])} · <b>${fmt(med(v))}</b> · ${fmt(v[v.length - 1])}` : '—'; };
    return `<dl class="ax-dl"><dt>${T('估值峰值', 'Peak val.')}</dt><dd>${rng(w.map(x => x.o.tok.val_peak), usd)}</dd><dt>${T('首周后倍数', '×wk-1')}</dt><dd>${rng(w.map(x => x.o.tok.mult_p7), mx)}</dd>
      <dt>${T('相对 BTC', 'vs BTC')}</dt><dd>${rng(w.map(x => x.o.tok.rel_btc_peak_p7), mx)}</dd><dt>${T('到峰天数', 'To peak')}</dt><dd>${rng(w.map(x => x.o.tok.days_to_peak), v => Math.round(v))}</dd>
      <dt>${T('一年内 ≥2× 天数', '≥2× days yr-1')}</dt><dd>${rng(w.map(x => x.o.tok.days_ge2x_365), v => Math.round(v))}</dd></dl>`;
  }
  function monitorPlanes(card) {
    const want = new Set(['mech', 'safety', 'data']);
    if (['cashflow', 'governance'].includes(card.classes.right.v)) want.add('capture');
    if (card.classes.opportunity.v === 'genesis') want.add('reflexive');
    if (card.classes.right.v !== 'none') { want.add('supply'); want.add('structure'); }
    return FW.monitor.planes.filter(p => want.has(p.k)).map(p => `<p class="small"><b>${esc(p.name)}</b> · ${T('触发：', 'Trigger: ')}${esc(p.trigger)}<br><span class="muted">${T('输出：', 'Output: ')}${esc(p.out)}</span></p>`).join('') + `<p class="small muted">${esc(FW.monitor.rule)}</p>`;
  }
  function valuationRows(card) {
    const rt = FW.classes.right.opts.find(o => o.k === card.classes.right.v);
    const bizVal = { trading: 'trading', realworld: 'payment', infra: 'resource' }[card.classes.business.v];
    return FW.valuation.rows.filter(r => (rt && r.k === rt.val) || r.k === bizVal);
  }

  /* ====================================================================== 机会看板：左列表 + 右详情 */
  let BF = 'invest', SELID = null, OPPS = null;
  const DONE = ['研究观察', '优先研究'];
  function oneLiner(o) {
    return o.one_liner || [BIZ()[o.classes.business.v], o.data.category, (o.data.chains || []).slice(0, 2).join(' · ')].filter(Boolean).join(' · ');
  }
  function boardList() {
    const os = OPPS.opps;
    const pool = BF === 'all' ? os.filter(o => o.bucket !== 'reject') : os.filter(o => o.bucket === BF);
    const fresh = pool.filter(o => o.fresh), rest = pool.filter(o => !o.fresh);
    const groups = [[T('新发现 · 3 天内', 'New · last 3 days'), fresh], [T('已补证', 'Researched'), rest.filter(o => DONE.includes(o.status))], [T('待补证', 'Pending research'), rest.filter(o => !DONE.includes(o.status))]];
    const row = o => { const d = o.data; const v = d.rev30 != null ? d.rev30 : d.tvl;
      return `<button type="button" class="md-row${o.id === SELID ? ' on' : ''}" data-id="${esc(o.id)}">
        <span class="r1"><span class="nm">${logo(d.logo, o.name, 20)}<b>${esc(o.name)}</b></span><i class="dot t-${STC[o.status] || 'neutral'}" title="${esc(o.status)}"></i></span>
        <span class="r2"><span>${d.rev30 != null ? usd(v) : (v ? 'TVL ' + usd(v) : '—')} ${pct(d.chg30)}</span>${sparkSvg(o.spark, (d.chg30 || 0) >= 0 ? 'up' : 'dn', 64, 18)}</span>
        <span class="r3">${o.entry.filter(e => e !== 'none').map(e => esc(ENTRY()[e])).join(' · ') || `<span class="muted">${T('暂无资金入口', 'No entry yet')}</span>`}</span></button>`; };
    return `<div class="fg md-filter">${[['invest', T('可投资', 'Investable')], ['watch', T('预警观察', 'Watchlist')], ['all', T('全部', 'All')], ['reject', T('已拒绝', 'Rejected')]]
        .map(([k, l]) => `<button type="button" class="pill${BF === k ? ' on' : ''}" data-bf="${k}">${l}<small>${k === 'all' ? os.filter(o => o.bucket !== 'reject').length : os.filter(o => o.bucket === k).length}</small></button>`).join('')}</div>
      ${groups.filter(g => g[1].length).map(([t, xs]) => `<div class="md-grp">${t}<span>${xs.length}</span></div>${xs.map(row).join('')}`).join('') || `<p class="muted small" style="padding:12px">${T('这一栏暂时没有。', 'Nothing here yet.')}</p>`}`;
  }
  function boardDetail(o) {
    if (!o) return `<div class="card" style="padding:24px" class="muted">${T('左边选一个机会。', 'Pick an opportunity on the left.')}</div>`;
    const d = o.data, R = o.research || {}, iv = cardIntervals(o), En = ENTRY();
    const sims = analogs(o, 5), w = sims.filter(x => x.o.tok);
    const vm = med(w.map(x => x.o.tok.val_peak)), m7 = med(w.map(x => x.o.tok.mult_p7));
    const gatesOpen = FW.gates.items.filter(x => !x.private && (o.gates[x.k] || {}).v !== '通过').map(x => `${x.name}：${(o.gates[x.k] || {}).v || 'U'}`);
    const list = (OPPS.opps.filter(x => BF === 'all' ? x.bucket !== 'reject' : x.bucket === BF));
    const idx = list.findIndex(x => x.id === o.id);
    let h = `<div class="md-nav"><button type="button" class="pill" data-nav="back">← ${T('列表', 'List')}</button><span class="muted small">${idx + 1} / ${list.length}</span><button type="button" class="pill" data-nav="-1">${T('上一个', 'Prev')}</button><button type="button" class="pill" data-nav="1">${T('下一个', 'Next')}</button></div>`;
    h += `<div class="glass ax-head"><div class="ax-title">${logo(d.logo, o.name, 34)}<h2>${esc(o.name)}</h2>${chip(o.status, STC[o.status])}${o.fresh ? chip(T('新发现', 'New'), 'up') : ''}<span class="ax-links">${links(d.url, d.twitter, d.slug)}</span></div>
      <p class="ax-one">${esc(oneLiner(o))}</p>
      <div class="ax-entry">${o.entry.map(e => `<span class="ent${e === 'none' ? ' none' : ''}">${esc(En[e] || e)}</span>`).join('')}<span class="muted small">${esc(o.entry_why || '')}</span></div>
      <div class="ax-meta small muted">${T('发现', 'Seen')} ${esc(o.discovered || '—')} · ${o.reviewer === 'claude-auto' ? T('补证：Claude 自动', 'Research: Claude (auto)') : o.reviewer ? T('补证：Codex', 'Research: Codex') : T('还没补证：只有系统按数据打的分', 'Not researched yet: system scores only')}${R.checked_utc ? ' · ' + esc(R.checked_utc.slice(0, 10)) : ''}</div></div>`;
    h += `<div class="grid g4 ax-kpis">
      <div class="glass hero"><div class="k">${d.rev30 != null ? T('30 天协议收入', '30d protocol revenue') : 'TVL'}<span>${d.rev30 != null ? T('环比', 'vs prior') : ''}</span></div><div class="v">${usd(d.rev30 != null ? d.rev30 : d.tvl)}</div><div class="s">${d.rev30 != null ? (d.chg30 == null ? T('前 30 天没有收入', 'no prior revenue') : pct(d.chg30) + T(' 比前 30 天', ' vs prior 30d')) : T('新上架，还没有收入读数', 'new listing, no revenue yet')}</div>${sparkSvg(o.spark, (d.chg30 || 0) >= 0 ? 'up' : 'dn', 200, 30)}</div>
      <div class="glass hero"><div class="k">${T('机制与扩张', 'Mechanism')}${tip(T('新参与机制、可达性、分配公平、独立扩散、价值归属五项，每项 0–4。区间下沿 = 已查清的得分，上沿 = 未知项全按满分；覆盖率 = 查清了几成。', 'Five items 0–4; range low = scored so far, high = unknowns at max.'))}</div><div class="v">${iv.mech.lo}–${iv.mech.hi}</div><div class="s">${T('查清', 'covered')} ${Math.round(iv.mech.cov * 100)}%</div>${meter(iv.mech)}</div>
      <div class="glass hero"><div class="k">${T('当前参与优势', 'Participation')}${tip(T('有效增长、需求独立性、当前窗口三项（个人执行项不公开），每项 0–4。', 'Growth, demand independence, window; 0–4 each.'))}</div><div class="v">${iv.part.lo}–${iv.part.hi}</div><div class="s">${T('查清', 'covered')} ${Math.round(iv.part.cov * 100)}%</div>${meter(iv.part)}</div>
      <div class="glass hero"><div class="k">${T('相近历史案例', 'Closest cases')}${tip(ANALOG_TIP)}</div><div class="v">${w.length ? usd(vm) : '—'}</div><div class="s">${w.length ? T(`估值峰值中位 · ${w.length} 个案例 · 首周后中位 ${mx(m7)}`, `median peak valuation · ${w.length} cases · ${mx(m7)}`) : T('已知维度太少，还找不到可比案例', 'too few known dimensions')}</div></div></div>`;
    h += d.rev30 != null ? `<div class="card ax-chart"><h3>${T('协议收入 · 近 180 天', 'Protocol revenue · last 180 days')}</h3><div data-chart="${esc(JSON.stringify({ v2: true, src: `/data/alpha/rev/${o.id}.json`, fmt: 'usd', series: [{ k: 'rev', n: T('每日协议收入', 'Daily revenue'), c: 's1', area: true }], note: T('DefiLlama dailyRevenue（协议留存的收入，不是持有人所得）。', 'DefiLlama dailyRevenue (protocol-retained, not holder income).') }))}"></div></div>` : '';
    h += `<div class="grid g2" style="margin-top:12px">
      <div class="card ax-box up"><h3>${T('为什么在看', 'Why it is here')}</h3>${R.verdict_reason ? `<p>${esc(R.verdict_reason)}</p>` : `<p class="muted">${T('系统按数据收进来：', 'Added by data rule: ')}${o.kind === 'tokenless' ? T('没发币、近 30 天协议收入达到门槛。', 'tokenless with revenue above threshold.') : T('新上架、TVL 达到门槛。', 'new listing with TVL above threshold.')}</p>`}${R.user_role && R.user_role !== 'U' ? `<p><span class="muted">${T('普通人怎么参与：', 'How to take part: ')}</span>${esc(R.user_role)}</p>` : ''}</div>
      <div class="card ax-box dn"><h3>${T('最大的风险', 'Biggest risk')}</h3>${R.counter && R.counter !== 'U' ? `<p>${esc(R.counter)}</p>` : `<p class="muted">${T('还没研究出最强反方。', 'No counter-argument researched yet.')}</p>`}${gatesOpen.length ? `<p class="small muted">${T('门槛未过：', 'Gates open: ')}${esc(gatesOpen.join('；'))}</p>` : ''}${R.wash_or_subsidy && R.wash_or_subsidy !== 'U' ? `<p class="small muted">${T('刷量 / 补贴：', 'Wash / subsidy: ')}${esc(R.wash_or_subsidy)}</p>` : ''}</div></div>`;
    if (sims.length) h += `<div class="card ax-box" style="margin-top:12px"><h3>${T('最像它的历史案例', 'Closest historical cases')}${tip(ANALOG_TIP)}</h3>${analogTable(sims)}</div>`;
    const vr = valuationRows(o);
    h += `<details class="card ax-more"><summary>${T('完整拆解', 'Full teardown')} <span class="muted small">${T('逐项评分 · 研究字段 · 估值口径 · 证据', 'scores · research · valuation · evidence')}</span></summary>
      <h4>${T('分类', 'Classes')}</h4>${classRows(o)}
      <h4>${esc(FW.scores.mech.name)}</h4>${scoreTable(o, 'mech', 4)}<h4>${esc(FW.scores.part.name)}</h4>${scoreTable(o, 'part', 4)}${FW.scores.invest ? `<h4>${esc(FW.scores.invest.name)}</h4>${scoreTable(o, 'invest', 3)}<p class="small muted">${esc(FW.scores.invest.facts.name)}：${esc(FW.scores.invest.facts.rule)}</p>` : ''}
      ${o.classes.right.v !== 'none' ? `<p class="small muted">${esc(FW.scores.token.name)}：${T('有代币的对象另评七项（0–3），待研究补证。', 'seven token modules (0–3), pending research.')}</p>` : ''}
      <h4>${T('门槛', 'Gates')}</h4>${FW.gates.items.filter(x => !x.private).map(x => { const s = o.gates[x.k] || {}; return `<div class="kv small"><span>${esc(x.name)}</span><span>${esc(s.v || 'U')} ${srcTag(s.src)} <span class="muted">${esc(s.why || '')}</span></span></div>`; }).join('')}
      ${o.research ? `<h4>${T('研究补证', 'Research')}</h4><dl class="ax-dl"><dt>${T('发币表态', 'Token stance')}</dt><dd>${esc(R.token_stance || 'U')}${R.token_stance_src && R.token_stance_src !== 'U' ? ` · <a href="${esc(R.token_stance_src)}" target="_blank" rel="noopener">${T('来源', 'source')}</a>` : ''}</dd>
        <dt>${T('收入归谁', 'Revenue goes to')}</dt><dd>${esc(R.revenue_who || 'U')}</dd><dt>${T('收入口径', 'Revenue method')}</dt><dd>${esc(R.revenue_method || 'U')}</dd></dl>
        ${(R.missing || []).length ? `<p class="small"><b>${T('还没查清', 'Still unknown')}</b></p><ul class="why">${R.missing.map(m => `<li>${esc(m)}</li>`).join('')}</ul>` : ''}` : ''}
      <h4>${T('四个问题（缺一项先查，不能用总分弥补）', 'Four questions')}</h4>${FW.questions.items.map(q => `<p class="small"><b>${esc(q.axis)}</b> · ${esc(q.name)}<br><span class="muted">${esc(q.hint)}</span></p>`).join('')}
      ${w.length ? `<h4>${T('历史对照区间（最低 · 中位 · 最高）', 'Historical ranges (min · median · max)')}</h4>${rangeRows(w)}` : ''}
      <h4>${T('持续监控', 'Monitoring')}</h4>${monitorPlanes(o)}
      <h4>${T('基础数据', 'Data')}</h4><dl class="ax-dl"><dt>${T('类型', 'Kind')}</dt><dd>${o.kind === 'tokenless' ? T('无币协议', 'tokenless protocol') : T('新上架协议', 'new listing')}</dd><dt>DefiLlama ${T('类目', 'category')}</dt><dd>${esc(d.category || '—')}</dd><dt>${T('链', 'Chains')}</dt><dd>${esc((d.chains || []).join(' · ') || '—')}</dd>${(d.children || []).length > 1 ? `<dt>${T('子产品', 'Products')}</dt><dd>${esc(d.children.join('、'))}</dd>` : ''}${d.listed ? `<dt>${T('收录日', 'Listed')}</dt><dd>${esc(d.listed)}</dd>` : ''}${d.tvl ? `<dt>TVL</dt><dd>${usd(d.tvl)}</dd>` : ''}${d.token_seen ? `<dt>${T('发币日', 'Token since')}</dt><dd>${esc(d.token_seen)}</dd>` : ''}<dt>${T('状态来源', 'State from')}</dt><dd>${esc(o.status_src)}</dd></dl>
      <h4>${T('估值该用什么', 'Valuation to use')}</h4>${vr.map(r => `<p class="small"><b>${esc(r.name)}</b> · ${T('用', 'use')}：${esc(r.use)}<br><span class="t-dn">${T('别', 'avoid')}</span>：${esc(r.avoid)}</p>`).join('') || '<p class="small muted">—</p>'}
      ${(o.evidence || []).length ? `<h4>${T('证据', 'Evidence')}</h4><p class="small">${o.evidence.map((e, i) => `<a href="${esc(e.url)}" target="_blank" rel="noopener">${i + 1}</a>`).join(' · ')}</p>` : ''}
      <p class="small muted">${T('框架和打分规则见「框架与方法」。', 'Rules: see Framework.')}</p></details>`;
    return h;
  }
  function renderBoard() {
    const os = OPPS.opps, act = os.filter(o => o.bucket !== 'reject');
    const doneN = act.filter(o => DONE.includes(o.status)).length;
    const freshN = act.filter(o => o.fresh).length;
    const list = () => BF === 'all' ? act : os.filter(o => o.bucket === BF);
    if (!SELID || !os.some(o => o.id === SELID)) SELID = (list()[0] || {}).id;
    const ord = () => { const l = list(); const g = [l.filter(o => o.fresh), l.filter(o => !o.fresh && DONE.includes(o.status)), l.filter(o => !o.fresh && !DONE.includes(o.status))]; return [].concat(...g); };
    app.innerHTML = `<div class="grid g4 ax-top">
        <div class="glass hero"><div class="k">${T('可投资机会', 'Investable')}</div><div class="v t-up">${OPPS.counts.invest || 0}</div><div class="s">${T('资金现在就能参与', 'capital can take part now')}</div></div>
        <div class="glass hero"><div class="k">${T('预警观察', 'Watchlist')}</div><div class="v">${OPPS.counts.watch || 0}</div><div class="s">${T('新东西，暂时没有资金入口', 'no capital entry yet')}</div></div>
        <div class="glass hero"><div class="k">${T('新发现 · 3 天内', 'New · 3 days')}</div><div class="v">${freshN}</div><div class="s">${T('不等补证，先放出来', 'shown before research')}</div></div>
        <div class="glass hero"><div class="k">${T('补证进度', 'Research progress')}${tip(T('每天自动补证一批，顺序：新发现 → 可投资 → 收入高。待补证清单可以下载交给 Codex。', 'Daily research works through the queue; downloadable for Codex.'))}</div><div class="v">${doneN}<span class="muted" style="font-size:15px"> / ${act.length}</span></div><div class="s"><a href="/data/alpha/research_queue.json" download>${T('下载待补证清单', 'Download queue')}</a></div></div></div>
      <div class="md"><aside class="md-list">${boardList()}</aside><section class="md-detail" id="ax-detail">${boardDetail(os.find(o => o.id === SELID))}</section></div>
      <p class="small muted" style="margin-top:12px">${T('数据日', 'Data day')} ${esc(OPPS.asof || '')} · ${T('框架', 'Framework')} ${esc(OPPS.framework)} · ${T('自动规则', 'Rules')} ${esc(OPPS.rules || '')} · <a href="${EN ? '/en' : ''}/alpha/framework/#auto">${T('打分规则', 'Scoring rules')}</a> · ${T('不按分数排名，不是买卖建议', 'no rankings, not trade advice')}</p>
      <details class="card ax-more"><summary>${T('待补证清单（每天自动生成）', 'Research queue (generated daily)')} <span class="muted small">${OPPS.queue_n == null ? '' : OPPS.queue_n + T(' 个', ' items')}</span></summary>
        <p class="small"><a href="/data/alpha/research_queue.json" download>${T('下载 JSON（含给 Codex 的提示词和交付格式）', 'Download JSON (with prompt and schema)')}</a></p>
        <p class="small muted">${T('每天的自动补证会话先补排在最前面的几个；想加快就把这个文件交给 Codex，交回的 <日期>_checks.json 放进 alpha/review/ 就会自动并入。', 'The daily session researches the top items; to go faster hand this file to Codex and drop the returned <date>_checks.json into alpha/review/.')}</p>
        <p class="small muted">${T('已拒绝的卡不删，左上「已拒绝」里能看到保留原因。', 'Rejected cards are kept with reasons under the Rejected filter.')}</p></details>`;
    const sel = (id, push) => {
      SELID = id;
      app.querySelectorAll('.md-row').forEach(b => b.classList.toggle('on', b.dataset.id === id));
      const det = document.getElementById('ax-detail');
      det.innerHTML = boardDetail(os.find(o => o.id === id));
      app.querySelector('.md').classList.add('show');   // 先显示再画图（图表组件只初始化可见的元素）
      if (window.ucBootCharts) window.ucBootCharts(det);
      if (push !== false) history.replaceState(null, '', '#' + encodeURIComponent(id));
    };
    if (window.ucBootCharts) window.ucBootCharts(app);
    app.onclick = e => {
      const f = e.target.closest('[data-bf]');
      if (f) { BF = f.dataset.bf; SELID = (list()[0] || {}).id; renderBoard(); return; }
      const r = e.target.closest('.md-row');
      if (r) { sel(r.dataset.id); if (window.innerWidth < 900) window.scrollTo({ top: app.offsetTop - 60 }); return; }
      const n = e.target.closest('[data-nav]');
      if (n) { if (n.dataset.nav === 'back') { app.querySelector('.md').classList.remove('show'); return; } const l = ord(); const i = l.findIndex(o => o.id === SELID); const x = l[(i + Number(n.dataset.nav) + l.length) % l.length]; if (x) sel(x.id); return; }
      const c = e.target.closest('[data-case]');
      if (c) location.href = `${EN ? '/en' : ''}/alpha/cases/#${c.dataset.case}`;
    };
    document.onkeydown = e => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target.tagName || ''))) return;
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      const l = ord(); const i = l.findIndex(o => o.id === SELID); const x = l[i + (e.key === 'ArrowDown' ? 1 : -1)];
      if (x) { e.preventDefault(); sel(x.id); const b = app.querySelector(`.md-row[data-id="${CSS.escape(x.id)}"]`); if (b) b.scrollIntoView({ block: 'nearest' }); }
    };
  }

  /* ====================================================================== 案例库：同样左列表 + 右详情；量级对照放下面 */
  let CSEL = null, CF = 'all';
  function rowsData() {
    const B = BIZ(); return CASES.cases.map(c => { const o = outcome(c); const t = o.tok || {}; return { c, o, t, name: c.name, biz: B[c.classes.business] || '',
      val: t.val_peak, mult: t.mult, mult7: t.mult_p7, rel: t.rel_btc_peak_p7, tp: t.days_to_peak, d2: t.days_ge2x_365, back: t.days_peak_to_below_p0,
      fee: o.fees && o.fees.peak30, hot: o.fees && !o.fees.late ? o.fees.hot_days : null, tvl: o.tvl && o.tvl.peak, M: c.scores.M, D: c.scores.D, E: c.scores.E, V: c.scores.V }; });
  }
  function groupTable(dim, label) {
    const rs = rowsData().filter(r => !r.c.control);
    const row = l => { const g = rs.filter(r => r[dim] === l); const w = g.filter(r => r.t.sym);
      return `<tr><td class="l"><b>${l}</b> <span class="small muted">${esc((FW.scores.mech.items.concat(FW.scores.part.items).find(i => i.k === dim) || {}).anchors[l] || '')}</span></td><td>${g.length}</td><td>${usd(med(w.map(r => r.val)))}</td><td>${mx(med(w.map(r => r.mult7)))}</td><td>${med(w.map(r => r.tp)) == null ? '—' : Math.round(med(w.map(r => r.tp)))}</td><td class="l small">${g.map(r => esc(r.c.name.split(/[ /]/)[0])).join('、')}</td></tr>`; };
    return `<div class="tw"><table><thead><tr><th class="l">${label}</th><th>${T('案例', 'n')}</th><th>${T('估值峰值中位', 'Median peak val.')}</th><th>${T('首周后倍数中位', 'Median ×wk-1')}</th><th>${T('到峰中位（天）', 'Median to peak')}</th><th class="l">${T('有哪些', 'Which')}</th></tr></thead><tbody>${[0, 1, 2, 3, 4].map(row).join('')}</tbody></table></div>`;
  }
  let SORT = { k: 'val', d: -1 }, FILTER = { business: '', control: 'all' };
  const bars = v => v === 'U' || v == null ? '<span class="muted">U</span>' : `<span class="sc5">${[0, 1, 2, 3].map(i => `<i class="${i < v ? 'f' : ''}"></i>`).join('')}</span> ${v}`;
  function caseTable() {
    let rs = rowsData();
    if (FILTER.business) rs = rs.filter(r => r.c.classes.business === FILTER.business);
    if (FILTER.control === 'main') rs = rs.filter(r => !r.c.control);
    if (FILTER.control === 'ctl') rs = rs.filter(r => r.c.control);
    rs.sort((a, b) => { const x = a[SORT.k], y = b[SORT.k]; if (x == null || x === 'U') return 1; if (y == null || y === 'U') return -1; return typeof x === 'string' ? SORT.d * x.localeCompare(y) : SORT.d * (x - y); });
    const B = BIZ();
    const th = (k, l, cls) => `<th data-s="${k}" class="${cls || ''}">${l}${SORT.k === k ? (SORT.d > 0 ? ' ↑' : ' ↓') : ''}</th>`;
    return `<div class="tw" style="max-height:640px;overflow:auto"><table><thead><tr>${th('name', T('案例', 'Case'), 'l')}${th('biz', T('需求来源', 'Demand'), 'l')}${th('M', T('创新 M', 'Innov. M'))}${th('D', T('需求独立 D', 'Demand D'))}${th('val', T('估值峰值', 'Peak val.'))}${th('mult7', T('首周后倍数', 'From wk-1'))}${th('mult', T('首日倍数', 'From day-1'))}${th('rel', T('相对 BTC', 'vs BTC'))}${th('tp', T('到峰', 'To peak'))}${th('d2', T('≥2× 天', '≥2× days'))}${th('back', T('峰后跌回起点', 'Back below P0'))}${th('fee', T('30 天手续费峰值', 'Peak 30d fees'))}${th('hot', T('热度天数', 'Hot days'))}${th('tvl', T('TVL 峰值', 'Peak TVL'))}</tr></thead><tbody>
      ${rs.map(r => `<tr data-id="${r.c.id}" class="${r.c.control ? 'ctl' : ''}${CSEL === r.c.id ? ' sel' : ''}"><td class="l"><b>${esc(r.c.name)}</b>${r.c.control ? `<span class="tag ctl">${T('对照', 'control')}</span>` : ''}<div class="small muted">${esc(r.c.period)}</div></td>
        <td class="l small">${esc(B[r.c.classes.business] || '')}</td><td>${bars(r.M)}</td><td>${bars(r.D)}</td>
        <td>${usd(r.val)}${r.val != null ? `<div><span class="tier">${esc(tierOf(r.val))}</span></div>` : ''}</td><td><b>${mx(r.mult7)}</b></td><td class="muted">${mx(r.mult)}</td><td>${mx(r.rel)}</td><td>${dd(r.tp)}</td><td>${r.d2 == null ? '—' : r.d2}</td>
        <td>${r.back == null ? (r.t.sym ? T('至今没有', 'never') : '—') : dd(r.back)}</td><td>${usd(r.fee)}${r.o.fees && r.o.fees.late ? `<div class="small muted">${T('覆盖晚', 'late data')}</div>` : ''}</td><td>${r.hot == null ? '—' : r.hot}</td><td>${usd(r.tvl)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function scatter(dim, label) {
    const rs = rowsData().filter(r => r.val != null && r[dim] !== 'U' && r[dim] != null);
    const W = 560, H = 300, L = 54, R = 14, Tp = 12, Bt = 34;
    const ys = rs.map(r => Math.log10(r.val)); const y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys));
    const X = v => L + (W - L - R) * (v + 0.5) / 5, Y = v => Tp + (H - Tp - Bt) * (1 - (v - y0) / (y1 - y0));
    let g = '';
    for (let y = y0; y <= y1; y++) g += `<line class="ax-grid" x1="${L}" x2="${W - R}" y1="${Y(y)}" y2="${Y(y)}"/><text x="${L - 6}" y="${Y(y) + 3}" text-anchor="end">${usd(Math.pow(10, y))}</text>`;
    for (let x = 0; x <= 4; x++) g += `<text x="${X(x)}" y="${H - 14}" text-anchor="middle">${x}</text>`;
    g += `<text x="${(L + W - R) / 2}" y="${H - 1}" text-anchor="middle">${esc(label)}</text>`;
    const seen = {};
    rs.forEach(r => { const k = r[dim]; seen[k] = (seen[k] || 0) + 1; const j = ((seen[k] % 5) - 2) * 9; const cx = X(k) + j, cy = Y(Math.log10(r.val));
      g += `<circle class="pt${r.c.control ? ' ctl' : ''}${CSEL === r.c.id ? ' hi' : ''}" data-id="${r.c.id}" cx="${cx}" cy="${cy}" r="5"><title>${esc(r.c.name)} · ${usd(r.val)}</title></circle><text class="lbl" x="${cx + 7}" y="${cy + 3}">${esc(r.c.name.split(/[ /]/)[0])}</text>`; });
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(label)}">${g}</svg>`;
  }
  function caseCard(c) {
    const S2 = (v, src) => ({ v, src });
    return { caseId: c.id, name: c.name, status: c.control ? T('对照组', 'Control') : T('历史案例', 'Historical'), control: c.control,
      classes: { business: S2(c.classes.business, 'retro'), right: S2(c.classes.right, 'retro'), opportunity: S2(c.classes.opportunity, 'retro'), attribute: S2(c.classes.attribute, 'retro') },
      scores: Object.fromEntries('MAFEVGPDLT'.split('').map(k => [k, S2(c.scores[k] == null ? 'U' : c.scores[k], c.scores[k] == null || c.scores[k] === 'U' ? null : 'retro')])), gates: {} };
  }
  function caseDetail(c) {
    if (!c) return '';
    const o = outcome(c), t = o.tok || {}, card = caseCard(c), iv = cardIntervals(card);
    const toks = (MET.cases[c.id] || {}).tokens || [];
    const B = BIZ(), Rt = RIGHT();
    let h = `<div class="md-nav"><button type="button" class="pill" data-nav="back">← ${T('列表', 'List')}</button></div>
      <div class="glass ax-head"><div class="ax-title">${logo(c.logo, c.name, 34)}<h2>${esc(c.name)}</h2>${c.control ? chip(T('对照组', 'Control'), 'warn') : chip(esc(c.period), 'neutral')}${t.val_peak != null ? chip(tierOf(t.val_peak), 'up') : ''}<span class="ax-links">${links(c.url, null, null)}</span></div>
        <p class="ax-one">${esc(c.change)}</p><div class="ax-meta small muted">${esc(B[c.classes.business] || '')} · ${esc(Rt[c.classes.right] || '')} · ${esc(c.period)} · ${esc(c.src)}</div></div>
      <div class="grid g4 ax-kpis">
        <div class="glass hero"><div class="k">${T('估值峰值', 'Peak valuation')}${tip(t.val_kind || T('供给无上限或有迁移，不算估值', 'no valuation'))}</div><div class="v">${usd(t.val_peak)}</div><div class="s">${t.val_peak_date ? esc(t.val_peak_date) : T('没有价格结果', 'no price data')}</div></div>
        <div class="glass hero"><div class="k">${T('首周后最高倍数', 'Max × from week 1')}${tip(T('从上线第 7 天收盘算到之后最高收盘。第一天的价格普通人基本买不到，所以主看这个；首日倍数另列。', 'From the day-7 close to the later peak close.'))}</div><div class="v t-up">${mx(t.mult_p7)}</div><div class="s">${T('首日起', 'from day 1')} ${mx(t.mult)} · ${T('相对 BTC', 'vs BTC')} ${mx(t.rel_btc_peak_p7)}</div></div>
        <div class="glass hero"><div class="k">${T('多久到顶', 'Time to peak')}</div><div class="v">${dd(t.days_to_peak)}</div><div class="s">${T('峰后跌回起点：', 'Back below P0: ')}${t.sym ? (t.days_peak_to_below_p0 == null ? T('至今没有', 'never') : dd(t.days_peak_to_below_p0)) : '—'}</div></div>
        <div class="glass hero"><div class="k">${T('手续费 30 天峰值', 'Peak 30d fees')}${tip(T('DefiLlama 手续费 30 天滚动合计的峰值；热度天数 = 30 天均值 ≥ 峰值一半的天数。', '30d rolling fees peak; hot days = days at ≥ half the peak.'))}</div><div class="v">${o.fees ? usd(o.fees.peak30) : '—'}</div><div class="s">${o.fees ? (o.fees.late ? T('序列开始太晚，不代表早期', 'series starts late') : T('热度', 'hot') + ' ' + dd(o.fees.hot_days)) : (o.tvl ? 'TVL ' + T('峰值', 'peak') + ' ' + usd(o.tvl.peak) : '—')}</div></div></div>`;
    toks.forEach(x => { h += `<div class="card ax-chart"><h3>${esc(x.sym)} ${T('价格 ÷ 首日价（对数，周线）', 'price ÷ day-1 price (log, weekly)')}</h3><div data-chart="${esc(JSON.stringify({ v2: true, src: `/data/alpha/case/${c.id}_${x.sym}.json`, fmt: 'x', log: true, series: [{ k: 'p', n: x.sym + T(' 倍数', ' multiple'), c: 's1' }] }))}"></div></div>`; });
    if (o.fees && ((SER || {})[c.id] || {}).fees30) h += `<div class="card ax-chart"><h3>${T('30 天滚动手续费（周线）', '30d rolling fees (weekly)')}</h3><div data-chart="${esc(JSON.stringify({ v2: true, src: `/data/alpha/case/${c.id}_fees.json`, fmt: 'usd', series: [{ k: 'f', n: T('手续费', 'Fees'), c: 's2', area: true }] }))}"></div></div>`;
    h += `<div class="grid g2" style="margin-top:12px"><div class="card ax-box up"><h3>${T('当时怎么参与、解决了什么', 'Entry & problem solved')}</h3><p>${esc(c.entry)}</p><p class="muted">${esc(c.problem)}</p></div>
      <div class="card ax-box dn"><h3>${T('教训', 'Lesson')}</h3><p>${esc(c.lesson)}</p>${c.why_control ? `<p class="small muted">${T('为什么是对照：', 'Why control: ')}${esc(c.why_control)}</p>` : ''}${c.note ? `<p class="small muted">${esc(c.note)}</p>` : ''}</div></div>
      <details class="card ax-more"><summary>${T('框架拆解（回溯评分）', 'Framework teardown (retrospective)')} <span class="muted small">${T('机制', 'mech')} ${iv.mech.lo}–${iv.mech.hi} · ${T('参与', 'part')} ${iv.part.lo}–${iv.part.hi}</span></summary>
        <p class="small muted">${esc(CASES.score_basis)}</p><h4>${T('分类', 'Classes')}</h4>${classRows(card)}<h4>${esc(FW.scores.mech.name)}</h4>${scoreTable(card, 'mech', 4)}<h4>${esc(FW.scores.part.name)}</h4>${scoreTable(card, 'part', 4)}
        <h4>${T('结果明细（接口算出）', 'Outcome detail (computed)')}</h4>${toks.length ? toks.map(x => `<dl class="ax-dl"><dt>${esc(x.sym)}</dt><dd>P0 ${esc(x.p0_date)} → ${T('峰值', 'peak')} ${esc(x.peak_date)} · ${T('首日', 'day-1')} ${mx(x.mult)} · ${T('首周后', 'wk-1')} ${mx(x.mult_p7)}</dd>
          <dt>${T('估值口径', 'Valuation')}</dt><dd>${esc(x.val_kind || T('不算估值', 'none'))} ${x.val_peak != null ? usd(x.val_peak) : ''}</dd><dt>${T('相对 BTC', 'vs BTC')}</dt><dd>${T('首日起', 'from day-1')} ${mx(x.rel_btc_peak)} · ${T('首周后', 'wk-1')} ${mx(x.rel_btc_peak_p7)}</dd>
          <dt>${T('一年内 ≥2× 天数', '≥2× days yr-1')}</dt><dd>${x.days_ge2x_365}</dd><dt>${T('峰后跌回起点', 'Back below P0')}</dt><dd>${x.days_peak_to_below_p0 == null ? T('至今没有', 'never') : dd(x.days_peak_to_below_p0)}</dd><dt>${T('价格覆盖率', 'Coverage')}</dt><dd>${Math.round(x.coverage * 100)}%</dd></dl>`).join('') : `<p class="small muted">${T('没有同质化代币或价格源。', 'No fungible token / price source.')}</p>`}
        ${o.fees ? `<p class="small">${T('手续费序列起点', 'Fees series from')} ${esc(o.fees.first)} · ${T('30 天峰值', 'peak 30d')} ${usd(o.fees.peak30)}（${esc(o.fees.peak30_date)}）· ${T('热度天数', 'hot days')} ${o.fees.hot_days}</p>` : ''}${o.tvl ? `<p class="small">TVL ${T('峰值', 'peak')} ${usd(o.tvl.peak)}（${esc(o.tvl.peak_date)}）</p>` : ''}</details>`;
    return h;
  }
  function renderCases() {
    const rs = rowsData().sort((a, b) => (b.val || 0) - (a.val || 0));
    const pool = CF === 'ctl' ? rs.filter(r => r.c.control) : rs;
    if (!CSEL || !rs.some(r => r.c.id === CSEL)) CSEL = (pool[0] || {}).c && pool[0].c.id;
    const nP = rs.filter(r => r.t.sym).length;
    app.innerHTML = `<div class="grid g4 ax-top">
        <div class="glass hero"><div class="k">${T('历史案例', 'Cases')}</div><div class="v">${rs.filter(r => !r.c.control).length}</div><div class="s">${T('从 BTC 到 HYPE', 'from BTC to HYPE')}</div></div>
        <div class="glass hero"><div class="k">${T('对照组', 'Controls')}${tip(T('同期同类、抄机制或撒积分、后来表现差的项目，用来对冲「只看成功者」的偏差。', 'Same-era copies or points farms that did poorly.'))}</div><div class="v">${rs.filter(r => r.c.control).length}</div><div class="s">${T('还在补', 'more coming')}</div></div>
        <div class="glass hero"><div class="k">${T('有价格结果', 'With price outcome')}</div><div class="v">${nP}</div><div class="s">${T('其余是 NFT / 无单一代币', 'others: NFTs / no single token')}</div></div>
        <div class="glass hero"><div class="k">${T('怎么用', 'How to use')}${tip(ANALOG_TIP)}</div><div class="v" style="font-size:15px;line-height:1.5">${T('给新机会做预期管理', 'Expectation management')}</div><div class="s">${T('不是预测，不是目标价', 'not a forecast')}</div></div></div>
      <div class="md"><aside class="md-list"><div class="fg md-filter">${[['all', T('全部', 'All')], ['ctl', T('只看对照组', 'Controls')]].map(([k, l]) => `<button type="button" class="pill${CF === k ? ' on' : ''}" data-cf="${k}">${l}</button>`).join('')}</div>
        ${pool.map(r => `<button type="button" class="md-row${r.c.id === CSEL ? ' on' : ''}" data-id="${r.c.id}"><span class="r1"><span class="nm">${logo(r.c.logo, r.c.name, 20)}<b>${esc(r.c.name)}</b></span>${r.c.control ? `<span class="tag ctl">${T('对照', 'ctl')}</span>` : ''}</span>
          <span class="r2"><span>${r.val != null ? usd(r.val) : '—'}</span><span class="t-up">${r.mult7 != null ? mx(r.mult7) : ''}</span></span><span class="r3">${esc(r.c.period)}</span></button>`).join('')}</aside>
        <section class="md-detail" id="ax-detail">${caseDetail(CASES.cases.find(c => c.id === CSEL))}</section></div>
      <details class="card ax-more" style="margin-top:16px"><summary>${T('创新级别 × 结果量级', 'Innovation level × outcome')} <span class="muted small">${T('不含对照组 · 中位数只描述这批样本', 'controls excluded · medians describe this sample only')}</span></summary>
        <h4>${T('按创新级别 M', 'By innovation M')}</h4>${groupTable('M', 'M')}<h4>${T('按需求独立性 D', 'By demand independence D')}</h4>${groupTable('D', 'D')}
        <div class="grid g2" style="margin-top:12px"><div>${scatter('M', T('创新 M（横）× 估值峰值（纵，对数）', 'Innovation M × peak valuation (log)'))}</div><div>${scatter('D', T('需求独立 D（横）× 估值峰值（纵，对数）', 'Demand D × peak valuation (log)'))}</div></div></details>
      <details class="card ax-more"><summary>${T('全部案例明细表', 'All cases · full table')} <span class="muted small">${T('点表头排序', 'click headers to sort')}</span></summary><div class="fg" style="margin:8px 0"><select class="pill" data-filt="business"><option value="">${T('全部需求来源', 'All demand sources')}</option>${FW.classes.business.opts.map(o => `<option value="${o.k}">${esc(o.name)}</option>`).join('')}</select><select class="pill" data-filt="control"><option value="all">${T('含对照组', 'Incl. controls')}</option><option value="main">${T('不含对照组', 'Excl. controls')}</option><option value="ctl">${T('只看对照组', 'Controls only')}</option></select></div><div id="ax-table">${caseTable()}</div>
        <h4>${T('口径', 'Definitions')}</h4>${FW.outcomes.dims.map(d => `<p class="small"><b>${esc(d.name)}</b>：${esc(d.how)}</p>`).join('')}<ul class="why">${FW.outcomes.caveats.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
        <p class="small muted">${T('结果数据生成于', 'Outcome data generated')} ${esc((MET.generated || '').slice(0, 10))}</p></details>`;
    if (window.ucBootCharts) window.ucBootCharts(app);
    app.querySelectorAll('select[data-filt]').forEach(el => { el.value = FILTER[el.dataset.filt]; el.onchange = () => { FILTER[el.dataset.filt] = el.value; document.getElementById('ax-table').innerHTML = caseTable(); }; });
    app.onclick = e => {
      const so = e.target.closest('th[data-s]');
      if (so) { const k = so.dataset.s; SORT = { k, d: SORT.k === k ? -SORT.d : -1 }; document.getElementById('ax-table').innerHTML = caseTable(); return; }
      const pt = e.target.closest('circle[data-id], #ax-table tr[data-id]');
      if (pt) { CSEL = pt.dataset.id; renderCases(); document.getElementById('ax-detail').scrollIntoView({ block: 'start' }); return; }
      const f = e.target.closest('[data-cf]');
      if (f) { CF = f.dataset.cf; CSEL = null; renderCases(); return; }
      const r = e.target.closest('.md-row');
      if (r) { CSEL = r.dataset.id; history.replaceState(null, '', '#' + CSEL); app.querySelectorAll('.md-row').forEach(b => b.classList.toggle('on', b.dataset.id === CSEL));
        const det = document.getElementById('ax-detail'); det.innerHTML = caseDetail(CASES.cases.find(c => c.id === CSEL)); app.querySelector('.md').classList.add('show'); if (window.ucBootCharts) window.ucBootCharts(det); return; }
      const n = e.target.closest('[data-nav="back"]');
      if (n) app.querySelector('.md').classList.remove('show');
    };
  }

  const need = [J('/data/alpha/framework.json'), J('/data/alpha/cases.json'), J('/data/alpha/case_metrics.json'), MODE === 'cases' ? J('/data/alpha/case_series.json') : Promise.resolve({}),
    MODE === 'board' ? J('/data/alpha/opps.json') : Promise.resolve(null)];
  Promise.all(need).then(([fw, cs, met, ser, opps]) => {
    FW = fw; CASES = cs; MET = met; SER = ser;
    const h = decodeURIComponent((location.hash || '').slice(1));
    if (MODE === 'eval') initEval();
    else if (MODE === 'board') { OPPS = opps; const o = opps.opps.find(x => x.id === h); if (o) { SELID = h; BF = o.bucket === 'reject' ? 'reject' : o.bucket; } renderBoard(); }
    else { if (h && cs.cases.some(c => c.id === h)) CSEL = h; renderCases(); }
  }).catch(err => { app.innerHTML = `<div class="note">${T('数据加载失败：', 'Failed to load: ')}${esc(err.message)}</div>`; });
})();
