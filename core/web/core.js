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


/* ---------- 规则说明（大白话，11-14 大叔要求：读者看得懂、自己隔久了也记得住） ---------- */
const WHY={
 g1:L('BTC 在大周期的哪个阶段（本站宏观页 L2 状态机）。只有「熊底区」或「熊末→牛初」才算过：历史上这两个阶段之后一年大多是涨的；牛市后段、熊市中段不新开埋伏仓。',
      'Where BTC sits in the big cycle (L2 state machine on the Macro page). Passes only in the bear-bottom zone or late bear → early bull, which historically led to mostly positive years; no new ambush positions late in a bull or mid-bear.'),
 g2:L('BTC 收盘要在本轮最低收盘上方。跌破说明“底部已过”的判断失效，按方法论停止加仓。','BTC must close above this cycle’s lowest close. A break invalidates the “bottom is in” view; stop adding.'),
 g3:L('美联储净流动性（资产 − 财政部账户 − 逆回购）13 周跌超 2.72% 且美元同时走强才触发。触发后不是不能买，而是整体仓位打七折；扩张时也不因此加仓（只打折不加仓）。','Fed net liquidity (assets − TGA − RRP) down more than 2.72% over 13 weeks with a stronger dollar. When tripped, total risk is cut to 70%; expansion never adds.'),
 R1:L('《核心选币方法论》第 4 层：每个候选币在建仓前要写完一张“六问卡”（六个问题的原文待大叔补进来）。这里只记录写没写，没写就算条件未齐。','Method layer 4: each candidate needs a completed “six-question card” before entry (question list to be added). Only tracks whether it is written.'),
 R2:L('未来 30 天的解锁 / 增发不能超过流通量的 5%。大额解锁 = 一次性新增卖压，常常在解锁前后压住价格。','Unlocks / emissions over the next 30 days must stay below 5% of float: a large unlock is a one-off wave of new supply.'),
 R3:L('过去 30 天价格涨幅减去协议收入环比，差距超过 30 个百分点就算“价格跑在收入前面”：涨的是预期不是业绩（HYPE 从 2026-03 起就是这样）。','If the 30-day price change exceeds the 30-day revenue change by more than 30 points, price is running ahead of the business (HYPE since March 2026).'),
 R4:L('回测过：点火前 30 / 60 天相对 BTC 最强的那批币，之后并没有跑赢等权篮子（17 个窗口、56 个币）。所以这里不因为“最近涨得好”加分，技术形态只展示。','Backtested: the coins strongest vs BTC 30/60 days before ignition did not beat the equal-weight basket (17 windows, 56 coins), so recent strength earns nothing here.'),
 R6:L('发射台类（渠道 B，如 PUMP）的价值来自平台手续费：平台收入 7 日均要高于 30 日均（在回升）才算过。','Launchpad tokens (channel B, e.g. PUMP) live on platform fees: the 7-day revenue average must be above the 30-day average.')
};
const MOD_WHY={
 R:L('收入在变多还是变少：最近 7 天日均对 30 天日均、最近 30 天对前 30 天，取更差的那个。≥ +10% 得 3 分，≥ −10% 得 2，≥ −30% 得 1，更差 0 分。','Is revenue growing: worse of 7-day vs 30-day average and last 30 vs prior 30 days. ≥+10% → 3, ≥−10% → 2, ≥−30% → 1, else 0.'),
 C:L('协议赚的钱有多少真正到了持币人手里（回购、销毁、分红）：持有人收入 ÷ 协议收入。≥ 50% 得 3，≥ 20% 得 2，> 0 得 1，0 得 0。','How much of revenue reaches holders (buyback / burn / dividends): holder revenue ÷ revenue. ≥50% → 3, ≥20% → 2, >0 → 1, 0 → 0.'),
 V:L('贵不贵：市值 ÷ 年化持有人收入（类似市盈率）。< 15 倍得 3，< 30 得 2，< 60 得 1，更贵或持有人收入为 0 得 0。','Valuation: market cap ÷ annualised holder revenue (a P/E). <15× → 3, <30× → 2, <60× → 1, else 0.'),
 D:L('价格和收入谁跑得快：收入 30 天环比 − 价格 30 天涨跌。收入领先 ≥ 20 个百分点得 3，在 ±20 之间得 2，价格领先 20–50 得 1，领先更多 0。','Price vs revenue: revenue 30-day change minus price 30-day change. ≥+20pp → 3, within ±20 → 2, −20 to −50 → 1, worse → 0.'),
 B:L('业务量在变多还是变少（DEX 成交额或 TVL），阈值同 R。','Is activity (DEX volume or TVL) growing; same bands as R.'),
 S:L('未来 30 天解锁占流通量：< 0.5% 得 3，< 2% 得 2，< 5% 得 1，更多 0。只对人工登记过解锁的币打分。','30-day unlock as % of float: <0.5% → 3, <2% → 2, <5% → 1, else 0. Only where unlocks are logged.')
};
const BT_LAB={'已验证·方向':L('回测：方向有效','Backtest: works (direction)'),'已证伪':L('回测：已证伪','Backtest: falsified'),'未通过':L('回测：未通过','Backtest: not significant'),'样本不足':L('回测：样本不足','Backtest: too few samples')};
const btTag=k=>{const b=BT&&BT.modules&&BT.modules[k];if(!b)return `<span class="tg">${L('未检验','untested')}</span>`;const v=b.verdict;return `<span class="tg ${v==='已验证·方向'?'pool':''}" style="${v==='已证伪'?'border-color:var(--dn-bd);color:var(--dn)':''}">${BT_LAB[v]||esc(v)}</span>`};
let BT=null, ROT=null;

