/* 涨腿追踪 + 山寨轮动窗口（/leg-tracker/ 与首页卡片）。
   来源：站长交付的设计稿 leg-tracker-design.html；数据字段、文案、统计数字、状态规则照抄，不要改。
   数据：/data/leg_latest.json（leg/leg_data.py 生成，schema 2）。页面只读，不自己判断。
   STATS / ALT：《加密行情律动-规律清单》V13（V12 检验记录）/《山寨补涨板块轮动预警框架》V4 §0，研究升版才改，同步改 STATS_ASOF 并写更新日志。 */
(function(){
var root=document.getElementById('leg-card')||document.getElementById('leg-page');
if(!root){return;}
var lang=(document.documentElement.lang||'').toLowerCase().indexOf('zh')===0?'zh':'en';
var SRC=root.getAttribute('data-src'), HREF=root.getAttribute('data-href')||'/leg-tracker/';
var TODAY=new Date().toISOString().slice(0,10);

var LEN_B=[0,5,13,36,76,165], LEN_P=[0,25,50,75,90,100];
function clamp(x,a,b){return Math.min(b,Math.max(a,x));}
function lenPos(d){
  if(d<=0) return 0; if(d>=165) return 100;
  for(var i=1;i<LEN_B.length;i++){
    if(d<=LEN_B[i]){var a=LEN_B[i-1],b=LEN_B[i];return LEN_P[i-1]+(d-a)/(b-a)*(LEN_P[i]-LEN_P[i-1]);}
  }
  return 100;
}
function lenBucket(d){return d>=76?4:d>=36?3:d>=13?2:d>=5?1:0;}
function scaleMax(d){return Math.max(110,Math.ceil(d*1.1/10)*10);}   // 与海报同一刻度尺：默认110天，超出后整体右延
function ddPos(v){return clamp(v/40*100,0,100);}
function daysBetween(a,b){return Math.round((Date.parse(b)-Date.parse(a))/86400000);}
function isStale(asof,today){return daysBetween(asof,today)>3;}
function altPos(a){return a.stage==='cleared'?100:clamp((a.n||0)/30*100,0,100);}   // 山寨窗口刻度：D0 到 D0+30
function addDays(iso,n){return new Date(Date.parse(iso)+n*86400000).toISOString().slice(0,10);}

/* ===== 固定统计数字：规律清单 V13 / V12，山寨框架 V4 §0；升版时才改 ===== */
var STATS_ASOF='2026-09-28';
var STATS={
  bullLegs:103, len:{p25:5,p50:13,p75:36,p90:76,max:165}, bearLegs:49, bearMed:6,
  dd:{n:99,p25:14.5,p50:18.5,p75:22.9,p90:32.0,eras:[20.5,20.8,15.5,17.1]},
  l89:{ since2019:[{rem:39.7,days:8},{rem:0.9,days:2},{rem:7.4,days:30},{rem:7.7,days:13},{rem:12.9,days:38}] },
  t42:[{k:'<42',int:63,ret:7.3},{k:'42–89',int:48,ret:11.3},{k:'≥89',int:59,ret:12.4}]
};
var ALT={ windows:16, basket:57,
  hit:[{k:'dd',n:8,med:-9.5,p50:12},{k:'ok',n:8,med:11.3,p50:25}],        // BTC 30 天内回撤 ≤−10% / >−10%
  peak:{med:18,p25:10,p75:23,leadMed:23}, rho:0.007, rhoP:0.86, rhoN:634, mech:{a:9.0,b:12.9} };

/* ===== 文案 ===== */
var T={
zh:{
 pageTitle:'涨腿追踪',
 h1:'涨腿追踪',
 lead:'比特币每一轮上涨走了多久、涨了多少、中途回撤多深？急拉之后山寨币的窗口什么时候开、什么时候关？历史上有什么规律？这一页把规律摆出来，并标出当前读数。',
 callout:'<b>观察工具，不是买卖信号。</b>规律描述的是历史，不预测未来；每条规律都标了证据等级，没验证过的不会当结论。',
 navs:{how:'三个数怎么读',def:'什么算一轮涨腿',len:'一般走多久',dd:'回撤多深',l89:'89天提示线',alt:'山寨轮动窗口',false:'不成立的说法',method:'口径'},
 how_h:'三个数怎么读',
 how_ul:'<li><b>天数</b>：从确认的起点算起，每天收盘加一。看的是这一轮上涨已经持续多久。</li><li><b>涨幅</b>：起点收盘价到目前为止最高收盘价的涨幅。</li><li><b>腿内最大回撤</b>：这一轮里，从某个高点收盘价回落的最大幅度。回落到 10%，这一轮就算结束。</li>',
 def_h:'什么算一轮涨腿',
 def_body:'<p>只看日线收盘价。收盘价从一个摆动低点反向走出 <b>10%</b>，才回头确认那个低点是这一轮上涨的起点——低点当天没人知道它会不会继续跌，所以起点只能事后确认。</p><p>起点确认之后，天数和涨幅<b>每天直接重算</b>，不等这一轮结束。收盘价从高点回落 10%，这一轮就算结束，换成下跌腿。</p><p>所以「已走多少天」「涨了多少」每天都在变，不是一轮走完才算一次的数。</p>',
 tag_ver:'已验证', tag_desc:'描述统计·已复现', tag_hyp:'假设', tag_fals:'已证伪',
 len_h:'历史上涨腿一般走多久',
 len_p1:function(){return '2010–2026 年共 <b>'+STATS.bullLegs+'</b> 条牛市涨腿：四分之一不超过 '+STATS.len.p25+' 天，一半不超过 '+STATS.len.p50+' 天，四分之三不超过 '+STATS.len.p75+' 天，十分之九不超过 '+STATS.len.p90+' 天，最长 '+STATS.len.max+' 天。熊市里的反弹更短：'+STATS.bearLegs+' 条，中位 '+STATS.bearMed+' 天。';},
 lenChipK:['P25','中位','P75','P90'], lenUnit:'天',
 lenBucketTxt:['短于大多数历史涨腿（不到 25% 的位置）','长于约 25%–50% 的历史涨腿','长于约 50%–75% 的历史涨腿','长于约 75%–90% 的历史涨腿','已经长于 90% 以上的历史牛市涨腿'],
 lenLive:function(d,b){return '<span class="lbl">当前这一轮</span>已走 <b>'+d+'</b> 天，'+T.zh.lenBucketTxt[b]+'。';},
 len_p2:'注意：这是涨腿「长度」的分布，只说明大多数涨腿走不了太久，<b>不说明走得越久越容易断</b>——后者我们测过，不成立（见下文「不成立的说法」）。',
 dd_h:'回撤多深算正常',
 dd_p1:function(){var d=STATS.dd;return '牛市里一旦出现 10% 以上的回撤，它最终会跌多深？'+d.n+' 次回撤的分布：P25 <b>'+d.p25+'%</b>、中位 <b>'+d.p50+'%</b>、P75 <b>'+d.p75+'%</b>、P90 <b>'+d.p90.toFixed(1)+'%</b>。由早到晚四个年代的中位数依次是 '+d.eras.map(function(x){return x.toFixed(1)+'%'}).join(' → ')+'，带子在变窄：近年回撤的典型深度比早年浅。';},
 ddZone0:'未正式回撤',
 ddLive:function(v){return '<span class="lbl">当前这一轮</span>腿内最大回撤 <b>'+v.toFixed(1)+'%</b>，'+(v<10?'还没到 10%，这一轮上涨仍在继续。':'已达 10%，这一轮上涨已经结束。');},
 dd_p2:'上面的分布带量的是「回撤到 10% 以后最终跌多深」，所以进行中的涨腿（回撤必然小于 10%）的指针会停在最左边的灰区；回撤一旦到 10%，才轮到右边几档来衡量这次下跌。',
 l89_h:'89 天提示线',
 l89_p1:'2019 年以来走过 89 天的涨腿一共 <b>5</b> 条，之后都在 <b>2–38 天</b>内见顶；第 89 天收盘到腿顶，只剩 <b>+0.9% 到 +39.7%</b> 的涨幅（下图）。',
 l89Row:function(i){return '第 '+(i+1)+' 条';}, l89Rem:'离腿顶还剩涨幅', l89Peak:function(n){return n+' 天后见顶';},
 l89_pre:'2019 年以前的 5 条：第 89 天收盘后还能涨 +104.9%、+1215%、0、+67.9%、+62.2%，其中 4 条又走了 48–76 天。',
 l89_p2:'<b>但这只是 5 条样本。</b>放到全部历史看，走到 89 天以上的涨腿，之后 30 天被 10% 回撤打断的概率是 59%，收益中位 +12.4%，并不比别的涨腿差；2022 年以来这一档被打断 78%、收益中位 −1.4%，样本更少。所以它只是「当前年代的提示」，不是已验证的规律。',
 l89_falsify:'<b>什么时候作废：</b>下一条走过 89 天的涨腿，如果再走 60 天以上仍未见顶，这条提示线就作废。',
 alt_h:'山寨轮动窗口',
 alt_p1:'BTC 急拉之后，山寨币常有一段补涨窗口。这里只记录「窗口处在哪个阶段」，<b>验证的是时机，不是选币</b>，也不是开仓信号。<br><b>D0</b>：BTC 收盘 10 日涨幅首次 ≥15% 记为点火（45 天内不重复计）；点火后 7 天内（含点火当天）的最高收盘日就是 D0，要等这 7 天走完才确定。',
 alt_ul:'<li><b>D0+0 到 D0+24</b>：建仓窗。</li><li><b>D0+24 起</b>：只减不加（到期线）。D0+28 起临近清零。</li><li><b>D0+30</b>：清零，窗口结束。</li><li><b>关闭线</b>：D0 之后 BTC 收盘跌破 D0 收盘价的 90%，窗口提前关闭。</li>',
 alt_t_h:'关闭线：BTC 回撤超过 10%，山寨窗口基本就没了',
 altHead:['BTC 点火后 30 天内','窗口数','山寨篮子收益中位','摸到 +50% 的币占比'], altRows:['最大回撤 ≤ −10%','最大回撤 > −10%'],
 alt_note:function(){return '样本：2021 年以来 '+ALT.windows+' 个「BTC 急拉后横盘」窗口，'+ALT.basket+' 个币的篮子；2025 年 BTC 没有出现过 10 日涨幅 ≥15% 的急拉，所以没有样本。回撤 > −10% 的 8 个窗口里，篮子 P75 是 +34.1%，P90 是 +74.8%。';},
 alt_peak_h:'到期线：窗口里的涨幅多数在前三周兑现',
 alt_peak_p:function(){return '没被打断的窗口里，山寨篮子见顶日的中位数是 <b>D0+'+ALT.peak.med+'</b>（P25–P75 为 D0+'+ALT.peak.p25+' 到 D0+'+ALT.peak.p75+'），涨得最多的那四分之一，见顶日中位数是 D0+'+ALT.peak.leadMed+'。所以 D0+24 以后只减不加，D0+30 清零。这是描述统计，不是预测。';},
 alt_notsel:'<b>这条线只验证时机，不验证选币。</b>我们试过 8 种机械选币方式，没有一种跑赢等权篮子（'+'+9.0% 对 +12.9%）。所以这里不给个币名单。',
 alt_f_h:'「BTC 急拉时涨得多的币，窗口里会继续领涨」',
 alt_f_p:function(){return '634 个币-窗口的检验：币在 BTC 急拉段里的涨幅，和它在窗口里的收益几乎没有关系（相关系数 '+ALT.rho+'，p='+ALT.rhoP+'）。涨幅榜不能当选币依据。';},
 f_h:'我们测过、但不成立的说法',
 f_intro:'流传的说法不一定对。下面几条我们用 2010–2026 年日线逐条检验过，结论和说法相反或不成立，列在这里，免得你被它们误导。',
 f1_h:'「涨腿走过 42 天就该收手」',
 f1Head:['涨腿已走','之后 30 天被 10% 回撤打断','之后 30 天收益中位'], f1Rows:['不足 42 天','42–89 天','89 天以上'],
 f1_p:'走过 42 天还没断的涨腿，之后反而更稳：能走到这么久的，本来就是最强的那一批。走到第 42 天的 24 条涨腿，离腿顶还剩中位 <b>+45.5%</b>。四个年代方向一致。',
 f2_h:'「涨得久 + 腿内回撤小 + 近 5 天涨得快，叠起来预警回撤」',
 f2_p:'这三件事同时亮过 4 次（2010-10、2013-03、2023-10、2026-08），之后 10 天<b>一次都没有</b>被 10% 回撤打断；对照（所有涨腿日）是 27%。方向和说法相反。',
 f3_p:'旁证（初步）：单看「5 日累计涨幅 &gt; 17.25%」的 67 段，之后 10 天被 10% 回撤打断的概率是 52%（对照 27%），但收益中位 +8.9%（对照 +2.5%）——急涨之后波动变大，方向没变。',
 m_h:'口径',
 m_ul:'<li>数据：BTC 日线收盘（UTC）。统计样本 2010-07-18 起用 Coin Metrics，2017-08-17 起用币安日线；共 5,916 天、305 条腿（涨腿和跌腿合计）。当前读数用币安现货 BTCUSDT 已收盘的日线。</li><li>检验方式：站在每一天，只用当天已知的信息；涨腿起点要等 +10% 确认才开始算。</li><li>规律是否稳定：一律拆成几个年代分别看，只在一个年代成立的不算规律。</li><li>证据编号：EV-44、EV-55、EV-45、EV-38（见站点「证据总表」）。</li><li>当前读数每日更新；统计数字只在研究升版时更新。</li>',
 statsAsof:function(){return '统计更新于 '+STATS_ASOF+'。';},
 lg_ver:'独立检验通过，方向稳定。', lg_desc:'只描述历史分布，已用独立方法复现。', lg_hyp:'有一些样本支持，但没有通过完整检验，只作提示。', lg_fals:'检验后不成立，不要用。',
 disclaimer:'本站只提供数据和过程记录，不构成投资建议。发现问题或有想法，欢迎在 X 上找 <a href="https://x.com/Uncle_Onchain" style="color:var(--g-blue)">@Uncle_Onchain</a>。',
 /* 卡片 */
 cardTitle:'涨腿追踪', cardSub:'BTC 这一轮上涨走到哪了',
 dayPre:'第', dayPost:'天', gainLbl:'距起点涨幅',
 ddK:'腿内最大回撤', ddC:function(){return '历史牛市回撤中位 '+STATS.dd.p50+'%';},
 l89K:'89 天提示线', l89Before:function(n){return '还差 '+n+' 天';}, l89Today:'今天刚到', l89After:function(n){return '已越过 '+n+' 天';},
 l89C:'假设级提示',
 mark89:'89天', asof:'数据截至', cta:'看规律说明 →', staleB:'数据已停更',
 noneT:'当前没有进行中的涨腿', noneP:'新的一轮要等收盘价从低点反向走出 10% 才会确认。',
 lastLeg:function(l){return '上一轮：'+l.start_date+' → '+l.end_date+'，'+l.days+' 天，+'+l.gain_pct.toFixed(1)+'%';},
 err:'数据加载失败', retry:'点此重试', preview:'预览示例数据',
 altTitle:'山寨轮动窗口', altSub:'这条线只验证时机，不验证选币',
 stg:{build:'建仓窗',trim:'只减不加',closing:'临近清零',cleared:'已清零',stopped:'已提前关闭',pending:'等待确认 D0',idle:'暂无窗口'},
 z1:'建仓窗', z2:'只减不加', altDaySuf:'天',
 c_d0K:'窗口起点 D0', c_d0N:'BTC 急拉后的腿顶日',
 c_clrK:'距清零', c_clrV:function(d){return d+' 天';}, c_clrN:'D0+30 清零',
 c_doneK:'状态', c_doneV:'已清零', c_doneN:function(d){return d+' 清零 · 新窗口等新的 D0';},
 c_stopV:'已提前关闭', c_stopN:function(d){return 'BTC 收盘跌破 D0×0.90（'+d+'）';},
 c_ignK:'点火日', c_ignN:'D0 在点火后 7 天内确定', c_provK:'暂定 D0', c_provN:'还没最终确定',
 idleT:'暂无山寨窗口', idleP:'要等 BTC 收盘 10 日涨幅 ≥15% 的下一次急拉，再用其后 7 天内的最高收盘确定 D0。',
 pendT:'已点火，等待确认 D0', pendP:'D0 要等点火后 7 天走完才确定。',
 liveH:'当前这一轮', startK:'起点', confirmK:'确认于', highK:'最高收盘', ddOn:'出现于',
 liveDay:'已走天数', liveGain:'累计涨幅', liveDd:'腿内最大回撤',
 altLiveH:'山寨轮动窗口', stopLineK:'关闭线（D0×0.90）', btcNowK:'BTC 现价', vsLine:'高于关闭线', vsLineNeg:'低于关闭线'
},
en:{
 pageTitle:'Leg Tracker',
 h1:'Leg Tracker',
 lead:'How long does each Bitcoin rally last, how far does it go, how deep are the dips? And after a sharp BTC surge, when does the altcoin window open and close? This page lays out the historical pattern and the current readings.',
 callout:'<b>An observation tool, not a trading signal.</b> The patterns describe history and do not predict the future. Every pattern carries an evidence grade; unverified ones are never presented as conclusions.',
 navs:{how:'Reading the numbers',def:'What is a leg',len:'How long',dd:'How deep',l89:'Day-89 marker',alt:'Altcoin window',false:'What failed',method:'Method'},
 how_h:'Reading the three numbers',
 how_ul:'<li><b>Days</b>: counted from the confirmed start, +1 each daily close. How long this rally has lasted.</li><li><b>Gain</b>: from the start close to the highest close so far.</li><li><b>Max in-leg drawdown</b>: the largest close-to-close drop from a peak within this rally. At 10% the rally counts as over.</li>',
 def_h:'What counts as a rally leg',
 def_body:'<p>Daily closes only. A swing low is confirmed as the start of a rally once the close has moved <b>10%</b> off it in the opposite direction. On the day of the low nobody knows whether it will fall further, so the start can only be confirmed after the fact.</p><p>Once the start is confirmed, days and gain are <b>recomputed every day</b>; we do not wait for the leg to finish. When the close falls 10% from the peak, the rally is over and a down-leg begins.</p><p>So "days so far" and "gain so far" change daily; they are not one-off numbers computed after a leg ends.</p>',
 tag_ver:'Verified', tag_desc:'Descriptive · replicated', tag_hyp:'Hypothesis', tag_fals:'Falsified',
 len_h:'How long rallies usually last',
 len_p1:function(){return 'Across 2010–2026 there are <b>'+STATS.bullLegs+'</b> bull-market rallies: a quarter last ≤ '+STATS.len.p25+' days, half ≤ '+STATS.len.p50+', three quarters ≤ '+STATS.len.p75+', nine in ten ≤ '+STATS.len.p90+'; the longest ran '+STATS.len.max+' days. Bear-market bounces are shorter: '+STATS.bearLegs+' of them, median '+STATS.bearMed+' days.';},
 lenChipK:['P25','Median','P75','P90'], lenUnit:' d',
 lenBucketTxt:['shorter than most historical rallies (below the 25th percentile)','longer than roughly 25%–50% of historical rallies','longer than roughly 50%–75% of historical rallies','longer than roughly 75%–90% of historical rallies','already longer than 90%+ of historical bull-market rallies'],
 lenLive:function(d,b){return '<span class="lbl">Current rally</span>Day <b>'+d+'</b>, '+T.en.lenBucketTxt[b]+'.';},
 len_p2:'Note: this is the distribution of rally <b>length</b>. It says most rallies do not last very long; it does <b>not</b> say that older rallies are more likely to break. We tested that, and it does not hold (see "What failed" below).',
 dd_h:'How deep a pullback is normal',
 dd_p1:function(){var d=STATS.dd;return 'Once a bull-market drawdown passes 10%, how deep does it end up? Distribution of '+d.n+' drawdowns: P25 <b>'+d.p25+'%</b>, median <b>'+d.p50+'%</b>, P75 <b>'+d.p75+'%</b>, P90 <b>'+d.p90.toFixed(1)+'%</b>. Medians across the four eras, earliest to latest: '+d.eras.map(function(x){return x.toFixed(1)+'%'}).join(' → ')+'. The band is narrowing: typical drawdowns in recent years are shallower than in early ones.';},
 ddZone0:'not yet a drawdown',
 ddLive:function(v){return '<span class="lbl">Current rally</span>Max in-leg drawdown <b>'+v.toFixed(1)+'%</b>, '+(v<10?'still under 10%, so the rally is still running.':'at 10%, so this rally is over.');},
 dd_p2:'The bands above measure "how deep a drawdown ends up once it reaches 10%". A rally that is still running always has a drawdown below 10%, so its marker sits in the grey zone on the left; only after it hits 10% do the bands on the right apply to the decline.',
 l89_h:'The day-89 marker',
 l89_p1:'Since 2019, <b>5</b> rallies have lasted past day 89, and all of them topped out within <b>2–38 days</b>. From the day-89 close to the peak they had only <b>+0.9% to +39.7%</b> left (chart below).',
 l89Row:function(i){return 'Leg '+(i+1);}, l89Rem:'gain left to the peak', l89Peak:function(n){return 'peak '+n+' d later';},
 l89_pre:'The 5 rallies before 2019 still gained +104.9%, +1215%, 0, +67.9% and +62.2% after day 89; four of them ran another 48–76 days.',
 l89_p2:'<b>But that is only 5 samples.</b> Over the full history, rallies past day 89 had a 59% chance of being interrupted by a 10% drawdown within 30 days, with a median return of +12.4%, no worse than other rallies. Since 2022 that bucket was interrupted 78% of the time with a median return of −1.4%, on even fewer samples. So it is a "marker for the current era", not a verified rule.',
 l89_falsify:'<b>When it is retired:</b> if the next rally to pass day 89 keeps going for 60 more days without topping, the marker is dropped.',
 alt_h:'The altcoin window',
 alt_p1:'After a sharp BTC surge, altcoins often get a catch-up window. We only record <b>which stage the window is in</b>: it tests timing, not coin selection, and it is not an entry signal.<br><b>D0</b>: the first day BTC\'s 10-day close-to-close gain reaches 15% is an "ignition" (no repeats within 45 days); the highest close within 7 days of ignition (ignition day included) is D0, and it is only fixed once those 7 days have passed.',
 alt_ul:'<li><b>D0+0 to D0+24</b>: build window.</li><li><b>From D0+24</b>: trim only (the expiry line). From D0+28 the window is about to close.</li><li><b>D0+30</b>: cleared, the window is over.</li><li><b>Closing line</b>: if BTC closes below 90% of the D0 close, the window closes early.</li>',
 alt_t_h:'Closing line: once BTC draws down past 10%, the altcoin window is mostly gone',
 altHead:['BTC within 30 days of ignition','Windows','Altcoin basket median','Coins that touched +50%'], altRows:['Max drawdown ≤ −10%','Max drawdown > −10%'],
 alt_note:function(){return 'Sample: '+ALT.windows+' "sharp BTC surge, then sideways" windows since 2021, a basket of '+ALT.basket+' coins. BTC had no 10-day gain of 15%+ in 2025, so that year has no sample. In the 8 windows with drawdown > −10% the basket P75 was +34.1% and P90 +74.8%.';},
 alt_peak_h:'Expiry line: most of the gain comes in the first three weeks',
 alt_peak_p:function(){return 'In windows that were not interrupted, the basket peaked at a median of <b>D0+'+ALT.peak.med+'</b> (P25–P75: D0+'+ALT.peak.p25+' to D0+'+ALT.peak.p75+'); the top quarter of coins peaked at a median of D0+'+ALT.peak.leadMed+'. Hence trim only after D0+24 and clear at D0+30. This is descriptive statistics, not a forecast.';},
 alt_notsel:'<b>This line tests timing, not coin selection.</b> We tried 8 mechanical selection rules and none beat an equal-weight basket (+9.0% vs +12.9%). So no coin list is given here.',
 alt_f_h:'"Coins that rose most in the BTC surge keep leading in the window"',
 alt_f_p:function(){return 'Tested on 634 coin-windows: a coin\'s gain during the BTC surge has almost no relationship with its return in the window (correlation '+ALT.rho+', p='+ALT.rhoP+'). The gainers list is not a selection criterion.';},
 f_h:'Claims we tested that did not hold',
 f_intro:'Popular rules of thumb are not always right. We tested each of these on 2010–2026 daily data; the results contradict them or fail to support them, so we list them here.',
 f1_h:'"A rally older than 42 days should be treated with caution"',
 f1Head:['Rally age','Interrupted by 10% drawdown within 30 d','Median 30 d return'], f1Rows:['< 42 days','42–89 days','89+ days'],
 f1_p:'Rallies that survived past day 42 were actually steadier afterwards: the ones that last that long are the strongest ones. The 24 rallies that reached day 42 still had a median of <b>+45.5%</b> left to the peak. Direction was consistent in all four eras.',
 f2_h:'"Long rally + small in-leg drawdown + fast last 5 days, stacked, warns of a pullback"',
 f2_p:'All three conditions lit up together 4 times (2010-10, 2013-03, 2023-10, 2026-08). In the following 10 days a 10% drawdown happened <b>zero</b> times, versus 27% for all rally days. The opposite of the claim.',
 f3_p:'Side note (preliminary): looking only at "5-day gain &gt; 17.25%" (67 episodes), the chance of a 10% drawdown within 10 days was 52% (vs 27%), but the median return was +8.9% (vs +2.5%). After a sharp surge volatility rises; direction does not change.',
 m_h:'Method',
 m_ul:'<li>Data: BTC daily closes (UTC). Statistics use Coin Metrics from 2010-07-18 and Binance daily candles from 2017-08-17; 5,916 days and 305 legs (up and down combined). Current readings use closed daily candles of Binance spot BTCUSDT.</li><li>Testing: standing on each day using only what was known that day; a rally start counts only after the +10% confirmation.</li><li>Stability: every pattern is split by era; one that holds in a single era is not treated as a pattern.</li><li>Evidence IDs: EV-44, EV-55, EV-45, EV-38 (see the site evidence table).</li><li>The current readings update daily; the statistics change only when the research is revised.</li>',
 statsAsof:function(){return 'Statistics as of '+STATS_ASOF+'.';},
 lg_ver:'Passed independent testing; direction is stable.', lg_desc:'Describes the historical distribution only; independently replicated.', lg_hyp:'Some supporting samples, but it has not passed full testing. A marker only.', lg_fals:'Tested and rejected. Do not rely on it.',
 disclaimer:'Data and process records only. Not investment advice. Found a problem or have an idea? Find us on X: <a href="https://x.com/Uncle_Onchain" style="color:var(--g-blue)">@Uncle_Onchain</a>.',
 cardTitle:'Leg Tracker', cardSub:'Where this BTC rally stands',
 dayPre:'Day ', dayPost:'', gainLbl:'gain from start',
 ddK:'Max in-leg drawdown', ddC:function(){return 'Historical bull median '+STATS.dd.p50+'%';},
 l89K:'Day-89 marker', l89Before:function(n){return n+' days to go';}, l89Today:'Reached today', l89After:function(n){return n+' days past';},
 l89C:'Hypothesis-grade marker',
 mark89:'Day 89', asof:'Data as of', cta:'How it works →', staleB:'Data stale',
 noneT:'No rally in progress', noneP:'A new rally is confirmed only after the close moves 10% off a low.',
 lastLeg:function(l){return 'Previous: '+l.start_date+' → '+l.end_date+', '+l.days+' days, +'+l.gain_pct.toFixed(1)+'%';},
 err:'Failed to load data', retry:'Retry', preview:'Preview sample data',
 altTitle:'Altcoin window', altSub:'Tests timing, not coin selection',
 stg:{build:'Build window',trim:'Trim only',closing:'Closing out',cleared:'Cleared',stopped:'Closed early',pending:'D0 pending',idle:'No window'},
 z1:'Build', z2:'Trim only', altDaySuf:' d',
 c_d0K:'Window start D0', c_d0N:'BTC peak day after the surge',
 c_clrK:'To clear-out', c_clrV:function(d){return d+' days';}, c_clrN:'Clears at D0+30',
 c_doneK:'Status', c_doneV:'Cleared', c_doneN:function(d){return 'Cleared '+d+' · next window needs a new D0';},
 c_stopV:'Closed early', c_stopN:function(d){return 'BTC closed below D0×0.90 ('+d+')';},
 c_ignK:'Ignition day', c_ignN:'D0 is fixed 7 days after ignition', c_provK:'Provisional D0', c_provN:'Not final yet',
 idleT:'No altcoin window', idleP:'Waiting for the next sharp BTC surge (10-day close gain ≥15%); D0 is then the highest close within the following 7 days.',
 pendT:'Ignited, D0 pending', pendP:'D0 is fixed only after 7 days from ignition have passed.',
 liveH:'Current rally', startK:'Start', confirmK:'confirmed', highK:'Highest close', ddOn:'on',
 liveDay:'Days so far', liveGain:'Gain so far', liveDd:'Max in-leg drawdown',
 altLiveH:'Altcoin window', stopLineK:'Closing line (D0×0.90)', btcNowK:'BTC now', vsLine:'above the line', vsLineNeg:'below the line'
}};


function t(k){var v=T[lang][k];if(typeof v==='function'){return v.apply(null,[].slice.call(arguments,1));}return v;}
function f1(v){return v.toFixed(1);}
function px(v){return v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});}

