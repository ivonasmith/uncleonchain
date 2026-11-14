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
    if (w < 8) return null;   // 至少两类信息才比较
    return { sim: 1 - d / w, n: used.length };
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
    const pend = [];
    if (G.safety !== '通过') pend.push(T('安全门槛未通过', 'safety gate open'));
    if (G.data !== '通过') pend.push(T('数据门槛未通过', 'data gate open'));
    const qs = FW.questions.items.filter(q => (S.q || {})[q.k] !== '已证实').map(q => q.axis);
    if (pend.length || !(S.six || {}).falsify) return { st: T('待核验', 'To verify'), cls: 'wait', why: why.concat(pend, qs.length ? [T('四问未证实：', 'Open questions: ') + qs.join('、')] : []) };
    return { st: T('研究观察', 'Watching'), cls: 'ok', why: [T('对象明确、有可证伪路径、门槛无否决（四.1）。要升「优先研究」需要出现独立证据改善且窗口有时效，由研究者判断。', 'Clear object, falsifiable path, no veto (4.1). Promotion to priority needs independent new evidence and a time-bound window.')].concat(qs.length ? [T('仍未证实：', 'Still open: ') + qs.join('、')] : []) };
  }

  function renderPanel() {
    const f = FW, sc = f.scores;
    const iv = {
      mech: interval(sc.mech.items.map(i => S.scores[i.k] === '' ? 'U' : S.scores[i.k]), 4),
      part: interval(sc.part.items.map(i => S.scores[i.k] === '' ? 'U' : S.scores[i.k]), 4),
      token: S.right === 'none' ? null : interval(sc.token.items.map(i => S.token[i.k] == null || S.token[i.k] === '' ? 'U' : S.token[i.k]), 3),
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
    h += `<div class="card" style="margin-top:12px"><b>${esc(sc.mech.name)}</b>${bar(iv.mech)}<b style="display:block;margin-top:8px">${esc(sc.part.name)}</b>${bar(iv.part)}<b style="display:block;margin-top:8px">${esc(sc.token.name)}</b>${bar(iv.token)}
      <p class="small muted" style="margin:8px 0 0">${esc(sc.formula.interval)}</p>
      <p class="small" style="margin:6px 0 0">${promo.length ? T('达到工作阈值：', 'Meets working threshold: ') + promo.map(esc).join('、') : T('未达到任何晋级工作阈值', 'Below all working thresholds')} <span class="muted">（${esc(sc.promote[0].note)}）</span></p></div>`;
    h += `<div class="card" style="margin-top:12px"><b>${T('估值该用什么', 'Valuation to use')}</b> <span class="muted small">${esc(f.valuation.sec)}</span>
      ${cc ? `<p class="small" style="margin:6px 0">${esc(cc.name)} → ${esc(cc.then)}</p>` : ''}
      ${vrows.length ? vrows.map(r => `<p class="small" style="margin:6px 0"><b>${esc(r.name)}</b><br>${T('用：', 'Use: ')}${esc(r.use)}<br><span style="color:var(--dn)">${T('别：', 'Avoid: ')}</span>${esc(r.avoid)}</p>`).join('') : `<p class="small muted">${T('先选需求来源和资产权利', 'Pick demand source and asset right first')}</p>`}</div>`;
    h += `<div class="card" style="margin-top:12px"><b>${T('历史量级对照（预期管理）', 'Historical analogs (expectation management)')}</b>
      ${sims.length ? `<div class="tw" style="margin-top:8px"><table><thead><tr><th class="l">${T('最相近的案例', 'Closest cases')}</th><th>${T('相似', 'Sim')}</th><th>${T('估值峰值', 'Peak val.')}</th><th>${T('首周后倍数', 'From wk-1')}</th><th>${T('到峰', 'To peak')}</th></tr></thead><tbody>
        ${sims.map(x => `<tr><td class="l">${esc(x.c.name)}${x.c.control ? `<span class="tag ctl">${T('对照', 'control')}</span>` : ''}</td><td>${Math.round(x.s.sim * 100)}%</td><td>${x.o.tok ? usd(x.o.tok.val_peak) : '—'}</td><td>${x.o.tok ? mx(x.o.tok.mult_p7) : '—'}</td><td>${x.o.tok ? dd(x.o.tok.days_to_peak) : '—'}</td></tr>`).join('')}</tbody></table></div>
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

  /* ====================================================================== 案例库 */
  let SORT = { k: 'val', d: -1 }, SEL = null, FILTER = { business: '', control: 'all' };
  function rowsData() {
    return CASES.cases.map(c => { const o = outcome(c); const t = o.tok || {}; return { c, o, t,
      val: t.val_peak, mult: t.mult, mult7: t.mult_p7, rel: t.rel_btc_peak_p7, tp: t.days_to_peak, d2: t.days_ge2x_365, back: t.days_peak_to_below_p0,
      fee: o.fees && o.fees.peak30, hot: o.fees && !o.fees.late ? o.fees.hot_days : null, tvl: o.tvl && o.tvl.peak, M: c.scores.M, D: c.scores.D, E: c.scores.E, V: c.scores.V }; });
  }
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
      ${rs.map(r => `<tr data-id="${r.c.id}" class="${r.c.control ? 'ctl' : ''}${SEL === r.c.id ? ' sel' : ''}"><td class="l"><b>${esc(r.c.name)}</b>${r.c.control ? `<span class="tag ctl">${T('对照', 'control')}</span>` : ''}<div class="small muted">${esc(r.c.period)}</div></td>
        <td class="l small">${esc(B[r.c.classes.business] || '')}</td><td>${bars(r.M)}</td><td>${bars(r.D)}</td>
        <td>${usd(r.val)}${r.val != null ? `<div><span class="tier">${esc(tierOf(r.val))}</span></div>` : ''}</td><td><b>${mx(r.mult7)}</b></td><td class="muted">${mx(r.mult)}</td><td>${mx(r.rel)}</td><td>${dd(r.tp)}</td><td>${r.d2 == null ? '—' : r.d2}</td>
        <td>${r.back == null ? (r.t.sym ? T('至今没有', 'never') : '—') : dd(r.back)}</td><td>${usd(r.fee)}${r.o.fees && r.o.fees.late ? `<div class="small muted">${T('覆盖晚', 'late data')}</div>` : ''}</td><td>${r.hot == null ? '—' : r.hot}</td><td>${usd(r.tvl)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function groupTable(dim, label) {
    const rs = rowsData().filter(r => !r.c.control);
    const lv = [0, 1, 2, 3, 4];
    const row = l => { const g = rs.filter(r => r[dim] === l); const w = g.filter(r => r.t.sym);
      return `<tr><td class="l"><b>${l}</b> <span class="small muted">${esc((FW.scores.mech.items.concat(FW.scores.part.items).find(i => i.k === dim) || {}).anchors[l] || '')}</span></td><td>${g.length}</td><td>${w.length}</td><td>${usd(med(w.map(r => r.val)))}</td><td>${mx(med(w.map(r => r.mult7)))}</td><td>${mx(med(w.map(r => r.rel)))}</td><td>${med(w.map(r => r.tp)) == null ? '—' : Math.round(med(w.map(r => r.tp)))}</td><td>${med(w.map(r => r.d2)) == null ? '—' : Math.round(med(w.map(r => r.d2)))}</td><td class="l small">${g.map(r => esc(r.c.name.split(' ')[0])).join('、')}</td></tr>`; };
    return `<div class="tw"><table><thead><tr><th class="l">${label}</th><th>${T('案例', 'Cases')}</th><th>${T('有价格', 'Priced')}</th><th>${T('估值峰值中位', 'Median peak val.')}</th><th>${T('首周后倍数中位', 'Median ×wk-1')}</th><th>${T('相对 BTC 中位', 'Median vs BTC')}</th><th>${T('到峰中位（天）', 'Median to peak')}</th><th>${T('≥2× 天数中位', 'Median ≥2× days')}</th><th class="l">${T('有哪些', 'Which')}</th></tr></thead><tbody>${lv.map(row).join('')}</tbody></table></div>`;
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
      g += `<circle class="pt${r.c.control ? ' ctl' : ''}${SEL === r.c.id ? ' hi' : ''}" data-id="${r.c.id}" cx="${cx}" cy="${cy}" r="5"><title>${esc(r.c.name)} · ${usd(r.val)}</title></circle><text class="lbl" x="${cx + 7}" y="${cy + 3}">${esc(r.c.name.split(/[ /]/)[0])}</text>`; });
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(label)}">${g}</svg>`;
  }
  function lineChart(pts, label, logScale, cls) {
    if (!pts || pts.length < 3) return `<p class="small muted">${T('没有序列数据', 'No series')}</p>`;
    const W = 560, H = 180, L = 50, R = 10, Tp = 10, Bt = 22;
    const vals = pts.map(p => p[1]).filter(v => v > 0);
    const f = v => logScale ? Math.log10(Math.max(v, 1e-9)) : v;
    let lo = Math.min(...vals.map(f)), hi = Math.max(...vals.map(f)); if (hi === lo) hi = lo + 1;
    const X = i => L + (W - L - R) * i / (pts.length - 1), Y = v => Tp + (H - Tp - Bt) * (1 - (f(v) - lo) / (hi - lo));
    let g = '';
    const ticks = logScale ? Array.from({ length: Math.floor(hi) - Math.ceil(lo) + 1 }, (_, i) => Math.ceil(lo) + i) : [lo, (lo + hi) / 2, hi];
    ticks.forEach(t => { const v = logScale ? Math.pow(10, t) : t; const y = Y(v); g += `<line class="ax-grid" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/><text x="${L - 5}" y="${y + 3}" text-anchor="end">${logScale ? mx(v) : usd(v)}</text>`; });
    g += `<text x="${L}" y="${H - 4}">${esc(pts[0][0])}</text><text x="${W - R}" y="${H - 4}" text-anchor="end">${esc(pts[pts.length - 1][0])}</text>`;
    g += `<polyline class="${cls || 'ln'}" points="${pts.filter(p => p[1] > 0).map((p, i) => `${X(pts.indexOf(p)).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ')}"/>`;
    return `<div class="small muted">${esc(label)}</div><svg viewBox="0 0 ${W} ${H}" width="100%">${g}</svg>`;
  }
  function detail(id) {
    const c = CASES.cases.find(x => x.id === id); if (!c) return '';
    const o = outcome(c); const s = (SER || {})[id] || {};
    const B = BIZ(), Rt = RIGHT(), Op = OPP();
    const toks = ((MET.cases[id] || {}).tokens || []);
    return `<div class="card detail"><h3>${esc(c.name)} ${c.control ? `<span class="tag ctl">${T('对照组', 'control')}</span>` : ''}</h3><div class="small muted">${esc(c.period)} · ${esc(c.src)}</div>
      <dl><dt>${T('当时入口', 'Entry')}</dt><dd>${esc(c.entry)}</dd><dt>${T('变化 / 创新', 'Change')}</dt><dd>${esc(c.change)}</dd><dt>${T('解决的问题', 'Problem')}</dt><dd>${esc(c.problem)}</dd>
      <dt>${T('分类', 'Classes')}</dt><dd>${esc(B[c.classes.business])} · ${esc(Rt[c.classes.right])} · ${esc(Op[c.classes.opportunity])}</dd>
      <dt>${T('回溯评分', 'Retro scores')}</dt><dd>${'MAFEVD'.split('').map(k => `${k} <b>${c.scores[k]}</b>`).join(' · ')}</dd>
      <dt>${T('教训', 'Lesson')}</dt><dd>${esc(c.lesson)}</dd>${c.why_control ? `<dt>${T('为什么是对照', 'Why control')}</dt><dd>${esc(c.why_control)}</dd>` : ''}${c.note ? `<dt>${T('数据注意', 'Data note')}</dt><dd>${esc(c.note)}</dd>` : ''}</dl>
      ${toks.map(t => `<div class="kv"><span>${esc(t.sym)} · P0 ${esc(t.p0_date)}（${T('首日', 'day 1')}）→ ${T('峰值', 'peak')} ${esc(t.peak_date)}</span><b>${mx(t.mult)} / ${T('首周后', 'wk-1')} ${mx(t.mult_p7)}</b></div>
        <div class="kv small"><span>${esc(t.val_kind || T('不算估值（供给无上限或有迁移）', 'no valuation (uncapped / migrated supply)'))}</span><b>${usd(t.val_peak)}</b></div>
        <div class="kv small"><span>${T('价格覆盖率', 'Price coverage')}</span><b>${Math.round(t.coverage * 100)}%</b></div>`).join('')}
      ${o.fees ? `<div class="kv small"><span>${T('30 天手续费峰值', 'Peak 30d fees')} ${esc(o.fees.peak30_date)} · ${T('序列起点', 'series from')} ${esc(o.fees.first)}</span><b>${usd(o.fees.peak30)}</b></div>` : ''}
      ${o.tvl ? `<div class="kv small"><span>TVL ${T('峰值', 'peak')} ${esc(o.tvl.peak_date)}</span><b>${usd(o.tvl.peak)}</b></div>` : ''}
      ${Object.entries(s.tokens || {}).map(([sym, pts]) => lineChart(pts, sym + T(' 价格 ÷ P0（对数，周线）', ' price ÷ P0 (log, weekly)'), true)).join('')}
      ${s.fees30 && s.fees30.length ? lineChart(s.fees30, T('30 天滚动手续费（周线）', '30d rolling fees (weekly)'), false, 'ln2') : ''}
      <p class="small"><a href="${EN ? '/en' : ''}/alpha/eval/" data-load="${c.id}">${T('在评估器里打开这个案例 →', 'Open in the evaluator →')}</a></p></div>`;
  }
  function renderCases() {
    const B = BIZ();
    const f = FW.outcomes;
    app.innerHTML = `<div class="cav"><b>${T('先读这几条', 'Read first')}</b><ul style="margin:4px 0 0;padding-left:18px">${f.caveats.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
      <h2>${T('创新级别 × 结果量级', 'Innovation level × outcome')} <span class="sub">${T('不含对照组', 'controls excluded')}</span></h2>
      <p class="small muted">${T('M = 新参与机制（附录一 B 锚点）；D = 需求独立性（谁持续付款，附录一 C）。中位数只描述这批样本，不是概率。', 'M = new mechanism; D = demand independence. Medians describe this sample only.')}</p>
      ${groupTable('M', T('创新 M', 'Innovation M'))}<div style="height:10px"></div>${groupTable('D', T('需求独立 D', 'Demand D'))}
      <div class="grid2" style="margin-top:14px"><div class="card">${scatter('M', T('创新 M（横）× 估值峰值（纵，对数）', 'Innovation M × peak valuation (log)'))}</div><div class="card">${scatter('D', T('需求独立 D（横）× 估值峰值（纵，对数）', 'Demand D × peak valuation (log)'))}</div></div>
      <h2>${T('全部案例', 'All cases')} <span class="sub">${CASES.cases.length} · ${T('点表头排序，点一行看详情', 'click headers to sort, rows for detail')}</span></h2>
      <div class="btns"><select id="ax-fb"><option value="">${T('全部需求来源', 'All demand sources')}</option>${Object.entries(B).map(([k, v]) => `<option value="${k}"${FILTER.business === k ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select>
        <select id="ax-fc"><option value="all">${T('含对照组', 'Incl. controls')}</option><option value="main"${FILTER.control === 'main' ? ' selected' : ''}>${T('只看案例', 'Cases only')}</option><option value="ctl"${FILTER.control === 'ctl' ? ' selected' : ''}>${T('只看对照组', 'Controls only')}</option></select></div>
      <div class="grid2"><div id="ax-table">${caseTable()}</div><div class="sticky" id="ax-detail">${SEL ? detail(SEL) : `<div class="card small muted">${T('点左边任意一行看详情、价格和手续费走势。', 'Click a row for details and charts.')}</div>`}</div></div>
      <h2>${T('口径', 'Definitions')}</h2><div class="card small">${f.dims.map(d => `<p style="margin:4px 0"><b>${esc(d.name)}</b>：${esc(d.how)}</p>`).join('')}<p style="margin:4px 0"><b>${T('评分口径', 'Scoring basis')}</b>：${esc(CASES.score_basis)}</p><p class="muted" style="margin:4px 0">${T('结果数据生成于', 'Outcome data generated')} ${esc((MET.generated || '').slice(0, 10))}</p></div>`;
    app.onclick = e => {
      const s = e.target.closest('th[data-s]');
      if (s) { const k = s.dataset.s; SORT = { k, d: SORT.k === k ? -SORT.d : -1 }; document.getElementById('ax-table').innerHTML = caseTable(); return; }
      const r = e.target.closest('tr[data-id], circle[data-id]');
      if (r) { SEL = r.dataset.id; renderCases(); document.getElementById('ax-detail').scrollIntoView({ block: 'nearest' }); return; }
      const l = e.target.closest('a[data-load]');
      if (l) { const c = CASES.cases.find(x => x.id === l.dataset.load); const st = blank(); Object.assign(st, { name: c.name, asof: c.period, business: c.classes.business, right: c.classes.right, opportunity: c.classes.opportunity, attribute: c.classes.attribute }); for (const k of 'MAFEVD') st.scores[k] = c.scores[k]; try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (err) { /* 忽略 */ } }
    };
    app.onchange = e => { if (e.target.id === 'ax-fb') { FILTER.business = e.target.value; document.getElementById('ax-table').innerHTML = caseTable(); } if (e.target.id === 'ax-fc') { FILTER.control = e.target.value; document.getElementById('ax-table').innerHTML = caseTable(); } };
  }

  Promise.all([J('/data/alpha/framework.json'), J('/data/alpha/cases.json'), J('/data/alpha/case_metrics.json'), MODE === 'cases' ? J('/data/alpha/case_series.json') : Promise.resolve({})])
    .then(([fw, cs, met, ser]) => { FW = fw; CASES = cs; MET = met; SER = ser; if (MODE === 'eval') initEval(); else renderCases(); })
    .catch(err => { app.innerHTML = `<div class="note">${T('数据加载失败：', 'Failed to load: ')}${esc(err.message)}</div>`; });
})();