/* ---------- 规则判定（原型同一套，闸门 1 / 3 改读本站 L2 与 L1 数据） ---------- */
function gates(){
  const r=[]; const g=GT||{};
  if(g.l2&&g.l2.code)r.push({w:'g1',id:L('闸门1','Gate 1'),t:L('L2 周期在熊底区或熊末→牛初','L2 cycle in bear-bottom zone or late bear → early bull'),k:g.l2.ok?'good':'crit',x:`${EN?g.l2.name_en:g.l2.name_zh}（${L('自','since')} ${g.l2.since}）`});
  else r.push({w:'g1',id:L('闸门1','Gate 1'),t:L('L2 周期在熊底区或熊末→牛初','L2 cycle state'),k:'na',x:L('L2 数据未取到','L2 data missing')});
  const fl=(MAN&&MAN.btc_floor)||58525, ok=D.btc.last>fl;
  r.push({w:'g2',id:L('闸门2','Gate 2'),t:L(`BTC 收盘 > ${fl.toLocaleString()}（本轮最低收盘）`,`BTC close > ${fl.toLocaleString()} (cycle-low close)`),k:ok?'good':'crit',x:`BTC ${Math.round(D.btc.last).toLocaleString()}（${D.btc.date}）`});
  if(g.liq&&nz(g.liq.netliq))r.push({w:'g3',id:L('闸门3','Gate 3'),t:L('净流动性闸门未触发','Net-liquidity gate not tripped'),k:g.liq.tripped?'serious':'good',
    x:L(`净流动性 13 周 ${fmtP(g.liq.netliq,2)}（${g.liq.asof}）；美元 13 周 ${fmtP(g.liq.usd,2)}。≤ −2.72% 且美元走强才触发（只打折不加仓）`,`Net liquidity 13w ${fmtP(g.liq.netliq,2)} (${g.liq.asof}); dollar 13w ${fmtP(g.liq.usd,2)}. Trips only at ≤ −2.72% with a stronger dollar (discount only)`)});
  else r.push({w:'g3',id:L('闸门3','Gate 3'),t:L('净流动性闸门','Net-liquidity gate'),k:'na',x:L('未取到','missing')});
  return r;
}
function checks(c){
  const r=gates(); const fr=c.fees.revenue, pr=c.price, u=c.unlock;
  r.push({w:'R1',id:'R1',t:L('六问卡写完（建仓前的六个问题）','Six-question card written'),k:'na',x:(MAN.sixq||{})[c.sym]||(c.track==='watch'?L('观察标的，未入候选','watch item, not a candidate'):L('未写','not written'))});
  if(u&&nz(u.pct_circ))r.push({w:'R2',id:'R2',t:L('30 日内无 ≥5% 流通量解锁','No ≥5% float unlock within 30 days'),k:u.pct_circ<5?'good':'crit',x:`${L('约','≈')} ${u.pct_circ.toFixed(2)}%（${esc(u.note)}）`});
  else r.push({w:'R2',id:'R2',t:L('30 日内无 ≥5% 流通量解锁','No ≥5% float unlock within 30 days'),k:c.under5?'good':'na',x:c.under5?L('已查未见 ≥5%（具体值未取）','checked, none ≥5% (exact size not fetched)'):L('未核','not checked')});
  if(pr&&fr&&nz(fr.mom30)&&nz(pr.ret30)){const g=pr.ret30-fr.mom30;r.push({w:'R3',id:'R3',t:L('价格没有跑在收入前面','Price not running ahead of revenue'),k:g>30?'serious':'good',x:L(`价格 30 日 ${fmtP(pr.ret30)}；收入 30 日环比 ${fmtP(fr.mom30)}；差 ${fmtP(g)}pp（> 30pp 算跑在前面）`,`Price 30d ${fmtP(pr.ret30)}; revenue 30d ${fmtP(fr.mom30)}; gap ${fmtP(g)}pp (>30pp = ahead)`)})}
  else r.push({w:'R3',id:'R3',t:L('价格没有跑在收入前面','Price not running ahead of revenue'),k:'na',x:L('缺收入或价格','missing revenue or price')});
  r.push({w:'R4',id:'R4',t:L('近期强势不加分','Recent strength earns no points'),k:'good',x:L('评分不含价格强弱；技术形态只展示（回测：点火前相对 BTC 最强的五分之一没有跑赢篮子）','Score excludes price strength; technicals shown only (backtest: the strongest fifth vs BTC before ignition did not beat the basket)')});
  if(c.tag==='channelB'){const w=fr?fr.d7v30:null;r.push({w:'R6',id:'R6',t:L('渠道 B：平台收入 7 日均转正','Channel B: platform revenue 7d avg turning up'),k:nz(w)&&w>0?'good':'crit',x:L(`收入 7 日均对 30 日均 ${fmtP(w)}`,`Revenue 7d vs 30d ${fmtP(w)}`)})}
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
  <div class="ccard"><h2>${L('资金面 · 币安成交额排名','Flows · Binance volume rank')}</h2>${volCard(c)}</div>
  <div class="ccard"><h2>${L('日活用户（基本面）','Daily active users (fundamentals)')}</h2><div id="ch6"></div>${c.users?`<div class="sm">${L('7 日均 / 30 日均','7d / 30d avg')} ${fmtU(c.users.avg7,1)} / ${fmtU(c.users.avg30,1)}（${fmtP(c.users.d7v30)}）· ${L('30 日环比','30d change')} ${fmtP(c.users.mom30)} · DefiLlama</div>`:''}</div>
  <div class="ccard"><h2>${L('上一轮 BTC 拉升里的表现（拉盘复盘）','In the last BTC rally (replay)')}</h2><div id="rotc">${rotCard(c)}</div></div></div>
  <div class="cgrid g2"><div class="ccard"><h2>${L('国库','Treasury')}</h2>${treasCard(c)}</div><div class="ccard"><h2>${L('核心开发者（GitHub）','Core developers (GitHub)')}</h2>${devCard(c)}</div></div>`;
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('技术形态','Technicals')}</h2><table class="kv"><tbody>
  <tr><td>${L('形态','Pattern')}</td><td>${p?trend(p.trend):'—'}</td></tr><tr><td>MA20 / MA50</td><td>${p?fmtPx(p.ma20)+' / '+fmtPx(p.ma50):'—'}</td></tr><tr><td>MA200</td><td>${p&&p.ma200?fmtPx(p.ma200)+'（'+fmtP(p.vsMA200)+'）':L('历史不足 200 天','<200 days of history')}</td></tr>
  <tr><td>RSI14</td><td>${p&&nz(p.rsi14)?p.rsi14.toFixed(0):'—'}</td></tr><tr><td>${L('距 120 日高点','vs 120-day high')}</td><td class="${cls(p&&p.dd120)}">${fmtP(p&&p.dd120)}</td></tr><tr><td>${L('30 日区间位置','30-day range position')}</td><td>${p&&nz(p.pos30)?p.pos30.toFixed(0)+'%'+L('（0 = 区间低点）',' (0 = range low)'):'—'}</td></tr>
  <tr><td>${L('成交额 7 日均 / 30 日均','Volume 7d / 30d avg')}</td><td>${p?fmtU(p.vol7)+' / '+fmtU(p.vol30)+'（'+fmtP(p.vol7v30)+'）':'—'}</td></tr><tr><td>${L('30 日换手（成交额 / 市值）','30d turnover (volume / mcap)')}</td><td>${v&&nz(v.turnover30)?v.turnover30.toFixed(0)+'%':'—'}</td></tr></tbody></table>
  <div class="sm" style="margin-top:6px">${L('技术形态只展示，不进评分（规则 R4：近期强势不加分）。','Technicals are shown, not scored (rule R4).')}</div></div>
  <div class="ccard"><h2>${L('估值与收入质量','Valuation & revenue quality')}</h2><table class="kv"><tbody>
  <tr><td>${L('市值 / 年化协议收入','Mcap / ann. revenue')}</td><td>${fmtX(v&&v.p_rev)}</td></tr><tr><td>${L('FDV / 年化协议收入','FDV / ann. revenue')}</td><td>${fmtX(v&&v.p_rev_fd)}</td></tr><tr><td>${L('市值 / 年化持有人收入','Mcap / ann. holder revenue')}</td><td>${fmtX(v&&v.p_hr)}</td></tr><tr><td>${L('持有人收入年化收益率','Holder revenue yield')}</td><td>${v&&nz(v.hr_yield)?v.hr_yield.toFixed(1)+'%':'—'}</td></tr>
  <tr><td>${L('手续费 / 收入 / 持有人 7v30','Fees / rev / holders 7v30')}</td><td>${fmtP(ff&&ff.d7v30)} / ${fmtP(fr&&fr.d7v30)} / ${fmtP(fh&&fh.d7v30)}</td></tr>
  <tr><td>${L('供给侧收入（付给 LP / 存款人）30 日','Supply-side revenue 30d (to LPs / lenders)')}</td><td>${fmtU(c.fees.supply&&c.fees.supply.sum30)}${c.fees.supply&&nz(c.fees.supply.d7v30)?'（7v30 '+fmtP(c.fees.supply.d7v30)+'）':''}</td></tr>
  <tr><td>${L('代币激励 / 收益（收入 − 激励）','Incentives / earnings')}</td><td class="sm">${L('待接入：免费数据源没有协议激励排放（DefiLlama emissions、Token Terminal 都要付费）。替代看“30 日解锁价值 vs 持有人收入”。','Pending: no free source for token incentives (DefiLlama emissions and Token Terminal are paid). See unlock value vs holder revenue instead.')}</td></tr>
  ${c.unlock&&nz(c.unlock.usd)&&c.unlock.usd>0?`<tr><td>${L('30 日解锁价值 vs 持有人收入','30d unlock value vs holder revenue')}</td><td>${fmtU(c.unlock.usd)} vs ${fmtU(fh?fh.sum30:0)}${nz(c.unlock.cover_paper)?'（'+L('覆盖','cover')+' '+(c.unlock.cover_paper*100).toFixed(0)+'%）':''}</td></tr>`:''}</tbody></table>
  ${c.sym==='NEAR'?`<div class="sm" style="margin-top:6px">${L('NEAR：收入口径仅为 Intents，对整个 NEAR 市值的倍数偏高，仅作参考。','NEAR: revenue is Intents only, so multiples vs the whole NEAR cap read high.')}</div>`:''}</div></div>`;
  h+=supplyCard(c);
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('基本面评分（假设）','Fundamental score (hypothesis)')}</h2>${c.sc.mods.map(m=>`<div class="mod"><span class="k">${m.k}</span><span>${esc(m.n)}<br>${btTag(m.k)}</span><span class="sm">${esc(m.why)}<details class="why"><summary>${L('怎么打分','How it scores')}</summary>${MOD_WHY[m.k]||''}</details></span><b>${m.s===null?'—':m.s}</b></div>`).join('')}
  <div class="sm" style="margin-top:6px">${L('每项 0–3 分；综合分 = 已评模块得分 ÷（3 × 已评模块数）。未评模块不扣分，综合分只作排序用。','Each 0–3; total = points ÷ (3 × modules scored). Unscored modules are skipped; the total is for sorting only.')}</div></div>
  <div class="ccard"><h2>${L('建仓条件检查','Entry condition check')}</h2>${checks(c).map(x=>`<div class="mod mod2"><b style="text-align:left">${x.id}</b><div>${stat(x.k,esc(x.t))}<div class="sm">${x.x}</div>${x.w&&WHY[x.w]?`<details class="why"><summary>${L('这条是什么','What is this')}</summary>${WHY[x.w]}</details>`:''}</div></div>`).join('')}
  <div class="sm" style="margin-top:6px">${L('判定怎么来的：闸门 1 / 2、R2、R6 有一条不过，或闸门 3 触发、R3 亮橙，就是“有硬条件未过”；没有硬伤但有一条没写或没数据，是“条件未齐”；全部通过才是“条件齐备”——只代表可以进入人工建仓评估，不是买入信号。','How the verdict works: any failure on gates 1/2, R2, R6, or gate 3 / R3 flagged → “hard condition failing”; nothing failing but something unwritten or missing → “incomplete”; all pass → “conditions met”, which only means ready for manual review, not a buy signal.')}</div>
  <div class="sm" style="margin-top:6px">${L('失效规则（大叔方法论，不在此页判定）：90 天内无 T1 信号减半；较平均成本 −30% 清仓；BTC 收盘跌破本轮最低收盘停止加仓。埋伏仓不宜用窄止损（点火前回撤中位 −11.5%，最深 −23%）。','Exit rules (from the method, not judged here): halve if no T1 signal within 90 days; exit at −30% vs average cost; stop adding if BTC closes below the cycle low. Ambush positions should not use tight stops (pre-ignition pullback median −11.5%, worst −23%).')}</div></div></div>`;
  h+=`<div class="cgrid g2"><div class="ccard"><h2>${L('风险提示 · 证伪 / 降级条件','Risk · falsification / downgrade')}</h2>${man.length?man.map(f=>`<div class="mod mod1"><div>${stat(f.k,esc(f.t))}<div class="sm">${esc(f.x)}</div></div></div>`).join(''):''}${rk.map(f=>`<div class="mod mod1"><div>${stat('serious',esc(f.cat)+'：'+esc(f.t))}<div class="sm">${L('人工登记','manual log')} ${esc(f.asof)}</div></div></div>`).join('')}${!man.length&&!rk.length?`<div class="empty">${L('尚未登记。','Nothing logged yet.')}</div>`:''}</div>
  <div class="ccard"><h2>${c.sym} ${L('相关消息','alerts')}</h2>${ALL(true).filter(e=>e.s===k).map(alertHTML).join('')||`<div class="empty">${L('暂无。','None.')}</div>`}</div></div>`;
  setTimeout(()=>drawCoin(c),0);
  if(!ROT)fetch(root.dataset.rot+'?v='+D.last_complete_day).then(r=>r.json()).then(x=>{ROT=x;const el=$('#rotc');if(el)el.innerHTML=rotCard(c)}).catch(()=>{});
  return h;
}
function treasCard(c){
  const t=c.treasury; if(!t)return `<div class="empty">${L('DefiLlama 没有这个协议的国库数据。','No treasury data on DefiLlama.')}</div>`;
  return `<table class="kv"><tbody><tr><td>${L('国库总额','Total')}</td><td><b>$${fmtU(t.total)}</b></td></tr><tr><td>${L('其中自家代币','Own token')}</td><td>$${fmtU(t.own)}（${nz(t.own_pct)?t.own_pct.toFixed(0)+'%':'—'}）</td></tr>
  <tr><td>${L('其余（稳定币 / 主流币等）','Other (stables / majors)')}</td><td>$${fmtU(t.other)}</td></tr>${c.val&&c.val.mcap?`<tr><td>${L('非自家代币部分 ÷ 市值','Non-own treasury ÷ mcap')}</td><td>${(t.other/c.val.mcap*100).toFixed(1)}%</td></tr>`:''}</tbody></table>
  <div class="sm" style="margin-top:6px">${L('自家代币占比高的国库，币价跌时会一起缩水；“其余”部分才是真正的弹药。DefiLlama，每周更新。','A treasury heavy in its own token shrinks with the price; the “other” part is the real buffer. DefiLlama, weekly.')}</div>`;
}
function devCard(c){
  const d=c.dev; if(!d)return `<div class="empty">${L('DefiLlama 没有登记这个协议的 GitHub。','No GitHub org listed on DefiLlama.')}</div>`;
  if(d.pending)return `<div class="empty">${L(`待接入：GitHub 组织 ${esc((d.orgs||[]).join('、'))}，下一次日更（Actions 带 GitHub 权限）开始取。`,`Pending: GitHub org ${esc((d.orgs||[]).join(', '))}; starts with the next daily run.`)}</div>`;
  return `<table class="kv"><tbody><tr><td>${L('近 30 天提交过代码的人','Developers with commits, 30d')}</td><td><b>${d.devs30}</b>（${L('前 30 天','prior 30d')} ${d.devs_prev30}）</td></tr><tr><td>${L('近 30 天提交数','Commits, 30d')}</td><td>${d.commits30}</td></tr>
  <tr><td>${L('统计范围','Scope')}</td><td class="sm">${esc((d.orgs||[]).join('、'))} · ${L(`最近活跃的 ${d.repos} 个公开仓库`,`${d.repos} most recently active public repos`)}</td></tr></tbody></table>
  <div class="sm" style="margin-top:6px">${L('按作者去重、剔除机器人；只看公开仓库，闭源开发看不到。每周更新。','Unique authors, bots removed; public repos only. Weekly.')}</div>`;
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
    if(f){const ser=[{n:L('手续费','Fees'),c:'var(--s1)',v:f.fees,w:1.6}];if(f.revenue.some(nz))ser.push({n:L('协议收入','Revenue'),c:'var(--s2)',v:f.revenue});if(f.holders.some(nz))ser.push({n:L('持有人收入','Holder revenue'),c:'var(--s3)',v:f.holders});if(f.supply&&f.supply.some(nz))ser.push({n:L('供给侧收入','Supply-side'),c:'var(--s7)',v:f.supply,w:1.2,dash:true});lineChart($('#ch3'),f.dates,ser,{h:210,zero:true,title:'fees'})}
    else $('#ch3').innerHTML=`<div class="empty">${L('没有协议收入数据（DefiLlama 无此协议的费用口径）。','No fee / revenue data on DefiLlama.')}</div>`;
    if($('#ch6')){if(s.users)lineChart($('#ch6'),s.users.dates,[{n:L('日活','DAU'),c:'var(--s1)',v:s.users.vals,w:1.3},{n:L('7 日均','7d avg'),c:'var(--s2)',v:sma(s.users.vals,7),w:2}],{h:190,zero:true,title:'users'});else $('#ch6').innerHTML=`<div class="empty">${L('DefiLlama 没有这个协议的日活数据。','No active-user data on DefiLlama.')}</div>`}
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
  const bs=M.basket_src||{};
  const bnote=bs.src==='leg'?L(`等权篮子 = 宏观页「山寨整体」同一个篮子（${M.n_basket} 个币：币安成交额前 50 名进篮、跌出 75 名出篮，每月 1 日重排，不含 BTC / ETH / 稳定币 / 代币化股票）。<a href="/macro/">去宏观页看山寨整体涨跌腿 →</a>`,`Equal-weight basket = the same basket as “Altcoins overall” on the Macro page (${M.n_basket} coins: enter at Binance volume top 50, leave below 75, rebalanced monthly; ex BTC/ETH/stables/tokenized stocks). <a href="/en/macro/">Macro page →</a>`)
    :L('宏观页山寨篮子读不到，今天临时用 USDT 现货成交额前 50 代替。','Macro basket unavailable today; fell back to the top 50 by USDT spot volume.');
  return `<div class="note" style="background:var(--cool-bg);border-color:var(--cool-bd)">${bnote}</div><div class="cgrid g4">${kp(L(`等权篮子 7 日（中位，${M.n_basket} 个币）`,`EW basket 7d (median, ${M.n_basket} coins)`),'r7')}${kp(L('等权篮子 30 日（中位）','EW basket 30d (median)'),'r30')}${kp(L('等权篮子 90 日（中位）','EW basket 90d (median)'),'r90')}
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
const VTAG={regular:[L('常客','Regular'),L('近 90 天里至少 80% 的日子在前 30','top 30 on ≥80% of the last 90 days')],
 entrant:[L('新进榜','New entrant'),L('之前很少进前 30（≤ 3 天），最近 7 天进了 ≥ 2 次，现在在前 50','rarely top 30 before (≤3 days), ≥2 times in the last 7, now top 50')],
 exit:[L('掉榜','Dropped'),L('之前一半以上日子在前 30，最近 7 天一次没进','top 30 on half the earlier days, none in the last 7')],
 new:[L('新上','New listing'),L('90 天窗口内才开始有成交','started trading inside the 90-day window')]};