function trackHTML(day){
  var sm=scaleMax(day), pos=clamp(day/sm*100,0,100), p89=89/sm*100;
  return '<div class="bw"><div class="track" role="img" aria-label="'+t('dayPre')+day+t('dayPost')+'">'
   +'<div class="fill" style="width:'+pos+'%"></div>'
   +'<div class="m89" style="left:'+p89+'%"><span>'+t('mark89')+'</span></div>'
   +'<i class="now" style="left:'+pos+'%"></i>'
   +'<div class="nl" style="left:'+clamp(pos,9,91)+'%">'+t('dayPre')+day+t('dayPost')+'</div></div></div>';
}
function l89Text(day){var n=day-89;return n<0?t('l89Before',-n):n===0?t('l89Today'):t('l89After',n);}

function altBarHTML(a,withDot){
  var dot=withDot&&['build','trim','closing','cleared','stopped'].indexOf(a.stage)>=0;
  var dim=(a.stage==='cleared'||a.stage==='stopped')?' dim':'';
  return '<div class="bw"><div class="altz"><span style="left:40%">'+t('z1')+'</span><span style="left:86.7%">'+t('z2')+'</span></div>'
   +'<div class="abar'+dim+'"><i style="width:80%;background:var(--g-bar-blue)"></i><i style="width:13.333%;background:var(--g-bar-gold)"></i><i style="width:6.667%;background:var(--g-bar-red)"></i>'
   +'<b class="tick" style="left:80%"></b><b class="tick" style="left:93.333%"></b>'
   +(dot?'<i class="now" style="left:'+altPos(a)+'%"></i>':'')+'</div>'
   +'<div class="altt"><span style="left:80%">D0+24</span><span style="left:93.333%">D0+28</span></div></div>';
}
function altChips(a){
  function tile(k,v,c){return '<div class="tile"><div class="k">'+k+'</div><div class="v">'+v+'</div><div class="c">'+c+'</div></div>';}
  if(a.stage==='pending'){return '<div class="tiles">'+tile(t('c_ignK'),a.ignition_date,t('c_ignN'))+tile(t('c_provK'),a.d0_date,t('c_provN'))+'</div>';}
  var left=tile(t('c_d0K'),a.d0_date,t('c_d0N'));
  var right;
  if(a.stage==='cleared'){right=tile(t('c_doneK'),t('c_doneV'),t('c_doneN',a.clear_date));}
  else if(a.stage==='stopped'){right=tile(t('c_doneK'),t('c_stopV'),t('c_stopN',a.stopped_date));}
  else{right=tile(t('c_clrK'),t('c_clrV',a.days_to_clear),t('c_clrN'));}
  return '<div class="tiles">'+left+right+'</div>';
}
function altModuleHTML(a,stale){
  var head='<div class="mod-head"><div class="mod-title">'+t('altTitle')+'</div><span class="badge b-'+a.stage+'">'+t('stg')[a.stage]+'</span></div><div class="mod-sub">'+t('altSub')+'</div>';
  if(a.stage==='idle'){return '<div class="mod m2">'+head+'<div class="empty"><b>'+t('idleT')+'</b>'+t('idleP')+'</div></div>';}
  if(a.stage==='pending'){return '<div class="mod m2">'+head+'<div class="empty"><b>'+t('pendT')+'</b>'+t('pendP')+'</div>'+altChips(a)+'</div>';}
  return '<div class="mod m2">'+head
   +'<div class="reading"><div class="big"><small>D0+</small>'+a.n+'<small>'+t('altDaySuf')+'</small></div></div>'
   +altBarHTML(a,true)+altChips(a)+'</div>';
}
function btcModuleHTML(b){
  var badge=b.badge?'<span class="badge">'+b.badge[lang]+'</span>':'';
  var head='<div class="mod-head"><div class="mod-title">'+t('cardTitle')+'<small>Leg Tracker</small></div>'+badge+'</div><div class="mod-sub">'+t('cardSub')+'</div>';
  if(b.status!=='active'||!b.leg){
    return '<div class="mod m1">'+head+'<div class="empty"><b>'+t('noneT')+'</b>'+t('noneP')+(b.last_leg?'<br><span class="small">'+t('lastLeg',b.last_leg)+'</span>':'')+'</div></div>';
  }
  var L=b.leg;
  return '<div class="mod m1">'+head
   +'<div class="reading"><div class="big"><small>'+t('dayPre')+'</small>'+L.day+'<small>'+t('dayPost')+'</small></div><div class="gain">+'+f1(L.gain_pct)+'%<small>'+t('gainLbl')+'</small></div></div>'
   +trackHTML(L.day)
   +'<div class="tiles"><div class="tile"><div class="k">'+t('ddK')+'</div><div class="v">'+f1(L.max_dd_pct)+'%</div><div class="c">'+t('ddC')+'</div></div>'
   +'<div class="tile"><div class="k">'+t('l89K')+'</div><div class="v">'+l89Text(L.day)+'</div><div class="c">'+t('l89C')+'</div></div></div></div>';
}

