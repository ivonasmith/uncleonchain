/* 核心选币观测台（/core/）：大叔 2026-11-14 交付的原型 obs.html 拆过来，取数改读 /data/core/*.json，颜色改站点变量，加中英文。
   规则判定 / 评分全部【假设】，只做条件检查与风险提示，不是买卖建议。数据由 core/core_daily.py 每天生成。 */
(function(){
'use strict';
const root=document.getElementById('core'); if(!root)return;
const EN=(document.documentElement.lang||'').startsWith('en');
const L=(zh,en)=>EN?en:zh;
const $=s=>root.querySelector(s);
const nz=x=>x!==null&&x!==undefined&&!Number.isNaN(x);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtU=(x,d=2)=>!nz(x)?'—':(Math.abs(x)>=1e9?(x/1e9).toFixed(d)+'B':Math.abs(x)>=1e6?(x/1e6).toFixed(d)+'M':Math.abs(x)>=1e3?(x/1e3).toFixed(1)+'K':x.toFixed(2));
const fmtP=(x,d=1)=>!nz(x)?'—':((x>0?'+':'')+x.toFixed(d)+'%');
const cls=x=>!nz(x)?'':(x>0?'pos':x<0?'neg':'');
const fmtPx=x=>!nz(x)?'—':(x>=100?x.toFixed(2):x>=1?x.toFixed(3):x>=0.01?x.toFixed(4):x.toPrecision(3));
const fmtX=x=>!nz(x)?'—':(x>=1000?Math.round(x)+'x':x.toFixed(1)+'x');
const stat=(k,t)=>`<span class="st ${k}"><i>${{good:'✓',warn:'!',serious:'!',crit:'✕',na:'?'}[k]}</i><span>${t}</span></span>`;
const TREND_EN={'多头排列（MA20、MA50 上方）':'Uptrend (above MA20 & MA50)','修复中（站上 MA20、MA50，均线未金叉）':'Repairing (above MA20 & MA50, no golden cross yet)',
 '趋势已破（MA20、MA50 下方）':'Trend broken (below MA20 & MA50)','回调（跌破 MA20，守在 MA50 上方）':'Pullback (below MA20, above MA50)','反弹（站上 MA20，仍在 MA50 下方）':'Bounce (above MA20, below MA50)','历史不足':'Not enough history'};
const trend=t=>EN?(TREND_EN[t]||t):t;
const TIER={T1:L('T1 已执行回购 / 销毁','T1 buyback / burn live'),T2:L('T2 有机制 / 口径待核','T2 mechanism, to verify'),T3:L('T3 计划 / 治理中','T3 planned / in governance'),W:L('观察（叙事 / 赛道）','Watch (narrative / sector)')};
const src=root.dataset.src, sdir=root.dataset.series, hsrc=root.dataset.hist, HOME=root.dataset.home||'';
let D,C,SYMS,MAN,GT,HIST=null;

/* ---------- 规则判定（原型同一套，闸门 1 / 3 改读本站 L2 与 L1 数据） ---------- */
function gates(){
  const r=[]; const g=GT||{};
  if(g.l2&&g.l2.code)r.push({id:L('闸门1','Gate 1'),t:L('L2 周期在熊底区或熊末→牛初','L2 cycle in bear-bottom zone or late bear → early bull'),k:g.l2.ok?'good':'crit',x:`${EN?g.l2.name_en:g.l2.name_zh}（${L('自','since')} ${g.l2.since}）`});
  else r.push({id:L('闸门1','Gate 1'),t:L('L2 周期在熊底区或熊末→牛初','L2 cycle state'),k:'na',x:L('L2 数据未取到','L2 data missing')});
  const fl=(MAN&&MAN.btc_floor)||58525, ok=D.btc.last>fl;
  r.push({id:L('闸门2','Gate 2'),t:L(`BTC 收盘 > ${fl.toLocaleString()}（本轮最低收盘）`,`BTC close > ${fl.toLocaleString()} (cycle-low close)`),k:ok?'good':'crit',x:`BTC ${Math.round(D.btc.last).toLocaleString()}（${D.btc.date}）`});
  if(g.liq&&nz(g.liq.netliq))r.push({id:L('闸门3','Gate 3'),t:L('净流动性闸门未触发','Net-liquidity gate not tripped'),k:g.liq.tripped?'serious':'good',
    x:L(`净流动性 13 周 ${fmtP(g.liq.netliq,2)}（${g.liq.asof}）；美元 13 周 ${fmtP(g.liq.usd,2)}。≤ −2.72% 且美元走强才触发（只打折不加仓）`,`Net liquidity 13w ${fmtP(g.liq.netliq,2)} (${g.liq.asof}); dollar 13w ${fmtP(g.liq.usd,2)}. Trips only at ≤ −2.72% with a stronger dollar (discount only)`)});
  else r.push({id:L('闸门3','Gate 3'),t:L('净流动性闸门','Net-liquidity gate'),k:'na',x:L('未取到','missing')});
  return r;
}
function checks(c){
  const r=gates(); const fr=c.fees.revenue, pr=c.price, u=c.unlock;
  r.push({id:'R1',t:L('六问卡完整','Six-question card complete'),k:'na',x:(MAN.sixq||{})[c.sym]||(c.track==='watch'?L('观察标的，未入候选','watch item, not a candidate'):L('未写','not written'))});
  if(u&&nz(u.pct_circ))r.push({id:'R2',t:L('30 日内无 ≥5% 流通量解锁','No ≥5% float unlock within 30 days'),k:u.pct_circ<5?'good':'crit',x:`${L('约','≈')} ${u.pct_circ.toFixed(2)}%（${esc(u.note)}）`});
  else r.push({id:'R2',t:L('30 日内无 ≥5% 流通量解锁','No ≥5% float unlock within 30 days'),k:c.under5?'good':'na',x:c.under5?L('已查未见 ≥5%（具体值未取）','checked, none ≥5% (exact size not fetched)'):L('未核','not checked')});
  if(pr&&fr&&nz(fr.mom30)&&nz(pr.ret30)){const g=pr.ret30-fr.mom30;r.push({id:'R3',t:L('价格没有跑在收入前面','Price not running ahead of revenue'),k:g>30?'serious':'good',x:L(`价格 30 日 ${fmtP(pr.ret30)}；收入 30 日环比 ${fmtP(fr.mom30)}；差 ${fmtP(g)}pp（> 30pp 算跑在前面）`,`Price 30d ${fmtP(pr.ret30)}; revenue 30d ${fmtP(fr.mom30)}; gap ${fmtP(g)}pp (>30pp = ahead)`)})}
  else r.push({id:'R3',t:L('价格没有跑在收入前面','Price not running ahead of revenue'),k:'na',x:L('缺收入或价格','missing revenue or price')});
  r.push({id:'R4',t:L('近期强势不加分','Recent strength earns no points'),k:'good',x:L('评分不含价格强弱；技术形态只展示（回测：点火前相对 BTC 最强的五分之一没有跑赢篮子）','Score excludes price strength; technicals shown only (backtest: the strongest fifth vs BTC before ignition did not beat the basket)')});
  if(c.tag==='channelB'){const w=fr?fr.d7v30:null;r.push({id:'R6',t:L('渠道 B：平台收入 7 日均转正','Channel B: platform revenue 7d avg turning up'),k:nz(w)&&w>0?'good':'crit',x:L(`收入 7 日均对 30 日均 ${fmtP(w)}`,`Revenue 7d vs 30d ${fmtP(w)}`)})}
  return r;
}
function verdict(c){
  const ck=checks(c); const hard=ck.filter(x=>x.k==='crit'||x.k==='serious'); const unk=ck.filter(x=>x.k==='na'&&/1|3/.test(x.id)&&x.id!=='R3');
  if(hard.length)return {k:'crit',t:L('有硬条件未过','Hard condition failing'),d:hard.map(x=>x.id).join('、')};
  if(c.track==='watch')return {k:'na',t:L('观察标的','Watch item'),d:L('不做建仓条件检查','no entry checklist')};
  if(unk.length)return {k:'warn',t:L('条件未齐','Conditions incomplete'),d:L('缺 ','missing ')+unk.map(x=>x.id).join('、')};
  return {k:'good',t:L('条件齐备','Conditions met'),d:L('可进入建仓评估','ready for entry review')};
}

/* ---------- 风险提示（自动规则 + 人工登记） ---------- */
function autoAlerts(){
  const out=[]; const T=D.last_complete_day;
  SYMS.forEach(k=>{const c=C[k],fr=c.fees.revenue,pr=c.price,a=c.act,u=c.unlock;
    if(fr&&nz(fr.d7v30)&&fr.d7v30<=-25)out.push({d:fr.last_day||T,s:k,k:'serious',t:L(`收入 7 日均比 30 日均低 ${Math.abs(fr.d7v30).toFixed(1)}%`,`Revenue 7d avg ${Math.abs(fr.d7v30).toFixed(1)}% below 30d avg`),src:'DefiLlama',lvl:L('自动','auto')});
    if(fr&&nz(fr.d7v30)&&fr.d7v30>=25)out.push({d:fr.last_day||T,s:k,k:'good',t:L(`收入 7 日均比 30 日均高 ${fr.d7v30.toFixed(1)}%`,`Revenue 7d avg ${fr.d7v30.toFixed(1)}% above 30d avg`),src:'DefiLlama',lvl:L('自动','auto')});
    if(fr&&fr.sum30>0&&c.fees.holders&&c.fees.holders.sum30===0)out.push({d:T,s:k,k:'warn',t:L('协议有收入，但持有人收入为 0（无回购 / 分红口径）','Protocol earns revenue but holder revenue is 0 (no buyback / dividend)'),src:'DefiLlama',lvl:L('自动','auto')});
    if(pr&&pr.dd120<=-40)out.push({d:pr.date,s:k,k:'warn',t:L(`价格较 120 日高点回撤 ${pr.dd120.toFixed(1)}%`,`Price ${pr.dd120.toFixed(1)}% off its 120-day high`),src:L('币安日线','Binance daily'),lvl:L('自动','auto')});
    if(pr&&nz(pr.rsi14)&&pr.rsi14<=25)out.push({d:pr.date,s:k,k:'warn',t:L(`日线 RSI14 = ${pr.rsi14.toFixed(0)}（超卖区）`,`Daily RSI14 = ${pr.rsi14.toFixed(0)} (oversold)`),src:L('币安日线','Binance daily'),lvl:L('自动','auto')});
    if(pr&&nz(pr.rsi14)&&pr.rsi14>=75)out.push({d:pr.date,s:k,k:'warn',t:L(`日线 RSI14 = ${pr.rsi14.toFixed(0)}（超买区）`,`Daily RSI14 = ${pr.rsi14.toFixed(0)} (overbought)`),src:L('币安日线','Binance daily'),lvl:L('自动','auto')});
    if(pr&&nz(pr.vol7v30)&&pr.vol7v30<=-40)out.push({d:pr.date,s:k,k:'warn',t:L(`代币成交额 7 日均比 30 日均低 ${Math.abs(pr.vol7v30).toFixed(0)}%（量能萎缩）`,`Token volume 7d avg ${Math.abs(pr.vol7v30).toFixed(0)}% below 30d (drying up)`),src:L('币安日线','Binance daily'),lvl:L('自动','auto')});
    if(a&&nz(a.d7v30)&&a.d7v30<=-20)out.push({d:a.last_day||T,s:k,k:'serious',t:L(`${a.label} 7 日均比 30 日均低 ${Math.abs(a.d7v30).toFixed(1)}%`,`${a.label==='TVL'?'TVL':'Volume'} 7d avg ${Math.abs(a.d7v30).toFixed(1)}% below 30d`),src:'DefiLlama',lvl:L('自动','auto')});
    if(pr&&fr&&nz(fr.mom30)&&nz(pr.ret30)&&pr.ret30-fr.mom30>30)out.push({d:pr.date,s:k,k:'serious',t:L(`价格跑在收入前面（价格 30 日 ${fmtP(pr.ret30)} / 收入 30 日环比 ${fmtP(fr.mom30)}）`,`Price ahead of revenue (price 30d ${fmtP(pr.ret30)} / revenue 30d ${fmtP(fr.mom30)})`),src:L('规则 R3','Rule R3'),lvl:L('假设','hypothesis')});
    if(u&&nz(u.cover)&&u.cover<1&&u.cover>0)out.push({d:T,s:k,k:'serious',t:L(`30 日持有人收入只覆盖${u.actual_usd!=null?'近月实际领取':'解锁价值'}的 ${(u.cover*100).toFixed(0)}%`,`30d holder revenue covers only ${(u.cover*100).toFixed(0)}% of the ${u.actual_usd!=null?'actual monthly claim':'unlock value'}`),src:L('解锁登记 × 收入','Unlock log × revenue'),lvl:L('假设','hypothesis')});
  });
  return out;
}
const manualEv=()=>(MAN.events||[]).map(e=>({...e,lvl:e.lvl}));
const ALL=(fut=false)=>[...manualEv().filter(e=>fut||e.d<=D.last_complete_day),...autoAlerts()].sort((a,b)=>b.d.localeCompare(a.d));
const alertHTML=e=>`<div class="alert"><div class="d">${esc(e.d)}</div><div>${e.s?`<a data-go="coin/${esc(e.s)}"><b>${esc(e.s)}</b></a> `:''}${stat(e.k,esc(e.t))}<div class="sm">${esc(e.src||'')}${e.lvl?' · '+esc(e.lvl):''}</div></div></div>`;

/* ---------- 图表（SVG，悬停 / 触摸看数） ---------- */
function lineChart(host,dates,series,o={}){
  if(!host)return; const W=640,H=o.h||200,pl=50,pr=10,pt=8,pb=22; const n=dates.length;
  let vals=series.flatMap(s=>s.v.filter(nz)); if(!vals.length||n<2){host.innerHTML=`<div class="empty">${L('数据不足','Not enough data')}</div>`;return}
  if(o.zero)vals.push(0);
  let lo=Math.min(...vals),hi=Math.max(...vals); if(lo===hi){lo-=1;hi+=1} const pad=(hi-lo)*.06; const nonneg=Math.min(...vals)>=0; lo-=pad;hi+=pad; if((o.zero&&lo>0)||(nonneg&&lo<0))lo=0;
  if(o.lo!=null)lo=o.lo; if(o.hi!=null)hi=o.hi;
  const x=i=>pl+(W-pl-pr)*(i/(n-1)), y=v=>pt+(H-pt-pb)*(o.inv?(v-lo)/(hi-lo):(1-(v-lo)/(hi-lo)));
  const yf=o.yf||fmtU; let g='';
  for(let t=0;t<4;t++){const v=lo+(hi-lo)*t/3;g+=`<line x1="${pl}" x2="${W-pr}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/><text x="${pl-6}" y="${y(v)+4}" text-anchor="end" font-size="10" fill="var(--muted)">${yf(v)}</text>`}
  [0,Math.floor((n-1)/2),n-1].forEach(i=>{g+=`<text x="${x(i)}" y="${H-6}" text-anchor="${i===0?'start':i===n-1?'end':'middle'}" font-size="10" fill="var(--muted)">${dates[i].slice(5)}</text>`});
  (o.hl||[]).forEach(h=>{g+=`<line x1="${pl}" x2="${W-pr}" y1="${y(h.v)}" y2="${y(h.v)}" stroke="var(--muted)" stroke-dasharray="4 3"/><text x="${W-pr}" y="${y(h.v)-3}" text-anchor="end" font-size="10" fill="var(--muted)">${h.t}</text>`});
  series.forEach(s=>{let d='',pen=false;s.v.forEach((v,i)=>{if(!nz(v)){pen=false;return}d+=(pen?'L':'M')+x(i).toFixed(1)+' '+y(v).toFixed(1);pen=true});
    if(s.dot&&!d.includes('L'))s.v.forEach((v,i)=>{if(nz(v))g+=`<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="${s.c}"/>`});
    g+=`<path d="${d}" fill="none" stroke="${s.c}" stroke-width="${s.w||2}" stroke-linejoin="round" ${s.dash?'stroke-dasharray="5 3"':''}/>`});
  host.innerHTML=`<div class="legend">${series.map(s=>`<span style="--c:${s.c}">${s.n}</span>`).join('')}</div><div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.title||'')}">${g}<line class="cx" y1="${pt}" y2="${H-pb}" stroke="var(--muted)" style="display:none"/><rect x="${pl}" y="0" width="${W-pl-pr}" height="${H}" fill="transparent"/></svg><div class="tip"></div></div>`;
  const box=host.querySelector('.chart'),svg=box.querySelector('svg'),tip=box.querySelector('.tip'),cx=box.querySelector('.cx');
  const mv=ev=>{const r=svg.getBoundingClientRect();const px=(ev.clientX-r.left)/r.width*W;let i=Math.round((px-pl)/(W-pl-pr)*(n-1));i=Math.max(0,Math.min(n-1,i));
    cx.setAttribute('x1',x(i));cx.setAttribute('x2',x(i));cx.style.display='';tip.style.display='block';
    tip.innerHTML=`<b>${dates[i]}</b><br>`+series.map(s=>`<span style="color:${s.c}">●</span> ${s.n}: ${(o.tf||yf)(s.v[i])}`).join('<br>');
    tip.style.left=Math.max(0,Math.min(x(i)/W*r.width+12,r.width-170))+'px';tip.style.top='6px'};
  svg.addEventListener('mousemove',mv);svg.addEventListener('touchmove',e=>mv(e.touches[0]),{passive:true});svg.addEventListener('mouseleave',()=>{tip.style.display='none';cx.style.display='none'});
}
function spark(vals,w=90,h=24,col='var(--s1)'){if(!vals)return '';const v=vals.filter(nz);if(v.length<2)return '';const lo=Math.min(...v),hi=Math.max(...v);const n=vals.length;let d='',pen=false;
  vals.forEach((q,i)=>{if(!nz(q)){pen=false;return}const X=i/(n-1)*(w-2)+1,Y=h-2-(hi===lo?.5:(q-lo)/(hi-lo))*(h-4);d+=(pen?'L':'M')+X.toFixed(1)+' '+Y.toFixed(1);pen=true});
  return `<svg class="sp" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><path d="${d}" fill="none" stroke="${col}" stroke-width="1.6"/></svg>`}
const sma=(a,n)=>a.map((_,i)=>i<n-1?null:a.slice(i-n+1,i+1).reduce((p,q)=>p+(q||0),0)/n);

/* ---------- 页面 ---------- */
const scTxt=c=>c.sc.total===null?'—':`${c.sc.total} <span class="sm">(${c.sc.n}/6)</span>`;
const tagHTML=c=>`${c.track==='pool'?`<span class="tg pool">${c.tier}</span>`:`<span class="tg">${L('观察','Watch')}</span>`}${c.tag==='ambush'?`<span class="tg">${L('埋伏候选','Ambush')}</span>`:''}${c.tag==='channelB'?`<span class="tg">${L('渠道B','Channel B')}</span>`:''}`;
function home(){
  const rows=SYMS.map(k=>C[k]), pool=rows.filter(c=>c.track==='pool');
  const withR=pool.filter(c=>c.fees.revenue&&nz(c.fees.revenue.d7v30)), up=withR.filter(c=>c.fees.revenue.d7v30>0).length;
  const al=autoAlerts().filter(a=>a.k==='serious'||a.k==='crit').length;
  const ranked=pool.filter(c=>c.sc.n>=4).sort((a,b)=>b.sc.total-a.sc.total);
  const amb=pool.filter(c=>c.tag==='ambush'||c.tag==='channelB');
  const gs=gates(); const gOK=gs.filter(x=>x.k==='good').length;
  let h=`<div class="cgrid g4">
  <div class="ccard kpi"><div class="l">${L('三道闸门（周期 / BTC 底线 / 流动性）','Three gates (cycle / BTC floor / liquidity)')}</div><div class="v">${gOK} / 3</div><div class="s">${gs.map(x=>stat(x.k,x.id)).join(' ')}</div></div>
  <div class="ccard kpi"><div class="l">${L('收入 7 日均 > 30 日均','Revenue 7d > 30d avg')}</div><div class="v">${up} / ${withR.length}</div><div class="s">${L(`观测池 ${pool.length} 个协议`,`${pool.length} protocols in the pool`)}</div></div>
  <div class="ccard kpi"><div class="l">${L('需要关注的风险信号','Risk signals to watch')}</div><div class="v">${al}</div><div class="s"><a data-go="alerts">${L('看风险提示 →','See risk alerts →')}</a></div></div>
  <div class="ccard kpi"><div class="l">${L('观测池 对 全市场（30 日中位）','Pool vs market (30d median)')}</div><div class="v ${cls(D.market&&D.market.bench.r30.pool_med)}" style="font-size:20px">${D.market?fmtP(D.market.bench.r30.pool_med)+' / '+fmtP(D.market.bench.r30.ew_med):'—'}</div><div class="s">BTC ${fmtP(D.btc.r30)} · <a data-go="market">${L('全市场 →','Market →')}</a></div></div></div>`;
  h+=`<div class="ccard"><h2>${L('埋伏仓候选 · 条件检查','Ambush candidates · condition check')}</h2><div class="sm" style="margin-bottom:6px">${L('只做规则判定，不是买卖建议。点标的看每条规则的数据。','Rule checks only, not trade advice. Click a row for the data behind each rule.')}</div><div class="scroll"><table><thead><tr><th>${L('标的','Asset')}</th><th>${L('评分','Score')}</th><th>${L('规则判定','Rule check')}</th><th>${L('收入 7v30','Rev 7v30')}</th><th>${L('距 120 日高','vs 120d high')}</th><th>${L('量能 7v30','Volume 7v30')}</th><th>${L('技术形态','Technicals')}</th><th>${L('近 30 日收入','Revenue 30d')}</th></tr></thead><tbody>`+
  amb.map(c=>{const v=verdict(c),p=c.price,r=c.fees.revenue;return `<tr data-go="coin/${c.sym}"><td><b>${c.sym}</b> <span class="sm">${esc(c.name)}</span>${tagHTML(c)}</td><td>${scTxt(c)}</td><td>${stat(v.k,v.t)} <span class="sm">${esc(v.d)}</span></td><td class="${cls(r&&r.d7v30)}">${fmtP(r&&r.d7v30)}</td><td class="${cls(p&&p.dd120)}">${fmtP(p&&p.dd120)}</td><td class="${cls(p&&p.vol7v30)}">${fmtP(p&&p.vol7v30)}</td><td>${p?trend(p.trend):'—'}</td><td>${spark(c.spark_rev)}</td></tr>`}).join('')+`</tbody></table></div></div>`;
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('评分排行（已评 ≥ 4 个模块）','Score ranking (≥4 modules scored)')}</h2>`+ranked.slice(0,10).map((c,i)=>`<div class="mod" style="grid-template-columns:22px 64px 1fr 34px;cursor:pointer" data-go="coin/${c.sym}"><span class="sm">${i+1}</span><b style="text-align:left">${c.sym}</b><div class="bar"><b style="width:${c.sc.total}%"></b></div><span>${c.sc.total}</span></div>`).join('')+`<div class="sm" style="margin-top:6px">${L('评分只用于排序，不是预测；规则为【假设】，见“口径与规则”。','Score is for sorting only, not a forecast; rules are hypotheses (see Method).')}</div></div>
  <div class="ccard"><h2>${L('最新监控消息','Latest alerts')}</h2>${ALL().slice(0,7).map(alertHTML).join('')}<div style="margin-top:6px"><a data-go="alerts">${L('全部 →','All →')}</a></div></div></div>`;
  const f=(MAN.findings||[])[0];
  if(f)h+=`<div class="ccard find"><h2>${L('重大发现 · 最新一批','Key findings · latest batch')} <span class="sm">${f.d}</span></h2><h3>${esc(f.title)}</h3><ul>${f.items.slice(0,5).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><div style="margin-top:6px"><a data-go="findings">${L('全部记录 →','All findings →')}</a></div></div>`;
  return h;
}
let sortKey='score',sortDir=-1,fTier='all',fTag='all';
const COLS=[['score',L('评分','Score'),c=>c.sc.total],['rev',L('收入 7v30','Rev 7v30'),c=>c.fees.revenue&&c.fees.revenue.d7v30],['mom',L('收入 30 日环比','Rev 30d'),c=>c.fees.revenue&&c.fees.revenue.mom30],
 ['phr',L('市值 / 年化持有人收入','Mcap / ann. holder rev'),c=>c.val&&c.val.p_hr],['hsh',L('持有人占比','Holder share'),c=>c.hshare],['r30',L('价格 30 日','Price 30d'),c=>c.price&&c.price.ret30],['dd',L('距 120 日高','vs 120d high'),c=>c.price&&c.price.dd120],['ma',L('距 MA200','vs MA200'),c=>c.price&&c.price.vsMA200],
 ['vol',L('量能 7v30','Volume 7v30'),c=>c.price&&c.price.vol7v30],['act',L('业务量 7v30','Activity 7v30'),c=>c.act&&c.act.d7v30],['vr',L('成交额排名','Volume rank'),c=>c.vrank&&c.vrank.cur]];
function rank(){
  let rows=SYMS.map(k=>C[k]).filter(c=>(fTier==='all'||c.tier===fTier)&&(fTag==='all'||c.tag===fTag));
  const col=COLS.find(x=>x[0]===sortKey); rows.sort((a,b)=>{const x=col[2](a),y=col[2](b);if(!nz(x))return 1;if(!nz(y))return -1;return (x-y)*sortDir});
  const pill=(g,v,t,cur)=>`<span class="pill ${cur===v?'on':''}" data-f="${g}:${v}">${t}</span>`;
  return `<div class="ccard"><div class="filters"><span class="sm">${L('分层','Tier')}</span>${pill('tier','all',L('全部','All'),fTier)}${['T1','T2','T3','W'].map(t=>pill('tier',t,TIER[t],fTier)).join('')}<span class="sm">${L('候选','Candidate')}</span>${pill('tag','all',L('全部','All'),fTag)}${pill('tag','ambush',L('埋伏仓候选','Ambush'),fTag)}${pill('tag','channelB',L('渠道B','Channel B'),fTag)}</div>
  <div class="scroll"><table><thead><tr><th>${L('标的','Asset')}</th>${COLS.map(c=>`<th data-s="${c[0]}" class="${sortKey===c[0]?'sorted':''}">${c[1]}${sortKey===c[0]?(sortDir<0?' ↓':' ↑'):''}</th>`).join('')}<th>${L('收入 30 日','Revenue 30d')}</th><th>${L('价格 90 日','Price 90d')}</th></tr></thead><tbody>`+
  rows.map(c=>{const r=c.fees.revenue,p=c.price;return `<tr data-go="coin/${c.sym}"><td><b>${c.sym}</b>${tagHTML(c)}</td><td>${scTxt(c)}</td>
  <td class="${cls(r&&r.d7v30)}">${fmtP(r&&r.d7v30)}</td><td class="${cls(r&&r.mom30)}">${fmtP(r&&r.mom30)}</td><td>${fmtX(c.val&&c.val.p_hr)}</td><td>${nz(c.hshare)?c.hshare.toFixed(0)+'%':'—'}</td>
  <td class="${cls(p&&p.ret30)}">${fmtP(p&&p.ret30)}</td><td class="${cls(p&&p.dd120)}">${fmtP(p&&p.dd120)}</td><td class="${cls(p&&p.vsMA200)}">${fmtP(p&&p.vsMA200)}</td><td class="${cls(p&&p.vol7v30)}">${fmtP(p&&p.vol7v30)}</td><td class="${cls(c.act&&c.act.d7v30)}">${fmtP(c.act&&c.act.d7v30)}</td><td>${c.vrank&&c.vrank.cur?'#'+c.vrank.cur:'—'}</td>
  <td>${spark(c.spark_rev)}</td><td>${spark(c.spark_px,90,24,'var(--s2)')}</td></tr>`}).join('')+`</tbody></table></div>
  <div class="sm" style="margin-top:8px">${L('点表头排序，点行进详情。NEAR 的收入口径是 NEAR Intents，不是整条链，P/收入仅作参考。观察标的（叙事 / 赛道）多数没有协议收入，只看价格、量能和叙事阶段。成交额排名 = 币安现货 + U 本位永续合并。','Click a header to sort, a row for details. NEAR revenue is NEAR Intents only. Watch items mostly have no protocol revenue: price, volume and narrative stage only. Volume rank = Binance spot + USDⓈ-M perps combined.')}</div></div>`;
}
let SER={};
function coin(k){
  const c=C[k]; if(!c)return `<div class="ccard">${L('没有这个标的','Unknown asset')}</div>`;
  const p=c.price,fr=c.fees.revenue,fh=c.fees.holders,ff=c.fees.fees,v=c.val,vd=verdict(c),man=(MAN.fals||{})[k]||[],rk=(MAN.risks||[]).filter(x=>x.s===k);
  let h=`<a class="back" data-go="rank">← ${L('排行榜','Ranking')}</a><div class="ccard"><div style="display:flex;flex-wrap:wrap;gap:8px 18px;align-items:baseline"><h2 style="font-size:19px;margin:0">${c.sym} <span class="sm">${esc(c.name)}</span></h2>${tagHTML(c)}<span>${stat(vd.k,vd.t)} <span class="sm">${esc(vd.d)}</span></span></div>
  <div class="sm" style="margin-top:4px">${esc(c.sector||'')}${c.pos?' · '+esc(c.pos):''}${c.note?' · '+L('回购 / 销毁口径：','Buyback / burn: ')+esc(c.note):''}</div></div>`;
  h+=`<div class="cgrid g4">
  <div class="ccard kpi"><div class="l">${L('收盘','Close')}（${p?p.date:'—'}）</div><div class="v">${p?fmtPx(p.last):'—'}</div><div class="s ${cls(p&&p.ret30)}">${L('30 日','30d')} ${fmtP(p&&p.ret30)}${p&&nz(p.ret30vsBTC)?`（${L('对 BTC','vs BTC')} ${fmtP(p.ret30vsBTC)}pp）`:''}</div></div>
  <div class="ccard kpi"><div class="l">${L('综合评分（假设）','Score (hypothesis)')}</div><div class="v">${c.sc.total===null?'—':c.sc.total}</div><div class="s">${L(`已评 ${c.sc.n}/6 个模块`,`${c.sc.n}/6 modules scored`)}</div></div>
  <div class="ccard kpi"><div class="l">${L('市值 / FDV','Mcap / FDV')}</div><div class="v" style="font-size:20px">${v?fmtU(v.mcap):'—'} <span class="sm">/ ${v?fmtU(v.fdv):'—'}</span></div><div class="s">${v?esc(v.src):''}</div></div>
  <div class="ccard kpi"><div class="l">${L('30 日协议收入 / 持有人收入','30d revenue / holder revenue')}</div><div class="v" style="font-size:20px">${fr?fmtU(fr.sum30):'—'} <span class="sm">/ ${fh?fmtU(fh.sum30):'—'}</span></div><div class="s">${L('抽成率','Take rate')} ${nz(c.take)?c.take.toFixed(0)+'%':'—'} · ${L('持有人占比','holder share')} ${nz(c.hshare)?c.hshare.toFixed(0)+'%':'—'}</div></div></div>`;
  if(c.stage||c.basis)h+=`<div class="ccard"><h2>${L('叙事阶段','Narrative stage')} <span class="sm">${L('人工核对','manual check')} ${esc(c.asof||'')}</span></h2><div class="stage">${esc(c.stage||'—')}</div><div class="sm" style="color:var(--ink2);font-size:13px;line-height:1.65">${esc(c.basis||'')}</div></div>`;
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('价格与 MA200（技术面）','Price & MA200 (technicals)')}</h2><div id="ch1"></div></div><div class="ccard"><h2>${L('代币成交额（资金面，USDT / 日）','Token volume (flows, USDT / day)')}</h2><div id="ch2"></div></div>
  <div class="ccard"><h2>${L('手续费 / 协议收入 / 持有人收入（基本面，日）','Fees / revenue / holder revenue (fundamentals, daily)')}</h2><div id="ch3"></div></div>
  <div class="ccard"><h2>${c.act?(c.act.label==='TVL'?'TVL':L('业务量：日成交额','Activity: daily volume'))+L('（基本面）',' (fundamentals)'):L('业务量','Activity')}</h2>${c.act?'<div id="ch4"></div>':`<div class="empty">${L('该标的没有可用的业务量口径。','No activity series for this asset.')}</div>`}</div>
  <div class="ccard"><h2>${L('评分与成交额排名走势','Score & volume-rank history')}</h2><div id="ch5"></div><div class="sm">${L('每天一点，从 2026-11-13 开始记录，不回填。','One point a day from 2026-11-13; never backfilled.')}</div></div>
  <div class="ccard"><h2>${L('资金面 · 币安成交额排名','Flows · Binance volume rank')}</h2>${volCard(c)}</div></div>`;
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('技术形态','Technicals')}</h2><table class="kv"><tbody>
  <tr><td>${L('形态','Pattern')}</td><td>${p?trend(p.trend):'—'}</td></tr><tr><td>MA20 / MA50</td><td>${p?fmtPx(p.ma20)+' / '+fmtPx(p.ma50):'—'}</td></tr><tr><td>MA200</td><td>${p&&p.ma200?fmtPx(p.ma200)+'（'+fmtP(p.vsMA200)+'）':L('历史不足 200 天','<200 days of history')}</td></tr>
  <tr><td>RSI14</td><td>${p&&nz(p.rsi14)?p.rsi14.toFixed(0):'—'}</td></tr><tr><td>${L('距 120 日高点','vs 120-day high')}</td><td class="${cls(p&&p.dd120)}">${fmtP(p&&p.dd120)}</td></tr><tr><td>${L('30 日区间位置','30-day range position')}</td><td>${p&&nz(p.pos30)?p.pos30.toFixed(0)+'%'+L('（0 = 区间低点）',' (0 = range low)'):'—'}</td></tr>
  <tr><td>${L('成交额 7 日均 / 30 日均','Volume 7d / 30d avg')}</td><td>${p?fmtU(p.vol7)+' / '+fmtU(p.vol30)+'（'+fmtP(p.vol7v30)+'）':'—'}</td></tr><tr><td>${L('30 日换手（成交额 / 市值）','30d turnover (volume / mcap)')}</td><td>${v&&nz(v.turnover30)?v.turnover30.toFixed(0)+'%':'—'}</td></tr></tbody></table>
  <div class="sm" style="margin-top:6px">${L('技术形态只展示，不进评分（规则 R4：近期强势不加分）。','Technicals are shown, not scored (rule R4).')}</div></div>
  <div class="ccard"><h2>${L('估值与收入质量','Valuation & revenue quality')}</h2><table class="kv"><tbody>
  <tr><td>${L('市值 / 年化协议收入','Mcap / ann. revenue')}</td><td>${fmtX(v&&v.p_rev)}</td></tr><tr><td>${L('FDV / 年化协议收入','FDV / ann. revenue')}</td><td>${fmtX(v&&v.p_rev_fd)}</td></tr><tr><td>${L('市值 / 年化持有人收入','Mcap / ann. holder revenue')}</td><td>${fmtX(v&&v.p_hr)}</td></tr><tr><td>${L('持有人收入年化收益率','Holder revenue yield')}</td><td>${v&&nz(v.hr_yield)?v.hr_yield.toFixed(1)+'%':'—'}</td></tr>
  <tr><td>${L('手续费 / 收入 / 持有人 7v30','Fees / rev / holders 7v30')}</td><td>${fmtP(ff&&ff.d7v30)} / ${fmtP(fr&&fr.d7v30)} / ${fmtP(fh&&fh.d7v30)}</td></tr>
  <tr><td>${L('代币激励 / 收益（收入 − 激励）','Incentives / earnings')}</td><td class="sm">${L('待接入','Pending')}</td></tr>
  ${c.unlock&&nz(c.unlock.usd)&&c.unlock.usd>0?`<tr><td>${L('30 日解锁价值 vs 持有人收入','30d unlock value vs holder revenue')}</td><td>${fmtU(c.unlock.usd)} vs ${fmtU(fh?fh.sum30:0)}${nz(c.unlock.cover_paper)?'（'+L('覆盖','cover')+' '+(c.unlock.cover_paper*100).toFixed(0)+'%）':''}</td></tr>`:''}</tbody></table>
  ${c.sym==='NEAR'?`<div class="sm" style="margin-top:6px">${L('NEAR：收入口径仅为 Intents，对整个 NEAR 市值的倍数偏高，仅作参考。','NEAR: revenue is Intents only, so multiples vs the whole NEAR cap read high.')}</div>`:''}</div></div>`;
  h+=supplyCard(c);
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('基本面评分（假设）','Fundamental score (hypothesis)')}</h2>${c.sc.mods.map(m=>`<div class="mod"><span class="k">${m.k}</span><span>${esc(m.n)}</span><span class="sm">${esc(m.why)}</span><b>${m.s===null?'—':m.s}</b></div>`).join('')}
  <div class="sm" style="margin-top:6px">${L('每项 0–3 分；综合分 = 已评模块得分 ÷（3 × 已评模块数）。未评模块不扣分，综合分只作排序用。','Each 0–3; total = points ÷ (3 × modules scored). Unscored modules are skipped; the total is for sorting only.')}</div></div>
  <div class="ccard"><h2>${L('建仓条件检查','Entry condition check')}</h2>${checks(c).map(x=>`<div class="mod mod2"><b style="text-align:left">${x.id}</b><div>${stat(x.k,esc(x.t))}<div class="sm">${x.x}</div></div></div>`).join('')}
  <div class="sm" style="margin-top:6px">${L('失效规则（大叔方法论，不在此页判定）：90 天内无 T1 信号减半；较平均成本 −30% 清仓；BTC 收盘跌破本轮最低收盘停止加仓。埋伏仓不宜用窄止损（点火前回撤中位 −11.5%，最深 −23%）。','Exit rules (from the method, not judged here): halve if no T1 signal within 90 days; exit at −30% vs average cost; stop adding if BTC closes below the cycle low. Ambush positions should not use tight stops (pre-ignition pullback median −11.5%, worst −23%).')}</div></div></div>`;
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('风险提示 · 证伪 / 降级条件','Risk · falsification / downgrade')}</h2>${man.length?man.map(f=>`<div class="mod mod1"><div>${stat(f.k,esc(f.t))}<div class="sm">${esc(f.x)}</div></div></div>`).join(''):''}${rk.map(f=>`<div class="mod mod1"><div>${stat('serious',esc(f.cat)+'：'+esc(f.t))}<div class="sm">${L('人工登记','manual log')} ${esc(f.asof)}</div></div></div>`).join('')}${!man.length&&!rk.length?`<div class="empty">${L('尚未登记。','Nothing logged yet.')}</div>`:''}</div>
  <div class="ccard"><h2>${c.sym} ${L('相关消息','alerts')}</h2>${ALL(true).filter(e=>e.s===k).map(alertHTML).join('')||`<div class="empty">${L('暂无。','None.')}</div>`}</div></div>`;
  setTimeout(()=>drawCoin(c),0);
  return h;
}
function volCard(c){
  const r=c.vrank; if(!r)return `<div class="empty">${L('不在币安成交额榜统计范围（或无现货 USDT 交易对）。','Not in the Binance volume universe.')}</div>`;
  const vb=D.market&&D.market.vol;
  return `<table class="kv"><tbody><tr><td>${L('合并排名（现货 + 永续）','Combined rank (spot + perps)')}</td><td><b>#${r.cur||'—'}</b>（${vb?vb.last_day:''}）</td></tr>
  <tr><td>${L('现货 / 永续 单独排名','Spot / perp rank')}</td><td>${r.spot?'#'+r.spot:'—'} / ${r.fut?'#'+r.fut:'—'}</td></tr>
  <tr><td>${L(`近 ${vb?vb.window_days:90} 天排名中位 / 最好`,`Median / best rank (${vb?vb.window_days:90}d)`)}</td><td>#${r.med} / #${r.best}</td></tr>
  <tr><td>${L('进前 30 的天数','Days in top 30')}</td><td>${r.d30} / ${vb?vb.window_days:90}</td></tr>
  <tr><td>${L('近 30 天永续成交占比','Perp share of volume (30d)')}</td><td>${nz(r.fut_share_30d)?r.fut_share_30d.toFixed(0)+'%':'—'}</td></tr></tbody></table>
  <div class="sm" style="margin-top:6px">${L('排名代表流动性与热度，不是买入信号。','Rank reflects liquidity and attention, not a buy signal.')}</div>`;
}
function drawCoin(c){
  const go=s=>{
    const ps=s.price;
    if(ps){lineChart($('#ch1'),ps.dates,[{n:L('收盘价','Close'),c:'var(--s1)',v:ps.close},{n:'MA200',c:'var(--s2)',v:ps.ma200,w:1.5,dash:true}],{yf:fmtPx,h:210,title:'price'});
      lineChart($('#ch2'),ps.dates,[{n:L('成交额','Volume'),c:'var(--s1)',v:ps.vol,w:1.1},{n:L('7 日均','7d avg'),c:'var(--s2)',v:sma(ps.vol,7),w:2}],{h:210,zero:true,title:'volume'})}
    else{$('#ch1').innerHTML=`<div class="empty">${L('无币安现货日线。','No Binance spot candles.')}</div>`;$('#ch2').innerHTML=''}
    const f=s.fees;
    if(f){const ser=[{n:L('手续费','Fees'),c:'var(--s1)',v:f.fees,w:1.6}];if(f.revenue.some(nz))ser.push({n:L('协议收入','Revenue'),c:'var(--s2)',v:f.revenue});if(f.holders.some(nz))ser.push({n:L('持有人收入','Holder revenue'),c:'var(--s3)',v:f.holders});lineChart($('#ch3'),f.dates,ser,{h:210,zero:true,title:'fees'})}
    else $('#ch3').innerHTML=`<div class="empty">${L('没有协议收入数据（DefiLlama 无此协议的费用口径）。','No fee / revenue data on DefiLlama.')}</div>`;
    if(s.act&&$('#ch4'))lineChart($('#ch4'),s.act.dates,[{n:s.act.label==='TVL'?'TVL':L('日成交额','Daily volume'),c:'var(--s1)',v:s.act.vals},{n:L('7 日均','7d avg'),c:'var(--s2)',v:sma(s.act.vals,7),w:1.8}],{h:210,title:'activity'});
  };
  if(SER[c.sym])go(SER[c.sym]); else fetch(`${sdir}${c.sym}.json?v=${D.last_complete_day}`).then(r=>r.json()).then(s=>{SER[c.sym]=s;if(location.hash.slice(1)==='coin/'+c.sym)go(s)}).catch(()=>{});
  const hd=()=>{const h=(HIST||[]).filter(x=>x.coins[c.sym]);const el=$('#ch5');if(!el)return;
    if(h.length<2){el.innerHTML=`<div class="empty">${L(`记录中：已有 ${h.length} 天，满 2 天出图。`,`Recording: ${h.length} day(s) so far; chart appears from day 2.`)}${h.length?` ${L('今天','Today')}：${L('评分','score')} ${h[0].coins[c.sym].sc??'—'}，${L('成交额排名','volume rank')} #${h[0].coins[c.sym].vrank??'—'}`:''}</div>`;return}
    lineChart(el,h.map(x=>x.date),[{n:L('评分','Score'),c:'var(--s1)',v:h.map(x=>x.coins[c.sym].sc),dot:true}],{h:170,lo:0,hi:100,yf:v=>v.toFixed(0),title:'score'})};
  if(HIST)hd(); else fetch(hsrc+'?v='+D.last_complete_day).then(r=>r.json()).then(x=>{HIST=x;hd()}).catch(()=>{});
}
function supplyCard(c){
  const s=c.supply,u=c.unlock,fh=c.fees.holders;
  let h=`<div class="ccard"><h2>${L('代币经济学 · 供给与解锁','Tokenomics · supply & unlocks')}</h2><div class="cgrid g2" style="gap:18px;margin:0"><div><h3>${L('供给结构','Supply')}</h3>`;
  if(s){h+=`<table class="kv"><tbody><tr><td>${L('流通量','Circulating')}</td><td>${fmtU(s.circ)}</td></tr><tr><td>${L('总量（扣除销毁）','Total (net of burns)')}</td><td>${fmtU(s.total)}</td></tr>${s.max&&s.max!==s.total?`<tr><td>${L('最大供给','Max')}</td><td>${fmtU(s.max)}</td></tr>`:''}
  <tr><td>${L('流通率','Circulating ratio')}</td><td>${nz(s.circ_ratio)?s.circ_ratio.toFixed(1)+'%':'—'}</td></tr><tr><td>${L('未流通余量 / 流通量','Locked overhang / circulating')}</td><td>${nz(s.overhang_pct)?s.overhang_pct.toFixed(1)+'%':'—'}</td></tr></tbody></table>
  <div class="sm" style="margin-top:6px">${L('未流通余量大，说明未来稀释空间大；它不等于马上会卖。数据：CoinGecko。','A large overhang means room for dilution, not an imminent sale. Source: CoinGecko.')}</div>`}
  else h+=`<div class="empty">${L('无供给数据。','No supply data.')}</div>`;
  h+=`</div><div><h3>${L('解锁 / 增发（30 日）','Unlocks / emissions (30d)')}</h3>`;
  if(u){h+=`<table class="kv"><tbody><tr><td>${L('按条款','Per schedule')}</td><td>${u.tokens?fmtU(u.tokens,2)+' · '+fmtU(u.usd)+(nz(u.pct_circ)?' · '+u.pct_circ.toFixed(2)+'%':''):L('无待解锁','none pending')}</td></tr>
  ${u.actual_tokens!=null?`<tr><td>${L('近月实际领取','Actual last month')}</td><td>${fmtU(u.actual_tokens)} · ${fmtU(u.actual_usd)}</td></tr>`:''}
  ${nz(u.cover_paper)?`<tr><td>${L('30 日持有人收入 ÷ 条款解锁价值','30d holder rev ÷ scheduled unlock')}</td><td>${(u.cover_paper*100).toFixed(0)}%</td></tr>`:''}
  ${u.actual_tokens!=null&&nz(u.cover)?`<tr><td>${L('30 日持有人收入 ÷ 实际领取价值','30d holder rev ÷ actual claim')}</td><td>${(u.cover*100).toFixed(0)}%</td></tr>`:''}</tbody></table>
  <div class="sm" style="margin-top:6px">${esc(u.note)}${u.actual_note?'<br>'+esc(u.actual_note):''}<br>${L('来源','Source')}：${esc(u.src)} · ${esc(u.lvl)}${u.dated?'':L(' · 日期未精确到天',' · date not exact')}</div>`}
  else h+=`<div class="empty">${c.under5?L('已查：30 日内未见 ≥5% 流通量解锁，具体日期和数量未取。','Checked: no ≥5% float unlock in 30 days; exact figures not fetched.'):L('未登记，不当作“没有”。','Not logged; not the same as “none”.')}</div>`;
  return h+`</div></div></div>`;
}
function alerts(){
  const today=D.last_complete_day; const ev=(MAN.events||[]).filter(e=>e.d>today).sort((a,b)=>a.d.localeCompare(b.d));
  const cats={}; (MAN.risks||[]).forEach(r=>{(cats[r.cat]=cats[r.cat]||[]).push(r)});
  return `<div class="ccard"><h2>${L('未来催化剂 / 解锁日历','Upcoming catalysts / unlocks')}</h2>${ev.map(alertHTML).join('')||`<div class="empty">${L('暂无。','None.')}</div>`}<div class="sm" style="margin-top:6px">${L('月度循环的解锁（HYPE 约每月 6 日、PUMP 约每月 12 日、MORPHO 约每月 21 日、ETHFI 每日线性）见各标的详情页。','Monthly unlocks (HYPE ~6th, PUMP ~12th, MORPHO ~21st, ETHFI daily) are on each asset page.')}</div></div>
  <div class="ccard"><h2>${L('风险提示 · 自动规则 + 人工登记','Risk alerts · rules + manual log')}</h2><div class="sm" style="margin-bottom:6px">${L('自动规则：收入、量能、回撤、RSI、业务量、R3（价格跑在收入前面）、解锁覆盖。人工登记：治理、升级、解锁日历。每条标来源和证据等级。','Rules: revenue, volume, drawdown, RSI, activity, R3 (price ahead of revenue), unlock coverage. Manual: governance, upgrades, unlocks. Each line shows source and evidence grade.')}</div>${ALL().map(alertHTML).join('')}</div>
  <div class="ccard"><h2>${L('长期风险记录（团队 / 法律 / 安全 / 资金）','Standing risks (team / legal / security / supply)')}</h2>${Object.keys(cats).map(k=>`<h3 style="margin-top:8px">${esc(k)}</h3>`+cats[k].map(r=>`<div class="alert"><div class="d">${esc(r.asof)}</div><div><a data-go="coin/${esc(r.s)}"><b>${esc(r.s)}</b></a> <span class="sm" style="color:var(--ink2)">${esc(r.t)}</span></div></div>`).join('')).join('')}</div>`;
}
function findings(){
  return `<div class="ccard find"><h2>${L('重大发现看板','Key findings')}</h2><div class="sm" style="margin-bottom:8px">${L('滚动更新，只放“会改变判断”的信号，全部为事实记录，不含买卖建议。','Rolling log of signals that would change a view; facts only, no trade advice.')}${EN?' Entries are in Chinese.':''}</div>
  ${(MAN.findings||[]).map(f=>`<h3 style="margin-top:14px">${esc(f.d)} · ${esc(f.title)}</h3><ul>${f.items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`).join('')}</div>`;
}
let mSort='qv30',mDir=-1,mF='all';
function market(){
  const M=D.market; if(!M)return `<div class="ccard empty">${L('全市场数据未取到。','Market data missing.')}</div>`;
  const B=M.bench,R=M.rows;
  const MCOLS=[['r7',L('7 日','7d'),x=>x.r7],['r30',L('30 日','30d'),x=>x.r30],['r90',L('90 日','90d'),x=>x.r90],['dd120',L('距 120 日高','vs 120d high'),x=>x.dd120],['vsMA200',L('距 MA200','vs MA200'),x=>x.vsMA200],['vol7v30',L('量能 7v30','Vol 7v30'),x=>x.vol7v30],['qv30',L('30 日均现货成交额','30d avg spot volume'),x=>x.qv30],['vrank',L('合并成交额排名','Volume rank'),x=>x.vrank]];
  const kp=(l,k)=>`<div class="ccard kpi"><div class="l">${l}</div><div class="v ${cls(B[k].ew_med)}">${fmtP(B[k].ew_med)}</div><div class="s">BTC ${fmtP(B[k].btc)} · ${L('等权均值','EW mean')} ${fmtP(B[k].ew_mean)}</div></div>`;
  let rows=R.filter(x=>x.sym!=='BTC'&&(mF==='all'||(mF==='pool'&&x.pool)||(mF==='watch'&&x.watch)||(mF==='non'&&!x.pool&&!x.watch)));
  const col=MCOLS.find(c=>c[0]===mSort); rows.sort((a,b)=>{const x=col[2](a),y=col[2](b);if(!nz(x))return 1;if(!nz(y))return -1;return (x-y)*(mSort==='vrank'?-mDir:mDir)});
  const pill=(v,t)=>`<span class="pill ${mF===v?'on':''}" data-mf="${v}">${t}</span>`;
  const chip=s=>{const x=R.find(r=>r.sym===s);return `<span class="chip ${x&&x.pool?'in':''}" ${C[s]?`data-go="coin/${esc(s)}"`:''}>${esc(s)} ${x?fmtP(x.r30,0):''}</span>`};
  const ms=M.miss, np=R.filter(x=>x.pool).length;
  return `<div class="cgrid g4">${kp(L(`等权篮子 7 日（中位，前 ${M.n_basket}）`,`EW basket 7d (median, top ${M.n_basket})`),'r7')}${kp(L('等权篮子 30 日（中位）','EW basket 30d (median)'),'r30')}${kp(L('等权篮子 90 日（中位）','EW basket 90d (median)'),'r90')}
  <div class="ccard kpi"><div class="l">${L('观测池 对 篮子里的池外（中位）','Pool vs non-pool in basket (median)')}</div><div class="v" style="font-size:15px;line-height:1.55">30${L('日','d')} ${fmtP(B.r30.pool_med)} / ${fmtP(B.r30.non_med)}<br>90${L('日','d')} ${fmtP(B.r90.pool_med)} / ${fmtP(B.r90.non_med)}</div><div class="s">${L(`篮子里有 ${B.r30.n_pool} 个池内币；池是事后选的，90 日差距含后视偏差`,`${B.r30.n_pool} pool coins in basket; the pool was picked after the fact`)}</div></div></div>
  <div class="ccard"><h3>${L('错过记录：篮子里近 30 日最强前 15（看相对强弱）','Missed list: top 15 in the basket by 30d return')}</h3><div class="chips" style="margin:6px 0 8px">${ms.top15_30d.map(chip).join('')}</div>
  <div class="sm">${L(`前 15 里在观测池的：${ms.in_pool.join('、')||'无'}。绿框 = 观测池。近 7 日最强前 10：`,`In the pool: ${ms.in_pool.join(', ')||'none'}. Green border = pool. Top 10 over 7d: `)}${ms.top10_7d.map(esc).join('、')}。${L('每天重算；连续几周看，才能回答“只盯有收入的币会不会漏涨幅”。','Recomputed daily; only weeks of data can tell whether the pool misses the movers.')}</div></div>
  <div class="ccard"><div class="filters"><span class="sm">${L('范围','Scope')}</span>${pill('all',L('全部','All'))}${pill('pool',L('观测池','Pool'))}${pill('watch',L('观察标的','Watch'))}${pill('non',L('池外','Others'))}<span class="sm">${L(`现货成交额前 ${R.length} · 币安日线 · ${M.date}`,`Top ${R.length} by spot volume · Binance daily · ${M.date}`)}</span></div>
  <div class="scroll"><table><thead><tr><th>${L('标的','Asset')}</th><th>${L('收入线索（30 日）','Revenue clue (30d)')}</th>${MCOLS.map(c=>`<th data-ms="${c[0]}" class="${mSort===c[0]?'sorted':''}">${c[1]}${mSort===c[0]?(mDir<0?' ↓':' ↑'):''}</th>`).join('')}</tr></thead><tbody>`+
  rows.map(x=>`<tr ${C[x.sym]?`data-go="coin/${esc(x.sym)}"`:''}><td><b>${esc(x.sym)}</b>${x.pool?`<span class="tg pool">${L('观测池','Pool')}</span>`:x.watch?`<span class="tg">${L('观察','Watch')}</span>`:''}</td><td class="sm">${nz(x.rev30)&&x.rev30>0?'$'+fmtU(x.rev30,1):'—'}</td>
  <td class="${cls(x.r7)}">${fmtP(x.r7)}</td><td class="${cls(x.r30)}">${fmtP(x.r30)}</td><td class="${cls(x.r90)}">${fmtP(x.r90)}</td><td class="${cls(x.dd120)}">${fmtP(x.dd120)}</td><td class="${cls(x.vsMA200)}">${fmtP(x.vsMA200)}</td><td class="${cls(x.vol7v30)}">${fmtP(x.vol7v30)}</td><td>${fmtU(x.qv30,1)}</td><td>${x.vrank?'#'+x.vrank:'—'}</td></tr>`).join('')+`</tbody></table></div>
  <div class="sm" style="margin-top:8px">${L('币安现货 USDT 交易对，按 30 日均成交额取前列；已剔除稳定币、黄金、包装币和代币化美股 / ETF。收入线索 = DefiLlama 协议名单按代币符号匹配的近 30 日协议收入，待核；链本身的手续费（如 TRX）不等于持币人收入。近期涨幅不加分（规则 R4），这页用来防漏和对照基准，不是追涨清单。',
  'Binance USDT spot pairs ranked by 30-day average volume; stablecoins, gold, wrapped tokens and tokenized stocks/ETFs removed. Revenue clue = DefiLlama protocol revenue matched by ticker (unverified); chain fees (e.g. TRX) are not holder revenue. Recent gains earn no points (R4): this page is a benchmark and a miss-check, not a momentum list.')}</div></div>`;
}
function volume(){
  const V=D.market&&D.market.vol; if(!V)return `<div class="ccard empty">${L('成交额榜未取到。','Volume board missing.')}</div>`;
  const row=x=>`<tr ${C[x.sym]?`data-go="coin/${esc(x.sym)}"`:''}><td><b>${esc(x.sym)}</b>${C[x.sym]?`<span class="tg ${C[x.sym].track==='pool'?'pool':''}">${C[x.sym].track==='pool'?L('观测池','Pool'):L('观察','Watch')}</span>`:''}</td><td>#${x.cur||'—'}</td><td>${x.spot?'#'+x.spot:'—'}</td><td>${x.fut?'#'+x.fut:'—'}</td><td>#${x.med}</td><td>${x.d30}</td><td>${nz(x.fut_share_30d)?x.fut_share_30d.toFixed(0)+'%':'—'}</td><td>${fmtU(x.qv_today,1)}</td><td>${spark(x.spark.map(r=>r?-r:null),90,24,'var(--s3)')}</td></tr>`;
  const head=`<thead><tr><th>${L('标的','Asset')}</th><th>${L('合并排名','Combined')}</th><th>${L('现货','Spot')}</th><th>${L('永续','Perp')}</th><th>${L('90 天中位','90d median')}</th><th>${L('进前 30 天数','Days top-30')}</th><th>${L('永续占比 30 日','Perp share 30d')}</th><th>${L('当日成交额','Day volume')}</th><th>${L('近 30 天排名','Rank 30d')}</th></tr></thead>`;
  const tbl=(list,emp)=>list.length?`<div class="scroll"><table>${head}<tbody>${list.map(row).join('')}</tbody></table></div>`:`<div class="empty">${emp}</div>`;
  return `<div class="cgrid g4"><div class="ccard kpi"><div class="l">${L('全市场永续成交占比（当日）','Perp share of market volume (day)')}</div><div class="v">${nz(V.market_fut_share_pct)?V.market_fut_share_pct.toFixed(1)+'%':'—'}</div><div class="s">${L('现货','Spot')} ${V.universe.spot} · ${L('永续','Perps')} ${V.universe.fut} · ${V.last_day}</div></div>
  <div class="ccard kpi"><div class="l">${L('常客（≥ 80% 的天数在前 30）','Regulars (top 30 on ≥80% of days)')}</div><div class="v">${V.regulars.length}</div><div class="s">${L(`窗口 ${V.window_days} 天`,`${V.window_days}-day window`)}</div></div>
  <div class="ccard kpi"><div class="l">${L('新进榜','New entrants')}</div><div class="v">${V.entrants.length}</div><div class="s">${L('之前很少进前 30，最近 7 天 ≥ 2 次','rarely top 30 before, ≥2 times in last 7 days')}</div></div>
  <div class="ccard kpi"><div class="l">${L('掉榜','Dropped out')}</div><div class="v">${V.exits.length}</div><div class="s">${L('之前一半以上天数在前 30，最近 7 天 0 次','top 30 on half the days before, 0 in last 7')}</div></div></div>
  <div class="ccard"><h2>${L('新进榜','New entrants')}</h2>${tbl(V.entrants,L('今天没有。','None today.'))}</div>
  <div class="ccard"><h2>${L('掉榜','Dropped out')}</h2>${tbl(V.exits,L('今天没有。','None today.'))}</div>
  <div class="ccard"><h2>${L('成交额榜常客','Volume regulars')}</h2>${tbl(V.regulars,'—')}</div>
  <div class="ccard"><h2>${L(`当日合并成交额前 ${V.top.length}`,`Top ${V.top.length} by combined volume (day)`)}</h2>${tbl(V.top,'—')}
  <div class="sm" style="margin-top:8px">${L('现货 = 币安 USDT 现货对，永续 = U 本位永续（data.binance.vision 公开归档；1000PEPE 这类按 1 枚口径并回 PEPE），UTC 日成交额。已剔除稳定币、黄金、包装币和美股 / ETF（永续归档不带标的类型，所以只算现货也有 USDT 对的币，只有永续的币不进榜）。榜单代表流动性与热度，不是买入信号。',
  'Spot = Binance USDT pairs, perps = USDⓈ-M perpetuals (public archive at data.binance.vision; 1000PEPE etc. merged into PEPE), UTC daily volume. Stablecoins, gold, wrapped tokens and stocks/ETFs are removed (the archive has no underlying type, so only coins with a USDT spot pair are counted). Rank reflects liquidity and attention, not a buy signal.')}</div></div>`;
}
function method(){
  return `<div class="ccard"><h2>${L('口径与规则','Method & rules')}</h2>${EN?'<div class="note">Manual notes (narrative stage, unlocks, risks, findings) come from the research log and are in Chinese.</div>':''}
  <h3 style="margin-top:12px">${L('三个维度的数据','Data for the three angles')}</h3><ul class="plain">
  <li><b>${L('基本面','Fundamentals')}</b>：${L(`手续费 / 协议收入 / 持有人收入，DefiLlama 日度，UTC 整天。不同协议“收入”的定义可以相差数倍，先看口径再比较。业务量 = DEX 成交额或 TVL。供给与 FDV 取 CoinGecko，按币安收盘折算市值。`,'Fees / revenue / holder revenue from DefiLlama, UTC days; definitions differ across protocols. Activity = DEX volume or TVL. Supply and FDV from CoinGecko, valued at the Binance close.')}</li>
  <li><b>${L('资金面','Flows')}</b>：${L('币安现货成交额（7 日 / 30 日对比、换手率）；币安现货 + U 本位永续合并成交额排名、常客 / 新进榜 / 掉榜、永续占比；全市场等权篮子基准。','Binance spot volume (7d vs 30d, turnover); combined spot + perp volume rank, regulars / entrants / exits, perp share; equal-weight market basket.')}</li>
  <li><b>${L('技术面','Technicals')}</b>：${L('币安现货已收盘日线：MA20 / 50 / 200、RSI14（Wilder）、距 120 日高点、30 日区间位置。只展示，不计分。','Closed Binance spot daily candles: MA20/50/200, RSI14 (Wilder), drawdown from 120-day high, 30-day range position. Shown, not scored.')}</li>
  <li><b>${L('人工登记','Manual')}</b>：${L(`叙事阶段、回购口径、解锁、事件、证伪条件、风险记录、重大发现，来自研究笔记（最近核对 ${MAN.asof}），带来源强度；未登记的标“未核”，不当作“没有”。`,`Narrative stage, buyback notes, unlocks, events, falsification conditions, risks and findings from the research log (last checked ${MAN.asof}); not logged ≠ none.`)}</li></ul>
  <h3>${L('评分模块（全部【假设】，未回测）','Score modules (all hypotheses, not backtested)')}</h3><ul class="plain">
  <li><b>R ${L('收入趋势','Revenue trend')}</b>：${L('7 日均对 30 日均、30 日环比，取更差者；≥ +10% 得 3，≥ −10% 得 2，≥ −30% 得 1，否则 0。','worse of 7d-vs-30d and 30d-vs-prior-30d; ≥+10% → 3, ≥−10% → 2, ≥−30% → 1, else 0.')}</li>
  <li><b>C ${L('价值捕获','Value capture')}</b>：${L('30 日持有人收入 ÷ 协议收入；≥ 50% 得 3，≥ 20% 得 2，> 0 得 1，0 得 0。','30d holder revenue ÷ revenue; ≥50% → 3, ≥20% → 2, >0 → 1, 0 → 0.')}</li>
  <li><b>V ${L('估值','Valuation')}</b>：${L('市值 ÷ 年化持有人收入；< 15 得 3，< 30 得 2，< 60 得 1，否则或无持有人收入得 0。','mcap ÷ annualised holder revenue; <15 → 3, <30 → 2, <60 → 1, else 0.')}</li>
  <li><b>D ${L('价格 × 收入','Price × revenue')}</b>：${L('收入 30 日环比 − 价格 30 日涨跌；≥ +20pp 得 3，≥ −20pp 得 2，≥ −50pp 得 1，否则 0。','revenue 30d change − price 30d change; ≥+20pp → 3, ≥−20pp → 2, ≥−50pp → 1, else 0.')}</li>
  <li><b>B ${L('业务量','Activity')}</b>：${L('同 R 的阈值，取业务量。','same bands as R, on activity.')}</li>
  <li><b>S ${L('供给','Supply')}</b>：${L('只对登记过解锁的币；30 日解锁占流通量 < 0.5% 得 3，< 2% 得 2，< 5% 得 1，否则 0。','only where unlocks are logged; 30d unlock < 0.5% of float → 3, < 2% → 2, < 5% → 1, else 0.')}</li></ul>
  <h3>${L('建仓条件检查与风险提示','Entry checklist & risk alerts')}</h3><ul class="plain">
  <li>${L('三道闸门读本站数据：闸门 1 = L2 周期状态（熊底区或熊末→牛初才过）；闸门 2 = BTC 收盘高于本轮最低收盘；闸门 3 = L1 净流动性闸门（13 周 ≤ −2.72% 且美元走强才触发，只打折不加仓）。','Three gates read this site: Gate 1 = L2 cycle state (passes only in bear-bottom zone or late bear → early bull); Gate 2 = BTC close above the cycle-low close; Gate 3 = L1 net-liquidity gate (trips at ≤ −2.72% over 13w with a stronger dollar; discount only).')}</li>
  <li>${L('R1 六问卡、R2 解锁、R3 价格不跑在收入前面、R4 近期强势不加分、R6 渠道 B 平台收入转正。有一条硬条件不过就标“有硬条件未过”。','R1 six-question card, R2 unlocks, R3 price not ahead of revenue, R4 no points for recent strength, R6 channel-B revenue turning up. Any hard failure flags the asset.')}</li>
  <li>${L('“条件齐备”只表示可以进入人工建仓评估，不是买入信号；风险提示同理，不是卖出指令。','“Conditions met” only means the asset can go to manual entry review, not a buy signal; risk alerts are not sell orders.')}</li></ul>
  <h3>${L('待补维度','To add')}</h3><ul class="plain"><li>${L('代币激励与收益（收入 − 激励）、日活用户、核心开发者、国库、供给侧手续费：待接入。','Token incentives / earnings, DAU, core developers, treasury, supply-side fees: pending.')}</li></ul>
  ${D.errors&&D.errors.length?`<h3>${L('本次取数问题','Fetch issues this run')}</h3><ul class="plain">${D.errors.slice(0,20).map(e=>`<li>${esc(e)}</li>`).join('')}</ul>`:''}</div>`;
}
const VIEWS={home,rank,market,volume,alerts,findings,method};
const TABS=[['home',L('总观测台','Overview')],['rank',L('排行榜','Ranking')],['volume',L('成交额榜','Volume board')],['market',L('全市场','Market')],['alerts',L('风险提示','Risk alerts')],['findings',L('重大发现','Findings')],['method',L('口径与规则','Method')]];
function render(){
  const h=(location.hash||'#home').slice(1); const [p,arg]=h.split('/');
  root.querySelectorAll('.ctabs a').forEach(a=>a.classList.toggle('on',a.dataset.p===(p==='coin'?'rank':p)));
  $('#cview').innerHTML=p==='coin'?coin(decodeURIComponent(arg||'')):(VIEWS[p]||home)();
}
root.addEventListener('click',e=>{
  const g=e.target.closest('[data-go]');if(g){location.hash='#'+g.dataset.go;window.scrollTo(0,root.offsetTop-10);return}
  const n=e.target.closest('.ctabs a');if(n){e.preventDefault();location.hash='#'+n.dataset.p;return}
  const mf=e.target.closest('[data-mf]');if(mf){mF=mf.dataset.mf;render();return}
  const ms=e.target.closest('th[data-ms]');if(ms){const k=ms.dataset.ms;if(mSort===k)mDir*=-1;else{mSort=k;mDir=-1}render();return}
  const f=e.target.closest('[data-f]');if(f){const [a,b]=f.dataset.f.split(':');if(a==='tier')fTier=b;else fTag=b;render();return}
  const s=e.target.closest('th[data-s]');if(s){const k=s.dataset.s;if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=k==='vr'?1:-1}render()}
});
fetch(src).then(r=>r.json()).then(d=>{
  D=d;C=d.coins;SYMS=Object.keys(C);MAN=d.manual||{};GT=d.gates||{};
  const stale=(Date.now()-Date.parse(d.last_complete_day+'T00:00:00Z'))/864e5>3.5;
  root.innerHTML=`<div class="sm">${L('数据日','Data day')} ${d.last_complete_day}（UTC）· ${L('生成于','built')} ${esc(d.generated)}${stale?` · <b style="color:var(--warn)">${L('停更：数据超过 3 天没更新','Stale: no update for 3+ days')}</b>`:''}</div>
  <nav class="ctabs">${TABS.map(t=>`<a href="#${t[0]}" data-p="${t[0]}">${t[1]}</a>`).join('')}</nav><div id="cview"></div>`;
  window.addEventListener('hashchange',render); render();
}).catch(()=>{root.innerHTML=`<div class="empty">${L('数据加载失败，稍后刷新。','Failed to load data; refresh later.')}</div>`});
})();