const vtagHTML=ts=>(ts||[]).map(t=>`<span class="tg vt-${t}" title="${esc(VTAG[t][1])}">${VTAG[t][0]}</span>`).join('');
let vF='all',vSort='cur',vDir=1,vN=100;
function volume(){
  const V=D.market&&D.market.vol; if(!V)return `<div class="ccard empty">${L('成交额榜未取到。','Volume board missing.')}</div>`;
  const VC=[['cur',L('合并排名','Rank'),x=>x.cur,1],['spot',L('现货排名','Spot'),x=>x.spot,1],['fut',L('合约排名','Futures'),x=>x.fut,1],['med',L('90 天中位','90d median'),x=>x.med,1],
   ['d30',L('进前 30 天数','Days top-30'),x=>x.d30,-1],['fs',L('合约占比 30 日','Futures share 30d'),x=>x.fut_share_30d,-1],['qv',L('当日成交额','Day volume'),x=>x.qv_today,-1],['qv30',L('30 日日均','30d avg'),x=>x.qv30,-1]];
  let rows=V.rows.filter(x=>vF==='all'?x.cur&&x.cur<=150:vF==='pool'?C[x.sym]:(x.tags||[]).includes(vF));
  const col=VC.find(c=>c[0]===vSort); rows.sort((a,b)=>{const x=col[2](a),y=col[2](b);if(!nz(x))return 1;if(!nz(y))return -1;return (x-y)*vDir});
  const more=rows.length>vN; rows=rows.slice(0,vN);
  const cnt=V.counts||{}; const pill=(v,t,n)=>`<span class="pill ${vF===v?'on':''}" data-vf="${v}">${t}${n!=null?` <b>${n}</b>`:''}</span>`;
  const cov=V.coverage||{};
  return `<div class="cgrid g4"><div class="ccard kpi"><div class="l">${L('币安全市场当日成交额（现货 + 合约）','Binance total volume (spot + futures, day)')}</div><div class="v">$${fmtU(V.total_today)}</div><div class="s">${V.last_day}（UTC）</div></div>
  <div class="ccard kpi"><div class="l">${L('其中合约占比','Futures share')}</div><div class="v">${nz(V.market_fut_share_pct)?V.market_fut_share_pct.toFixed(1)+'%':'—'}</div><div class="s">${L(`覆盖 ${V.universe.coins} 个币`,`${V.universe.coins} coins covered`)}</div></div>
  <div class="ccard kpi"><div class="l">${L('新进榜 / 掉榜','Entrants / dropped')}</div><div class="v">${cnt.entrant||0} / ${cnt.exit||0}</div><div class="s">${L(`常客 ${cnt.regular||0} 个 · 窗口 ${V.window_days} 天`,`${cnt.regular||0} regulars · ${V.window_days}-day window`)}</div></div>
  <div class="ccard kpi"><div class="l">${L('观测池在榜','Pool coins on the board')}</div><div class="v">${V.rows.filter(x=>C[x.sym]&&x.cur&&x.cur<=50).length} / ${SYMS.length}</div><div class="s">${L('进合并前 50 的观测 / 观察标的','pool / watch names in the top 50')}</div></div></div>
  <div class="ccard"><div class="filters"><span class="sm">${L('筛选','Filter')}</span>${pill('all',L('前 150','Top 150'))}${pill('regular',VTAG.regular[0],cnt.regular)}${pill('entrant',VTAG.entrant[0],cnt.entrant)}${pill('exit',VTAG.exit[0],cnt.exit)}${pill('new',VTAG.new[0],cnt.new)}${pill('pool',L('观测池 + 观察','Pool + watch'))}</div>
  <div class="scroll"><table><thead><tr><th>${L('币','Coin')}</th><th style="text-align:left">${L('标签','Tags')}</th>${VC.map(c=>`<th data-vs="${c[0]}" class="${vSort===c[0]?'sorted':''}">${c[1]}${vSort===c[0]?(vDir>0?' ↑':' ↓'):''}</th>`).join('')}<th>${L('近 30 天排名','Rank 30d')}</th></tr></thead><tbody>`+
  rows.map(x=>`<tr ${C[x.sym]?`data-go="coin/${esc(x.sym)}"`:''}><td><b>${esc(x.sym)}</b>${C[x.sym]?`<span class="tg ${C[x.sym].track==='pool'?'pool':''}">${C[x.sym].track==='pool'?L('观测池','Pool'):L('观察','Watch')}</span>`:''}</td><td style="text-align:left">${vtagHTML(x.tags)}</td>
  <td><b>${x.cur?'#'+x.cur:'—'}</b></td><td>${x.spot?'#'+x.spot:'—'}</td><td>${x.fut?'#'+x.fut:'—'}</td><td>#${x.med}</td><td>${x.d30}</td><td>${nz(x.fut_share_30d)?x.fut_share_30d.toFixed(0)+'%':'—'}</td><td>${fmtU(x.qv_today,1)}</td><td>${fmtU(x.qv30,1)}</td><td>${spark((x.spark||[]).map(r=>r?-r:null),90,24,'var(--s3)')}</td></tr>`).join('')+`</tbody></table></div>
  ${more?`<div style="margin-top:8px"><span class="pill" data-vmore="1">${L('显示更多','Show more')}</span></div>`:''}
  <details class="why" style="margin-top:10px"><summary>${L('这张榜怎么算的','How this board is built')}</summary>
  ${L(`<p>一个币的成交额 = 币安上这个币<b>所有市场</b>当天（UTC）成交额之和，折成美元：</p><ul class="plain"><li>现货：全部计价对（${(cov.quotes||[]).join('、')}），计价币按当天收盘折美元，稳定币也按它自己对 USDT 的价格折；</li><li>合约：U 本位（USDT、USDC 保证金，永续 + 交割，共 ${(cov.contracts||{}).um||'—'} 个）+ 币本位（${(cov.contracts||{}).cm||'—'} 个，按标的币数 × 当天收盘折美元）；1000PEPE 这类按 1 枚口径并回原币。</li></ul><p>和币安 App 里的“成交额榜”不完全一样：App 是按<b>单个交易对</b>、滚动 24 小时排的；这里按<b>币</b>把所有交易对加起来、按 UTC 自然日算，才能连续比 90 天。已剔除稳定币、法币、黄金、包装币和代币化美股 / ETF；合约公开归档不带标的类型，所以只算币安现货有交易对的币（只有合约、没有现货的币不进榜）。合约数据比现货晚一天，榜单日期取两者都有的最近一天。排名代表流动性与热度，不是买入信号。</p>`,
  `<p>A coin’s volume = the sum of <b>all its Binance markets</b> for the UTC day, in USD: spot across every quote (${(cov.quotes||[]).join(', ')}), converted at that day’s close; USDⓈ-M futures (USDT and USDC margined, perpetual + delivery) and COIN-M (base volume × close); 1000PEPE-style contracts merged back. Unlike the Binance app ranking (per trading pair, rolling 24h), this is per coin and per UTC day so 90 days can be compared. Stablecoins, fiat, gold, wrapped tokens and tokenized stocks/ETFs are removed; only coins with a Binance spot market are ranked. Rank reflects liquidity and attention, not a buy signal.</p>`)}</details></div>`;
}
let rF='all',rSort='r30',rDir=-1;
const RCLS={lead:[L('龙头','Leader'),'var(--up)'],fade:[L('先行后掉队','Early, faded'),'var(--warn)'],follow:[L('后发跟涨','Late follower'),'var(--cool)'],lag:[L('落后','Laggard'),'var(--muted)']};
function rotation(){
  if(!ROT){fetch(root.dataset.rot+'?v='+D.last_complete_day).then(r=>r.json()).then(x=>{ROT=x;if(location.hash.startsWith('#rotation'))render()}).catch(()=>{});return `<div class="ccard empty">${L('加载中…','Loading…')}</div>`}
  const M=ROT.meta,R=ROT.coins.filter(x=>x.sym!=='BTC');
  const cnt=k=>R.filter(x=>x.cls===k).length; const pc=x=>fmtP(nz(x)?x*100:null,0);
  const med=a=>{a=a.filter(nz).sort((x,y)=>x-y);return a.length?a[Math.floor(a.length/2)]:null};
  // scatter: x = 锚点前相对 BTC，y = 锚点后 30 天
  const W=640,H=330,pl=46,pr=12,pt=10,pb=30; const xs=R.map(x=>x.pre_rel*100),ys=R.map(x=>x.r30*100);
  const clip=(v,a,b)=>Math.max(a,Math.min(b,v)); const xlo=-60,xhi=60,ylo=-40,yhi=200;
  const X=v=>pl+(clip(v,xlo,xhi)-xlo)/(xhi-xlo)*(W-pl-pr), Y=v=>pt+(1-(clip(v,ylo,yhi)-ylo)/(yhi-ylo))*(H-pt-pb);
  let g='';[ylo,0,50,100,150,yhi].forEach(v=>{g+=`<line x1="${pl}" x2="${W-pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--grid)"/><text x="${pl-5}" y="${Y(v)+4}" text-anchor="end" font-size="10" fill="var(--muted)">${v}%</text>`});
  [-60,-30,0,30,60].forEach(v=>{g+=`<text x="${X(v)}" y="${H-12}" text-anchor="middle" font-size="10" fill="var(--muted)">${v>0?'+':''}${v}pp</text>`});
  g+=`<line x1="${X(10)}" x2="${X(10)}" y1="${pt}" y2="${H-pb}" stroke="var(--muted)" stroke-dasharray="4 3"/><line x1="${pl}" x2="${W-pr}" y1="${Y(M.btc_r30*100)}" y2="${Y(M.btc_r30*100)}" stroke="var(--muted)" stroke-dasharray="4 3"/>`;
  g+=R.map(x=>`<circle cx="${X(x.pre_rel*100).toFixed(1)}" cy="${Y(x.r30*100).toFixed(1)}" r="${C[x.sym]?5:3.6}" fill="${RCLS[x.cls][1]}" opacity=".8" stroke="${C[x.sym]?'var(--ink)':'none'}"><title>${esc(x.sym)}｜${RCLS[x.cls][0]}｜${L('锚点前相对 BTC','pre-anchor vs BTC')} ${fmtP(x.pre_rel*100,0)}pp｜${L('锚点后 30 天','30d after')} ${fmtP(x.r30*100,0)}</title></circle>`).join('');
  const RC=[['r30',L('锚点后 30 天','30d after'),x=>x.r30],['pre_rel',L('锚点前相对 BTC','Pre vs BTC'),x=>x.pre_rel],['ret_end',L('区间收益','Window return'),x=>x.ret_end],['max_rally',L('区间最大涨幅','Max rally'),x=>x.max_rally],['from_peak',L('高点至今','From peak'),x=>x.from_peak],['comp',L('综合分','Composite'),x=>x.comp],['rank',L('市值排名','Mcap rank'),x=>x.rank]];
  let rows=R.filter(x=>rF==='all'||x.cls===rF||(rF==='pool'&&C[x.sym]));
  const col=RC.find(c=>c[0]===rSort); rows.sort((a,b)=>{const x=col[2](a),y=col[2](b);if(!nz(x))return 1;if(!nz(y))return -1;return (x-y)*rDir});
  const pill=(v,t)=>`<span class="pill ${rF===v?'on':''}" data-rf="${v}">${t}</span>`;
  const grp=(lo,hi)=>{const a=R.filter(x=>x.rank>=lo&&x.rank<=hi);return {n:a.length,up:a.filter(x=>x.up50).length,ret:med(a.map(x=>x.ret_end)),mx:med(a.map(x=>x.max_rally))}};
  const G=[[L('市值前 30','Top 30'),grp(1,30)],[L('31–100 名','31–100'),grp(31,100)],[L('101 名以后','101+'),grp(101,9999)]];
  return `<div class="note" style="background:var(--cool-bg);border-color:var(--cool-bd)">${L(`研究快照（大叔 ${esc(M.generated)} 生成，不每天更新）：${esc(M.start)} → ${esc(M.end)}，锚点 = BTC 拉升起点 <b>${esc(M.anchor)}</b>，数据到 ${esc(M.last_bar)}。名单：${esc(M.universe_note)}`,`Research snapshot (not updated daily): ${esc(M.start)} → ${esc(M.end)}, anchor = BTC rally start <b>${esc(M.anchor)}</b>. Universe: top ~125 by market cap with Binance USDT perps.`)}</div>
  <div class="cgrid g4">${['lead','fade','follow','lag'].map(k=>`<div class="ccard kpi"><div class="l"><span style="color:${RCLS[k][1]}">●</span> ${RCLS[k][0]}</div><div class="v">${cnt(k)}</div><div class="s">${L('锚点后 30 天中位','30d-after median')} ${pc(med(R.filter(x=>x.cls===k).map(x=>x.r30)))}</div></div>`).join('')}</div>
  <div class="cgrid g2"><div class="ccard"><h2>${L('先行、跟涨、掉队：每个点是一个币','Leaders, followers, laggards: one dot per coin')}</h2><div class="chart"><svg viewBox="0 0 ${W} ${H}">${g}</svg></div>
  <div class="sm">${L(`横轴 = 锚点前比 BTC 多涨多少（竖虚线 = +10 个百分点，先行门槛）；纵轴 = 锚点后 30 天收益（横虚线 = BTC 同期 ${pc(M.btc_r30)}，续强门槛）。右上 = 龙头。带白边的是观测台里的币。超出图框的贴边显示。`,`x = return vs BTC before the anchor (dashed = +10pp, “early” threshold); y = 30-day return after (dashed = BTC ${pc(M.btc_r30)}). Top-right = leaders. Outlined dots are monitored coins.`)}</div></div>
  <div class="ccard"><h2>${L('大币和小币谁先动','Large vs small caps')}</h2><table class="kv"><tbody><tr><td></td><td>${L('涨到低点 +50% 的占比','Reached low +50%')}</td><td>${L('区间收益中位','Median return')}</td><td>${L('最大涨幅中位','Median max rally')}</td></tr>${G.map(([n,v])=>`<tr><td>${n}（${v.n}）</td><td>${v.n?Math.round(v.up/v.n*100)+'%':'—'}</td><td>${pc(v.ret)}</td><td>${pc(v.mx)}</td></tr>`).join('')}</tbody></table>
  <h3 style="margin-top:14px">${L('怎么分类','How coins are classed')}</h3><ul class="plain"><li>${L('龙头 = 锚点前比 BTC 多涨 10 个百分点以上，且锚点后 30 天收益不低于 BTC','Leader = ≥10pp ahead of BTC before the anchor and ≥BTC over the next 30 days')}</li><li>${L('先行后掉队 = 只满足前一条；后发跟涨 = 只满足后一条；落后 = 都不满足','Early, faded = first only; late follower = second only; laggard = neither')}</li><li>${L('综合分 = 0.3×启动早晚 + 0.3×区间收益 + 0.2×均线 + 0.2×周线 MACD，只是排序','Composite = 0.3×start timing + 0.3×return + 0.2×MAs + 0.2×weekly MACD; sorting only')}</li></ul>
  <div class="sm">${L(`回测结论（原件）：区间收益前 25 名里没有一个比 BTC 更早启动；前 30 名 / 31–100 / 101 名以后的收益中位相近，小币最大涨幅更大但更晚。这条和观测台规则 R4“近期强势不加分”方向一致。`,`From the study: none of the top 25 by return started before BTC; R4 (“recent strength earns nothing”) points the same way.`)}</div></div></div>
  <div class="ccard"><div class="filters"><span class="sm">${L('筛选','Filter')}</span>${pill('all',L('全部','All'))}${['lead','fade','follow','lag'].map(k=>pill(k,RCLS[k][0])).join('')}${pill('pool',L('观测池 + 观察','Pool + watch'))}</div>
  <div class="scroll"><table><thead><tr><th>${L('币','Coin')}</th><th style="text-align:left">${L('分类','Class')}</th><th style="text-align:left">${L('启动批次','Batch')}</th>${RC.map(c=>`<th data-rs="${c[0]}" class="${rSort===c[0]?'sorted':''}">${c[1]}${rSort===c[0]?(rDir<0?' ↓':' ↑'):''}</th>`).join('')}<th style="text-align:left">${L('现在结构','Structure now')}</th><th>${L('周线走势','Weekly path')}</th></tr></thead><tbody>`+
  rows.map(x=>`<tr ${C[x.sym]?`data-go="coin/${esc(x.sym)}"`:''}><td><b>${esc(x.sym)}</b>${C[x.sym]?`<span class="tg pool">${L('观测','Pool')}</span>`:''}${x.low_act?`<span class="tg" title="${L('窗口内日成交额中位数低于 500 万美元','median daily volume < $5M')}">${L('低活跃','thin')}</span>`:''}</td><td style="text-align:left"><span style="color:${RCLS[x.cls][1]}">●</span> ${RCLS[x.cls][0]}</td><td style="text-align:left">${esc(x.queue||'')}</td>
  <td class="${cls(x.r30)}">${pc(x.r30)}</td><td class="${cls(x.pre_rel)}">${fmtP(nz(x.pre_rel)?x.pre_rel*100:null,0)}pp</td><td class="${cls(x.ret_end)}">${pc(x.ret_end)}</td><td>${pc(x.max_rally)}</td><td class="${cls(x.from_peak)}">${pc(x.from_peak)}</td><td>${nz(x.comp)?(x.comp*100).toFixed(0):'—'}</td><td>${x.rank||'—'}</td><td style="text-align:left">${esc(x.structure)}</td><td>${spark((x.path||[]).map(p=>p[1]),90,24,RCLS[x.cls][1])}</td></tr>`).join('')+`</tbody></table></div>
  <div class="sm" style="margin-top:8px">${L(`未纳入：${(ROT.skipped||[]).map(x=>esc(x.symbol)+'（'+esc(x.skipped)+'）').join('；')}。收益按币安永续日收盘；只是复盘描述，不是选币名单。`,`Excluded: ${(ROT.skipped||[]).map(x=>esc(x.symbol)).join(', ')}. Returns use Binance perpetual daily closes; a replay, not a pick list.`)}</div></div>`;
}
function rotCard(c){
  if(!ROT)return `<div class="empty">${L('加载中…','Loading…')}</div>`;
  const x=ROT.coins.find(r=>r.sym===c.sym); const M=ROT.meta;
  if(!x)return `<div class="empty">${L(`不在这期复盘名单里（市值前 125、有币安 USDT 永续）。`,`Not in this replay’s universe.`)}</div>`;
  return `<div class="stage"><span style="color:${RCLS[x.cls][1]}">●</span> ${RCLS[x.cls][0]} <span class="sm">· ${esc(x.queue||'')}</span></div><table class="kv"><tbody>
  <tr><td>${L(`锚点（${M.anchor}）前比 BTC`,`Before the anchor (${M.anchor}) vs BTC`)}</td><td class="${cls(x.pre_rel)}">${fmtP(x.pre_rel*100,0)}pp</td></tr>
  <tr><td>${L('锚点后 30 天','30 days after')}</td><td class="${cls(x.r30)}">${fmtP(x.r30*100,0)}（BTC ${fmtP(M.btc_r30*100,0)}）</td></tr>
  <tr><td>${L('区间收益 / 最大涨幅','Window return / max rally')}</td><td>${fmtP(x.ret_end*100,0)} / ${fmtP(x.max_rally*100,0)}</td></tr>
  <tr><td>${L('高点日 · 高点至今','Peak · from peak')}</td><td>${esc(x.peak_date||'—')} · ${fmtP(nz(x.from_peak)?x.from_peak*100:null,0)}</td></tr>
  <tr><td>${L('现在结构','Structure now')}</td><td>${esc(x.structure)}</td></tr></tbody></table>
  <div class="sm" style="margin-top:6px"><a data-go="rotation">${L('看整期复盘 →','Full replay →')}</a></div>`;
}
function btTable(){
  if(!BT)return `<div class="empty">${L('回测结果加载中或未生成。','Backtest results not available.')}</div>`;
  const nm={R:L('R 收入趋势','R revenue trend'),C:L('C 价值捕获','C value capture'),V:L('V 估值','V valuation'),D:L('D 价格×收入','D price × revenue'),T:L('合计（R/C/V/D 平均）','Total (avg of R/C/V/D)')};
  const cell=x=>x?`${x.ic>0?'+':''}${x.ic.toFixed(3)}<span class="sm">（t ${x.t==null?'—':x.t.toFixed(1)}）</span>`:'—';
  return `<div class="scroll"><table><thead><tr><th>${L('模块','Module')}</th><th>${L('结论','Verdict')}</th><th>${L('30 天 IC','IC 30d')}</th><th>${L('60 天 IC','IC 60d')}</th><th>${L('90 天 IC','IC 90d')}</th><th>${L('30 天 IC>0 的月份','Months IC>0 (30d)')}</th><th>${L('高 1/3 减低 1/3（30 天超额）','Top − bottom third (30d)')}</th><th>${L('月数 / 每月币数','Months / coins per month')}</th></tr></thead><tbody>`+
  Object.keys(nm).map(k=>{const m=BT.modules[k]||{},a=m['30'];return `<tr><td>${nm[k]}</td><td style="text-align:left">${btTag(k)}</td><td>${cell(m['30'])}</td><td>${cell(m['60'])}</td><td>${cell(m['90'])}</td><td>${a?a.hit+'%':'—'}</td><td class="${cls(a&&a.spread)}">${a?fmtP(a.spread):'—'}</td><td>${a?a.n_dates+' / '+a.avg_n:'—'}</td></tr>`}).join('')+`</tbody></table></div>
  <div class="sm" style="margin-top:6px">${L(`样本 ${BT.n_coins} 个有协议收入、在币安有现货的代币（${esc((BT.coins||[]).join('、'))}），${BT.dates[0]} 起每月 1 日打一次分，看之后 30 / 60 / 90 天相对同批中位数的超额。B（业务量）和 S（解锁）没有历史数据，未检验。生成于 ${esc(BT.generated)}。`,
  `${BT.n_coins} revenue-earning tokens with Binance spot markets, scored on the 1st of each month from ${BT.dates[0]}; outcome = excess return vs the cross-sectional median over the next 30/60/90 days. B and S have no history and are untested.`)}</div>
  <details class="why"><summary>${L('IC、t 值怎么看；判定标准（跑之前定的）','How to read IC and t; pass/fail rules (set before running)')}</summary>${L(`<p>IC = 每个月把“模块分数”和“之后相对收益”分别排名，算两者的相关系数（−1 到 +1）。正数说明分数高的币之后确实跑得更好；0.05 以上在选币里就算有用，但要稳定。t 值 = 平均 IC ÷ 波动 × √月数，绝对值 ≥ 2 才算不是运气。</p><p>判定：30 天、60 天 IC 都 > 0 且 30 天 t ≥ 2 → 方向有效；30 天 IC < 0 且 t ≤ −1 → 已证伪；其余 → 未通过（方向对但不显著，或方向反但不显著）。60 / 90 天的月份互相重叠，t 值偏高，只作参考。</p><p>局限：只能拿到今天还活着的协议（幸存者偏差，结果偏乐观）；每月只有 20 来个币，统计力有限；DefiLlama 的收入口径会回改。</p>`,
  `<p>IC = rank correlation between the module score and the subsequent relative return each month (−1..+1); above ~0.05 is useful if stable. t = mean IC ÷ sd × √months; |t| ≥ 2 means unlikely to be luck.</p><p>Rules: IC > 0 at 30 and 60 days with t ≥ 2 at 30 days → works; IC < 0 with t ≤ −1 → falsified; otherwise not significant. Survivorship bias applies; ~20 coins per month.</p>`)}</details>`;
}
function method(){
  const g=k=>`<li><b>${{g1:L('闸门 1 · 周期','Gate 1 · cycle'),g2:L('闸门 2 · BTC 底线','Gate 2 · BTC floor'),g3:L('闸门 3 · 流动性','Gate 3 · liquidity'),R1:L('R1 · 六问卡','R1 · six-question card'),R2:L('R2 · 解锁','R2 · unlocks'),R3:L('R3 · 价格不跑在收入前面','R3 · price vs revenue'),R4:L('R4 · 近期强势不加分','R4 · no points for strength'),R6:L('R6 · 渠道 B','R6 · channel B')}[k]}</b>：${WHY[k]}</li>`;
  return `<div class="ccard"><h2>${L('口径与规则','Method & rules')}</h2>${EN?'<div class="note">Manual notes (narrative stage, unlocks, risks, findings) come from the research log and are in Chinese.</div>':''}
  <h3 style="margin-top:12px">${L('三个维度的数据从哪来','Where the data comes from')}</h3><ul class="plain">
  <li><b>${L('基本面','Fundamentals')}</b>：${L('手续费 / 协议收入 / 持有人收入 / 供给侧收入、日活用户、国库：DefiLlama（UTC 整天）；业务量 = DEX 成交额或 TVL；流通量和 FDV：CoinGecko，按币安收盘折市值；核心开发者：GitHub 公开仓库提交记录（每周）。不同协议“收入”的定义可以相差数倍，先看口径再比较。','Fees / revenue / holder and supply-side revenue, active users, treasury: DefiLlama (UTC days); activity = DEX volume or TVL; supply and FDV: CoinGecko; developers: public GitHub commits (weekly).')}</li>
  <li><b>${L('资金面','Flows')}</b>：${L('成交额 = 币安这个币所有现货交易对 + U 本位 + 币本位合约，按币汇总成美元（见“成交额榜”的说明）；等权篮子 = 宏观页“山寨整体”同一个篮子。','Volume = all Binance spot pairs + USDⓈ-M + COIN-M futures per coin, in USD; the equal-weight basket is the Macro page’s “Altcoins overall” basket.')}</li>
  <li><b>${L('技术面','Technicals')}</b>：${L('币安现货已收盘日线：MA20 / 50 / 200、RSI14（Wilder）、距 120 日高点、30 日区间位置。只展示，不计分。','Closed Binance spot daily candles: MA20/50/200, RSI14, drawdown from 120-day high, 30-day range position. Shown, not scored.')}</li>
  <li><b>${L('人工登记','Manual')}</b>：${L(`叙事阶段、回购口径、解锁、事件、证伪条件、风险记录、重大发现来自研究笔记（最近核对 ${MAN.asof}）；未登记的标“未核”，不当作“没有”。`,`Narrative stage, unlocks, events, risks and findings from the research log (last checked ${MAN.asof}); not logged ≠ none.`)}</li></ul>
  <h3>${L('评分模块：每项怎么打分','Score modules')}</h3><ul class="plain">${['R','C','V','D','B','S'].map(k=>`<li><b>${k}</b> ${btTag(k)}：${MOD_WHY[k]}</li>`).join('')}<li>${L('综合分 = 已评模块得分 ÷（3 × 已评模块数），只用来排序。','Total = points ÷ (3 × modules scored); sorting only.')}</li></ul>
  <h3>${L('评分回测：这些模块到底有没有用','Score backtest: do the modules work?')}</h3>${btTable()}
  <h3 style="margin-top:14px">${L('建仓条件检查：每条是什么','Entry checklist: what each line means')}</h3><ul class="plain">${['g1','g2','g3','R1','R2','R3','R4','R6'].map(g).join('')}
  <li>${L('“条件齐备”只表示可以进入人工建仓评估，不是买入信号；风险提示同理，不是卖出指令。','“Conditions met” means ready for manual review, not a buy signal; risk alerts are not sell orders.')}</li></ul>
  <h3>${L('待补维度进度','Pending dimensions')}</h3><ul class="plain">
  <li>${L('已接入（11-14）：供给侧收入、日活用户、国库（总额 / 自家代币占比）、核心开发者（GitHub，近 30 天提交过代码的人数，从下一次 Actions 日更开始有数）。','Added (11-14): supply-side revenue, active users, treasury, core developers (GitHub, from the next Actions run).')}</li>
  <li>${L('还接不了：代币激励 / 收益（收入 − 激励）——协议激励排放只有付费源（DefiLlama emissions、Token Terminal）；解锁日历同理，目前人工登记。','Not yet: token incentives / earnings — only paid sources (DefiLlama emissions, Token Terminal); unlock calendars stay manual.')}</li></ul>
  ${D.errors&&D.errors.length?`<h3>${L('本次取数问题','Fetch issues this run')}</h3><ul class="plain">${D.errors.slice(0,20).map(e=>`<li>${esc(e)}</li>`).join('')}</ul>`:''}</div>`;
}
const VIEWS={home,rank,market,volume,rotation,alerts,findings,method};
const TABS=[['home',L('总观测台','Overview')],['rank',L('排行榜','Ranking')],['volume',L('成交额榜','Volume board')],['market',L('全市场','Market')],['rotation',L('拉盘复盘','Rally replay')],['alerts',L('风险提示','Risk alerts')],['findings',L('重大发现','Findings')],['method',L('口径与规则','Method')]];
function render(){
  const h=(location.hash||'#home').slice(1); const [p,arg]=h.split('/');
  root.querySelectorAll('.ctabs a').forEach(a=>a.classList.toggle('on',a.dataset.p===(p==='coin'?'rank':p)));
  $('#cview').innerHTML=p==='coin'?coin(decodeURIComponent(arg||'')):(VIEWS[p]||home)();
}
root.addEventListener('click',e=>{
  const g=e.target.closest('[data-go]');if(g){location.hash='#'+g.dataset.go;window.scrollTo(0,root.offsetTop-10);return}
  const n=e.target.closest('.ctabs a');if(n){e.preventDefault();location.hash='#'+n.dataset.p;return}
  const mf=e.target.closest('[data-mf]');if(mf){mF=mf.dataset.mf;render();return}
  const vf=e.target.closest('[data-vf]');if(vf){vF=vf.dataset.vf;vN=100;render();return}
  const vm=e.target.closest('[data-vmore]');if(vm){vN+=100;render();return}
  const vs=e.target.closest('th[data-vs]');if(vs){const k=vs.dataset.vs;if(vSort===k)vDir*=-1;else{vSort=k;vDir=['cur','spot','fut','med'].includes(k)?1:-1}render();return}
  const rf=e.target.closest('[data-rf]');if(rf){rF=rf.dataset.rf;render();return}
  const rs=e.target.closest('th[data-rs]');if(rs){const k=rs.dataset.rs;if(rSort===k)rDir*=-1;else{rSort=k;rDir=-1}render();return}
  const ms=e.target.closest('th[data-ms]');if(ms){const k=ms.dataset.ms;if(mSort===k)mDir*=-1;else{mSort=k;mDir=-1}render();return}
  const f=e.target.closest('[data-f]');if(f){const [a,b]=f.dataset.f.split(':');if(a==='tier')fTier=b;else fTag=b;render();return}
  const s=e.target.closest('th[data-s]');if(s){const k=s.dataset.s;if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=k==='vr'?1:-1}render()}
});
fetch(src).then(r=>r.json()).then(d=>{
  D=d;C=d.coins;SYMS=Object.keys(C);MAN=d.manual||{};GT=d.gates||{};
  fetch(root.dataset.bt+'?v='+d.last_complete_day).then(r=>r.ok?r.json():null).then(x=>{BT=x;if(x)render()}).catch(()=>{});
  const stale=(Date.now()-Date.parse(d.last_complete_day+'T00:00:00Z'))/864e5>3.5;
  root.innerHTML=`<div class="sm">${L('数据日','Data day')} ${d.last_complete_day}（UTC）· ${L('生成于','built')} ${esc(d.generated)}${stale?` · <b style="color:var(--warn)">${L('停更：数据超过 3 天没更新','Stale: no update for 3+ days')}</b>`:''}</div>
  <nav class="ctabs">${TABS.map(t=>`<a href="#${t[0]}" data-p="${t[0]}">${t[1]}</a>`).join('')}</nav><div id="cview"></div>`;
  window.addEventListener('hashchange',render); render();
}).catch(()=>{root.innerHTML=`<div class="empty">${L('数据加载失败，稍后刷新。','Failed to load data; refresh later.')}</div>`});
})();