function cardHTML(d){
  if(!d||!d.btc_leg||!d.alt_window){return '<div class="card"><div class="errbox">'+t('err')+' · <button type="button" data-leg-retry>'+t('retry')+'</button></div></div>';}
  var stale=isStale(d.asof,TODAY);
  var top=(stale?'<div style="margin-bottom:8px"><span class="badge stale">'+t('staleB')+'</span></div>':'');
  return '<a class="card'+(stale?' is-stale':'')+'" href="'+HREF+'">'+top+btcModuleHTML(d.btc_leg)+altModuleHTML(d.alt_window,stale)
   +'<div class="card-foot"><span>'+t('asof')+' '+d.asof+'</span><span class="cta">'+t('cta')+'</span></div></a>';
}

function liveHTML(d){
  if(!d||!d.btc_leg||!d.alt_window){return '';}
  var h='';
  var b=d.btc_leg;
  if(b.status==='active'&&b.leg){
    var L=b.leg;
    h+='<div class="card panel"><div class="mod-head"><div class="mod-title">'+t('liveH')+'</div><span class="small muted">'+(isStale(d.asof,TODAY)?'<span class="badge stale">'+t('staleB')+'</span> ':'')+t('asof')+' '+d.asof+'</span></div>'
     +trackHTML(L.day)
     +'<div class="tiles tiles3">'
     +'<div class="tile"><div class="k">'+t('liveDay')+'</div><div class="v">'+L.day+'</div><div class="c">'+t('startK')+' '+L.start_date+'<br>'+px(L.start_close)+'</div></div>'
     +'<div class="tile"><div class="k">'+t('liveGain')+'</div><div class="v">+'+f1(L.gain_pct)+'%</div><div class="c">'+t('highK')+' '+px(L.high_close)+'<br>'+L.high_date+'</div></div>'
     +'<div class="tile"><div class="k">'+t('liveDd')+'</div><div class="v">'+f1(L.max_dd_pct)+'%</div><div class="c">'+t('ddOn')+' '+L.max_dd_date+'</div></div></div>'
     +'<div class="small muted" style="margin-top:8px">'+t('confirmK')+' '+L.confirm_date+'</div></div>';
  }
  var a=d.alt_window;
  h+='<div class="card panel"><div class="mod-head"><div class="mod-title">'+t('altLiveH')+'</div><span class="badge b-'+a.stage+'">'+t('stg')[a.stage]+'</span></div>';
  if(a.stage==='idle'){h+='<div class="empty"><b>'+t('idleT')+'</b>'+t('idleP')+'</div></div>';}
  else if(a.stage==='pending'){h+='<div class="empty"><b>'+t('pendT')+'</b>'+t('pendP')+'</div>'+altChips(a)+'</div>';}
  else{
    var vs=a.btc_vs_stop_pct, vsTxt=vs==null?'':(vs>=0?'+'+f1(vs)+'% '+t('vsLine'):f1(vs)+'% '+t('vsLineNeg'));
    h+='<div class="reading"><div class="big"><small>D0+</small>'+a.n+'<small>'+t('altDaySuf')+'</small></div></div>'+altBarHTML(a,true)
     +'<div class="tiles tiles3">'
     +'<div class="tile"><div class="k">D0</div><div class="v" style="font-size:15px">'+a.d0_date+'</div><div class="c">'+px(a.d0_close)+'</div></div>'
     +'<div class="tile"><div class="k">'+t('stopLineK')+'</div><div class="v" style="font-size:15px">'+px(a.stop_line)+'</div><div class="c">'+t('btcNowK')+' '+px(a.btc_close)+'<br>'+vsTxt+'</div></div>'
     +'<div class="tile"><div class="k">'+(a.stage==='cleared'?t('c_doneK'):t('c_clrK'))+'</div><div class="v" style="font-size:15px">'+(a.stage==='cleared'?t('c_doneV'):a.stage==='stopped'?t('c_stopV'):t('c_clrV',a.days_to_clear))+'</div><div class="c">'+(a.stage==='cleared'?t('c_doneN',a.clear_date):a.stage==='stopped'?t('c_stopN',a.stopped_date):t('c_clrN'))+'</div></div></div></div>';
  }
  return h;
}

function meterHTML(v){
  var segs=[[0,10,'rgba(127,127,127,.28)'],[10,STATS.dd.p25,'rgba(127,184,220,.25)'],[STATS.dd.p25,STATS.dd.p50,'rgba(127,184,220,.42)'],[STATS.dd.p50,STATS.dd.p75,'rgba(127,184,220,.62)'],[STATS.dd.p75,STATS.dd.p90,'rgba(127,184,220,.85)'],[STATS.dd.p90,40,'rgba(232,163,167,.7)']];
  var h='<div class="meter">';
  segs.forEach(function(s,i){h+='<div class="z" style="left:'+ddPos(s[0])+'%;width:'+(ddPos(s[1])-ddPos(s[0]))+'%;background:'+s[2]+';'+(i===0?'border-radius:7px 0 0 7px;':'')+(i===segs.length-1?'border-radius:0 7px 7px 0;':'')+'"></div>';});
  [[10,'10','up'],[STATS.dd.p25,String(STATS.dd.p25),'dn'],[STATS.dd.p50,String(STATS.dd.p50),'up'],[STATS.dd.p75,String(STATS.dd.p75),'dn'],[STATS.dd.p90,f1(STATS.dd.p90),'up']].forEach(function(k){
    h+='<div class="tk '+k[2]+'" style="left:'+ddPos(k[0])+'%"><span>'+k[1]+'</span></div>';});
  if(v!=null){h+='<div class="mk" style="left:'+ddPos(v)+'%"></div>';}
  return h+'</div>';
}
function l89BarsHTML(){
  var h='';
  STATS.l89.since2019.forEach(function(r,i){
    h+='<div class="brow"><span>'+t('l89Row',i)+'</span><div class="bg"><i style="width:'+clamp(r.rem/45*100,1.5,100)+'%"></i></div><div class="val">+'+f1(r.rem)+'%<small>'+t('l89Peak',r.days)+'</small></div></div>';
  });
  return h+'<div class="small muted">'+t('l89Rem')+'</div>';
}
function f1TableHTML(){
  var H=t('f1Head'),R=t('f1Rows');
  var h='<tr><th>'+H[0]+'</th><th>'+H[1]+'</th><th>'+H[2]+'</th></tr>';
  STATS.t42.forEach(function(r,i){h+='<tr><td>'+R[i]+'</td><td>'+r.int+'%</td><td>+'+f1(r.ret)+'%</td></tr>';});
  return h;
}
function altTableHTML(){
  var H=t('altHead'),R=t('altRows');
  var h='<tr><th>'+H[0]+'</th><th>'+H[1]+'</th><th>'+H[2]+'</th><th>'+H[3]+'</th></tr>';
  ALT.hit.forEach(function(r,i){h+='<tr><td>'+R[i]+'</td><td>'+r.n+'</td><td>'+(r.med>0?'+':'−')+Math.abs(r.med).toFixed(1)+'%</td><td>'+r.p50+'%</td></tr>';});
  return h;
}


/* ===== 总渲染 ===== */
function okData(d){
  if(!d||d.schema!==2||!d.asof||!d.btc_leg||!d.alt_window){return false;}
  var b=d.btc_leg,a=d.alt_window;
  if(b.status==='active'){var L=b.leg;if(!L){return false;}
    var ks=['start_date','start_close','confirm_date','day','gain_pct','high_close','high_date','max_dd_pct','max_dd_date'];
    for(var i=0;i<ks.length;i++){if(L[ks[i]]==null){return false;}}}
  else if(b.status!=='none'){return false;}
  if(!T[lang].stg[a.stage]){return false;}
  var need={pending:['ignition_date','d0_date'],idle:[]}[a.stage]||['d0_date','d0_close','n','days_to_clear','clear_date','stop_line','btc_close'];
  for(var j=0;j<need.length;j++){if(a[need[j]]==null){return false;}}
  if(a.stage==='stopped'&&a.stopped_date==null){return false;}
  return true;
}
var DATA=null, TRIED=false;
function $(id){return document.getElementById(id);}
function renderCard(){root.innerHTML=cardHTML(DATA);}
function renderPage(){
  document.querySelectorAll('#leg-page [data-i18n]').forEach(function(el){var v=t(el.getAttribute('data-i18n'));if(v!=null)el.innerHTML=v;});
  var navs=t('navs');$('legChips').innerHTML=Object.keys(navs).map(function(k){return '<a href="#'+k+'">'+navs[k]+'</a>';}).join('');
  $('liveMount').innerHTML=!TRIED?'':DATA?liveHTML(DATA):'<div class="card"><div class="errbox">'+t('err')+' · <button type="button" data-leg-retry>'+t('retry')+'</button></div></div>';
  var active=DATA&&DATA.btc_leg.status==='active'&&DATA.btc_leg.leg?DATA.btc_leg.leg:null;
  $('lenChips').innerHTML=['p25','p50','p75','p90'].map(function(k,i){return '<div class="tile"><div class="k">'+t('lenChipK')[i]+'</div><div class="v">'+STATS.len[k]+t('lenUnit')+'</div></div>';}).join('');
  $('lenPinMount').innerHTML=active?'<div class="pin" style="left:'+lenPos(active.day)+'%"><span>'+t('dayPre')+active.day+t('dayPost')+'</span></div>':'';
  $('lenLive').style.display=active?'':'none';
  if(active){$('lenLive').innerHTML=t('lenLive',active.day,lenBucket(active.day));}
  $('ddMeter').innerHTML=meterHTML(active?active.max_dd_pct:null);
  $('ddLegend').innerHTML='<span>'+t('ddZone0')+' &lt; 10%</span><span>P25 '+STATS.dd.p25+'%</span><span>'+(lang==='zh'?'中位':'Median')+' '+STATS.dd.p50+'%</span><span>P75 '+STATS.dd.p75+'%</span><span>P90 '+f1(STATS.dd.p90)+'%</span>';
  $('ddLive').style.display=active?'':'none';
  if(active){$('ddLive').innerHTML=t('ddLive',active.max_dd_pct);}
  $('l89Bars').innerHTML=l89BarsHTML();
  $('altStatic').innerHTML=altBarHTML({stage:'idle'},false);
  $('altTable').innerHTML=altTableHTML();
  $('f1Table').innerHTML=f1TableHTML();
  $('statsAsof').textContent=t('statsAsof');
}
function render(){if(root.id==='leg-card'){renderCard();}else{renderPage();}}
function load(){
  fetch(SRC,{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();})
   .then(function(j){TRIED=true;DATA=okData(j)?j:null;render();})
   .catch(function(){TRIED=true;DATA=null;render();});
}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-leg-retry]');if(b){e.preventDefault();load();}});
if(root.id==='leg-page'){render();}
load();
})();
