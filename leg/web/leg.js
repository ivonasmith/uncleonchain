/* 涨跌腿追踪 + 山寨轮动窗口（宏观页顶部卡片、首页卡片、/leg-tracker/ 详情页）。
   来源：站长交付的设计稿 v3（leg-tracker-design_1.html）；数据字段、文案、统计数字、状态规则照抄，不要改。
   数据：/data/leg_latest.json（schema 3）+ /data/leg_history.json（详情页「全部行情」），都由 leg/leg_data.py 生成。页面只读，不自己判断。
   STATS / ALT：《加密行情律动-规律清单》V13（V12 检验记录）/《山寨补涨板块轮动预警框架》V4 §0，研究升版才改，同步改 STATS_ASOF 并写更新日志。 */
(function(){
var root=document.getElementById('leg-card')||document.getElementById('leg-page');
if(!root){return;}
var lang=(document.documentElement.lang||'').toLowerCase().indexOf('zh')===0?'zh':'en';
var SRC=root.getAttribute('data-src'), HSRC=root.getAttribute('data-hist'), HREF=root.getAttribute('data-href')||'/leg-tracker/';
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
function ddBucket(v,b){b=b||[14.5,18.5,22.9,32.0];return v<b[0]?0:v<b[1]?1:v<b[2]?2:v<b[3]?3:4;}
function pctRank(xs,v){if(!xs||!xs.length)return null;var c=0;xs.forEach(function(x){if(x<v)c++;});return Math.round(c/xs.length*100);}
function dirOf(b){return b.direction||(b.status==='active'?'up':'none');}
function prevOf(b){return b.prev_leg||null;}
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
 meterCap:'刻度：历史牛市回撤分位（%）', dirUp:'上涨腿', dirDown:'下跌腿', dnGain:'高点至最低收盘',
 dnPeakK:'现价距高点', dnPeakC:function(l){return '高点 '+px(l.start_close)+' · '+l.start_date.slice(5);},
 revK:'反弹确认线', revC:function(p){return '较现价 +'+f1(p)+'% · 收盘站上＝涨腿重新开始';},
 prevLeg:function(l){return '上一腿：'+(l.dir==='up'?'涨腿':'跌腿')+' '+l.start_date+' → '+l.end_date+'，'+l.days+' 天，'+(l.pct>0?'+':'')+f1(l.pct)+'%';},
 liveDnDay:'已走天数', liveDnDrop:'已跌幅度', liveDnPeak:'高点', liveDnLow:'最低收盘', liveRev:'反弹确认线',
 ddBucketTxt:['落在历史牛市回撤最浅的四分之一里','比约 25%–50% 的历史牛市回撤深','比约 50%–75% 的历史牛市回撤深','比约 75%–90% 的历史牛市回撤深','已经比 90% 以上的历史牛市回撤都深'],
 ddLiveDn:function(v){return '<span class="lbl">当前这一腿（跌腿）</span>已从高点跌 <b>'+v.toFixed(1)+'%</b>，'+t('ddBucketTxt')[ddBucket(v)]+'。';},
 lenLiveDn:function(d){return '<span class="lbl">当前这一腿（跌腿）</span>已走 <b>'+d+'</b> 天。上面这条分布是涨腿的长度；跌腿的时长分布见下面「全部行情的涨腿与跌腿」。';},
 hist_h:'全部行情的涨腿与跌腿',
 hist_p1:function(H){var s=H.summary,c=H.coverage;return '用同一套 10% 折线，把 <b>'+c.from+'</b> 到 <b>'+c.to+'</b> 的全部日线（'+c.days.toLocaleString('en-US')+' 天）逐条切成涨腿和跌腿，<b>不分牛熊</b>。已走完 <b>'+s.completed_legs+'</b> 条：涨腿 '+s.up.n+' 条、跌腿 '+s.down.n+' 条。'+(c.mode==='partial'?'<br><b>⚠ 早期历史没取全，只覆盖上面这段，条数和分布偏少。</b>':'');},
 histDaysH:'持续天数', histMagH:'幅度（涨腿＝涨幅，跌腿＝跌幅）', histRowUp:'涨腿', histRowDn:'跌腿', histCols:['P25','中位','P75','P90','最大'], histNUnit:' 条',
 histNowUp:function(d,rd,g,rg,sc){return '<span class="lbl">当前这一腿（涨腿）在历史'+sc+'涨腿里的位置</span>已走 <b>'+d+'</b> 天，比 <b>'+rd+'%</b> 的历史'+sc+'涨腿长；累计涨 <b>+'+f1(g)+'%</b>，比 <b>'+rg+'%</b> 的历史'+sc+'涨腿涨得多。这一腿还没走完，数字还会变。';},
 histNowDn:function(d,rd,g,rg,sc){return '<span class="lbl">当前这一腿（跌腿）在历史'+sc+'跌腿里的位置</span>已走 <b>'+d+'</b> 天，比 <b>'+rd+'%</b> 的历史'+sc+'跌腿长；已跌 <b>'+f1(g)+'%</b>，比 <b>'+rg+'%</b> 的历史'+sc+'跌腿深。这一腿还没走完，数字还会变。';},
 histRecentH:'最近的几条腿', histRecentCols:['方向','起点 → 终点','天数','幅度'], histOngoing:'进行中',
 histSplitH:'按牛市 / 熊市拆开',
 regTxt:{bull:'牛市',bear:'熊市'}, rowBU:'牛市涨腿', rowBD:'牛市跌腿', rowRU:'熊市涨腿', rowRD:'熊市跌腿',
 histSplitNote:'牛熊用「周期口径」事后标注：顶＝之后 365 天没被超过的历史新高，底＝顶之后到下一次突破前的最低收盘，顶到底算熊市，其余算牛市；腿按终点日归类。这是事后口径，只用来给历史分类，不是实时信号。牛市涨腿 103、牛市跌腿 99、熊市涨腿 49 条，与《加密行情律动-规律清单》V13 一致。',
 histMissing:'历史数据未加载（leg_history.json）。',
 pageTitle:'涨跌腿追踪',
 h1:'涨跌腿追踪',
 lead:'比特币每一腿——涨腿或跌腿——走了多久、涨了或跌了多少？急拉之后山寨币的窗口什么时候开、什么时候关？历史上有什么规律？这一页把规律摆出来，并标出当前读数。',
 callout:'<b>观察工具，不是买卖信号。</b>规律描述的是历史，不预测未来；每条规律都标了证据等级，没验证过的不会当结论。',
 navs:{how:'三个数怎么读',def:'什么算一腿',len:'涨腿一般走多久',dd:'回撤多深',hist:'全部行情的历史',l89:'89天提示线',alt:'山寨轮动窗口',false:'不成立的说法',method:'口径'},
 how_h:'三个数怎么读',
 how_ul:'<li><b>方向</b>：BTC 每天不是在一条涨腿里，就是在一条跌腿里。涨腿结束的那一天，跌腿就开始了。</li><li><b>天数</b>：从起点算起，每天收盘加一。涨腿的起点是低点，跌腿的起点是高点。</li><li><b>幅度</b>：涨腿看起点收盘到目前最高收盘的涨幅；跌腿看高点收盘到目前最低收盘的跌幅。</li><li><b>腿内最大回撤</b>（涨腿）：涨腿里，从某个高点收盘回落的最大幅度。回落到 10%，涨腿结束，换成跌腿。</li>',
 def_h:'什么算一腿',
 def_body:'<p>只看日线收盘价。收盘价从一个摆动低点反向走出 <b>10%</b>，才回头确认那个低点是一条涨腿的起点——低点当天没人知道它会不会继续跌，所以起点只能事后确认。跌腿完全对称：收盘价从高点回落 <b>10%</b>，那个高点就是一条跌腿的起点。</p><p>起点确认之后，天数和涨跌幅<b>每天直接重算</b>，不等这一腿结束。涨腿里收盘从高点回落 10%，涨腿结束、换成跌腿；跌腿里收盘从最低点反弹 10%，跌腿结束、换成涨腿。</p><p>所以「已走多少天」「涨了/跌了多少」每天都在变，不是一腿走完才算一次的数。整个行情（不分牛熊）都被这两种腿覆盖。</p>',
 tag_ver:'已验证', tag_desc:'描述统计·已复现', tag_hyp:'假设', tag_fals:'已证伪',
 len_h:'历史上涨腿一般走多久',
 len_p1:function(){return '2010–2026 年共 <b>'+STATS.bullLegs+'</b> 条牛市涨腿：四分之一不超过 '+STATS.len.p25+' 天，一半不超过 '+STATS.len.p50+' 天，四分之三不超过 '+STATS.len.p75+' 天，十分之九不超过 '+STATS.len.p90+' 天，最长 '+STATS.len.max+' 天。熊市里的反弹更短：'+STATS.bearLegs+' 条，中位 '+STATS.bearMed+' 天。';},
 lenChipK:['P25','中位','P75','P90'], lenUnit:'天',
 lenBucketTxt:['短于大多数历史涨腿（不到 25% 的位置）','长于约 25%–50% 的历史涨腿','长于约 50%–75% 的历史涨腿','长于约 75%–90% 的历史涨腿','已经长于 90% 以上的历史牛市涨腿'],
 lenLive:function(d,b){return '<span class="lbl">当前这一腿（涨腿）</span>已走 <b>'+d+'</b> 天，'+T.zh.lenBucketTxt[b]+'。';},
 len_p2:'注意：这是涨腿「长度」的分布，只说明大多数涨腿走不了太久，<b>不说明走得越久越容易断</b>——后者我们测过，不成立（见下文「不成立的说法」）。',
 dd_h:'回撤多深算正常',
 dd_p1:function(){var d=STATS.dd;return '牛市里一旦出现 10% 以上的回撤，它最终会跌多深？'+d.n+' 次回撤的分布：P25 <b>'+d.p25+'%</b>、中位 <b>'+d.p50+'%</b>、P75 <b>'+d.p75+'%</b>、P90 <b>'+d.p90.toFixed(1)+'%</b>。由早到晚四个年代的中位数依次是 '+d.eras.map(function(x){return x.toFixed(1)+'%'}).join(' → ')+'，带子在变窄：近年回撤的典型深度比早年浅。';},
 ddZone0:'未正式回撤',
 ddLive:function(v){return '<span class="lbl">当前这一腿（涨腿）</span>腿内最大回撤 <b>'+v.toFixed(1)+'%</b>，'+(v<10?'还没到 10%，这一轮上涨仍在继续。':'已达 10%，这一轮上涨已经结束。');},
 dd_p2:'上面的分布带量的是「回撤到 10% 以后最终跌多深」。涨腿进行中时回撤必然小于 10%，指针停在最左边的灰区；一旦回撤到 10%，当前这一腿就变成跌腿，指针按它已经跌的幅度落到右边的档里。',
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
 cardTitle:'涨跌腿追踪', cardSub:'比特币这一腿走到哪了',
 dayPre:'第', dayPost:'天', gainLbl:'距起点涨幅',
 ddK:'腿内最大回撤', ddC:function(){return '历史牛市回撤中位 '+STATS.dd.p50+'%';},
 l89K:'89 天提示线', l89Before:function(n){return '还差 '+n+' 天';}, l89Today:'今天刚到', l89After:function(n){return '已越过 '+n+' 天';},
 l89C:'假设级提示',
 mark89:'89天', asof:'数据截至', cta:'看规律说明 →', staleB:'数据已停更',
 noneT:'方向未定', noneP:'历史价格里还没出现过 10% 的摆动，暂时分不出涨腿或跌腿。',
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
 liveH:'当前这一腿', startK:'起点', confirmK:'确认于', highK:'最高收盘', ddOn:'出现于',
 liveDay:'已走天数', liveGain:'累计涨幅', liveDd:'腿内最大回撤',
 altLiveH:'山寨轮动窗口', stopLineK:'关闭线（D0×0.90）', btcNowK:'BTC 现价', vsLine:'高于关闭线', vsLineNeg:'低于关闭线'
},
en:{
 meterCap:'Ticks: bull-market drawdown percentiles (%)', dirUp:'Up-leg', dirDown:'Down-leg', dnGain:'peak to lowest close',
 dnPeakK:'Now vs peak', dnPeakC:function(l){return 'Peak '+px(l.start_close)+' · '+l.start_date.slice(5);},
 revK:'Rebound line', revC:function(p){return '+'+f1(p)+'% from now · a close above it starts a new up-leg';},
 prevLeg:function(l){return 'Previous leg: '+(l.dir==='up'?'up':'down')+' '+l.start_date+' → '+l.end_date+', '+l.days+' days, '+(l.pct>0?'+':'')+f1(l.pct)+'%';},
 liveDnDay:'Days so far', liveDnDrop:'Drop so far', liveDnPeak:'Peak', liveDnLow:'Lowest close', liveRev:'Rebound line',
 ddBucketTxt:['in the shallowest quarter of historical bull-market drawdowns','deeper than roughly 25%–50% of historical bull-market drawdowns','deeper than roughly 50%–75% of historical bull-market drawdowns','deeper than roughly 75%–90% of historical bull-market drawdowns','already deeper than 90%+ of historical bull-market drawdowns'],
 ddLiveDn:function(v){return '<span class="lbl">Current leg (down)</span>Down <b>'+v.toFixed(1)+'%</b> from the peak, '+t('ddBucketTxt')[ddBucket(v)]+'.';},
 lenLiveDn:function(d){return '<span class="lbl">Current leg (down)</span>Day <b>'+d+'</b>. The distribution above is for up-legs; down-leg durations are in "Whole-market up-legs and down-legs" below.';},
 hist_h:'Whole-market up-legs and down-legs',
 hist_p1:function(H){var s=H.summary,c=H.coverage;return 'The same 10% zigzag, applied to every daily close from <b>'+c.from+'</b> to <b>'+c.to+'</b> ('+c.days.toLocaleString('en-US')+' days), cut into up-legs and down-legs with <b>no bull/bear split</b>. <b>'+s.completed_legs+'</b> completed legs: '+s.up.n+' up, '+s.down.n+' down.'+(c.mode==='partial'?'<br><b>⚠ Early history is incomplete; only the range above is covered, so counts and distributions are understated.</b>':'');},
 histDaysH:'Duration (days)', histMagH:'Size (up-leg = gain, down-leg = drop)', histRowUp:'Up-legs', histRowDn:'Down-legs', histCols:['P25','Median','P75','P90','Max'], histNUnit:'',
 histNowUp:function(d,rd,g,rg,sc){return '<span class="lbl">Where the current up-leg sits among historical '+sc+'up-legs</span>Day <b>'+d+'</b>, longer than <b>'+rd+'%</b> of them; up <b>+'+f1(g)+'%</b>, more than <b>'+rg+'%</b> of them. The leg is not finished, so these numbers will change.';},
 histNowDn:function(d,rd,g,rg,sc){return '<span class="lbl">Where the current down-leg sits among historical '+sc+'down-legs</span>Day <b>'+d+'</b>, longer than <b>'+rd+'%</b> of them; down <b>'+f1(g)+'%</b>, deeper than <b>'+rg+'%</b> of them. The leg is not finished, so these numbers will change.';},
 histRecentH:'Most recent legs', histRecentCols:['Direction','Start → end','Days','Size'], histOngoing:'ongoing',
 histSplitH:'Split by bull / bear market',
 regTxt:{bull:'bull-market ',bear:'bear-market '}, rowBU:'Bull up-legs', rowBD:'Bull down-legs', rowRU:'Bear up-legs', rowRD:'Bear down-legs',
 histSplitNote:'Bull/bear is labelled after the fact with the cycle basis: a top is an all-time high not exceeded for the next 365 days, the bottom is the lowest close between that top and the next breakout; top-to-bottom counts as bear, everything else as bull; each leg is classified by its end date. This is a hindsight label for classifying history, not a real-time signal. Bull up-legs 103, bull down-legs 99 and bear up-legs 49 match the research list V13.',
 histMissing:'History data not loaded (leg_history.json).',
 pageTitle:'Leg Tracker',
 h1:'Leg Tracker',
 lead:'How long does each Bitcoin leg — up or down — last, and how far does it go? After a sharp BTC surge, when does the altcoin window open and close? This page lays out the historical pattern and the current readings.',
 callout:'<b>An observation tool, not a trading signal.</b> The patterns describe history and do not predict the future. Every pattern carries an evidence grade; unverified ones are never presented as conclusions.',
 navs:{how:'Reading the numbers',def:'What is a leg',len:'How long up-legs last',dd:'How deep',hist:'Whole-market history',l89:'Day-89 marker',alt:'Altcoin window',false:'What failed',method:'Method'},
 how_h:'Reading the three numbers',
 how_ul:'<li><b>Direction</b>: every day BTC is inside either an up-leg or a down-leg. The day an up-leg ends, a down-leg begins.</li><li><b>Days</b>: counted from the start, +1 each daily close. An up-leg starts at a low, a down-leg at a high.</li><li><b>Size</b>: for an up-leg, the gain from the start close to the highest close so far; for a down-leg, the drop from the peak close to the lowest close so far.</li><li><b>Max in-leg drawdown</b> (up-legs): the largest close-to-close drop from a peak within the rally. At 10% the up-leg is over and a down-leg begins.</li>',
 def_h:'What counts as a leg',
 def_body:'<p>Daily closes only. A swing low is confirmed as the start of an up-leg once the close has moved <b>10%</b> off it in the opposite direction. On the day of the low nobody knows whether it will fall further, so the start can only be confirmed after the fact. Down-legs are symmetric: once the close falls <b>10%</b> from a high, that high is the start of a down-leg.</p><p>Once the start is confirmed, days and size are <b>recomputed every day</b>; we do not wait for the leg to finish. When an up-leg closes 10% below its peak it ends and a down-leg begins; when a down-leg closes 10% above its low it ends and an up-leg begins.</p><p>So "days so far" and "gain/drop so far" change daily; they are not one-off numbers computed after a leg ends. The whole market (bull and bear alike) is covered by these two kinds of leg.</p>',
 tag_ver:'Verified', tag_desc:'Descriptive · replicated', tag_hyp:'Hypothesis', tag_fals:'Falsified',
 len_h:'How long rallies usually last',
 len_p1:function(){return 'Across 2010–2026 there are <b>'+STATS.bullLegs+'</b> bull-market rallies: a quarter last ≤ '+STATS.len.p25+' days, half ≤ '+STATS.len.p50+', three quarters ≤ '+STATS.len.p75+', nine in ten ≤ '+STATS.len.p90+'; the longest ran '+STATS.len.max+' days. Bear-market bounces are shorter: '+STATS.bearLegs+' of them, median '+STATS.bearMed+' days.';},
 lenChipK:['P25','Median','P75','P90'], lenUnit:' d',
 lenBucketTxt:['shorter than most historical rallies (below the 25th percentile)','longer than roughly 25%–50% of historical rallies','longer than roughly 50%–75% of historical rallies','longer than roughly 75%–90% of historical rallies','already longer than 90%+ of historical bull-market rallies'],
 lenLive:function(d,b){return '<span class="lbl">Current leg (up)</span>Day <b>'+d+'</b>, '+T.en.lenBucketTxt[b]+'.';},
 len_p2:'Note: this is the distribution of rally <b>length</b>. It says most rallies do not last very long; it does <b>not</b> say that older rallies are more likely to break. We tested that, and it does not hold (see "What failed" below).',
 dd_h:'How deep a pullback is normal',
 dd_p1:function(){var d=STATS.dd;return 'Once a bull-market drawdown passes 10%, how deep does it end up? Distribution of '+d.n+' drawdowns: P25 <b>'+d.p25+'%</b>, median <b>'+d.p50+'%</b>, P75 <b>'+d.p75+'%</b>, P90 <b>'+d.p90.toFixed(1)+'%</b>. Medians across the four eras, earliest to latest: '+d.eras.map(function(x){return x.toFixed(1)+'%'}).join(' → ')+'. The band is narrowing: typical drawdowns in recent years are shallower than in early ones.';},
 ddZone0:'not yet a drawdown',
 ddLive:function(v){return '<span class="lbl">Current leg (up)</span>Max in-leg drawdown <b>'+v.toFixed(1)+'%</b>, '+(v<10?'still under 10%, so the rally is still running.':'at 10%, so this rally is over.');},
 dd_p2:'The bands above measure "how deep a drawdown ends up once it reaches 10%". While an up-leg is running its drawdown is always below 10%, so the marker sits in the grey zone on the left; once it hits 10% the current leg becomes a down-leg and the marker moves into the bands on the right according to how far it has fallen.',
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
 cardTitle:'Leg Tracker', cardSub:'Where the current BTC leg stands',
 dayPre:'Day ', dayPost:'', gainLbl:'gain from start',
 ddK:'Max in-leg drawdown', ddC:function(){return 'Historical bull median '+STATS.dd.p50+'%';},
 l89K:'Day-89 marker', l89Before:function(n){return n+' days to go';}, l89Today:'Reached today', l89After:function(n){return n+' days past';},
 l89C:'Hypothesis-grade marker',
 mark89:'Day 89', asof:'Data as of', cta:'How it works →', staleB:'Data stale',
 noneT:'Direction not set', noneP:'No 10% swing has appeared in the price history yet, so there is no up-leg or down-leg to show.',
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
 liveH:'Current leg', startK:'Start', confirmK:'confirmed', highK:'Highest close', ddOn:'on',
 liveDay:'Days so far', liveGain:'Gain so far', liveDd:'Max in-leg drawdown',
 altLiveH:'Altcoin window', stopLineK:'Closing line (D0×0.90)', btcNowK:'BTC now', vsLine:'above the line', vsLineNeg:'below the line'
}};


function t(k){var v=T[lang][k];if(typeof v==='function'){return v.apply(null,[].slice.call(arguments,1));}return v;}
function f1(v){return v.toFixed(1);}
function sg(v){return (v<0?'−':'+')+Math.abs(v).toFixed(1)+'%';}
function fn(x,suf,sign){return x==null?'—':(sign||'')+(+x.toFixed(1))+(suf||'');}
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
function bgsHTML(b,dir){
  return '<span class="bgs">'+(dir==='none'?'':'<span class="badge dir-'+dir+'">'+t(dir==='up'?'dirUp':'dirDown')+'</span>')+(b.badge?'<span class="badge">'+b.badge[lang]+'</span>':'')+'</span>';
}
function btcModuleHTML(b){
  var dir=dirOf(b), pv=prevOf(b);
  var head='<div class="mod-head"><div class="mod-title">'+t('cardTitle')+(lang==='zh'?'<small>Leg Tracker</small>':'')+'</div>'+bgsHTML(b,dir)+'</div><div class="mod-sub">'+t('cardSub')+'</div>';
  var prev=pv?'<div class="prev">'+t('prevLeg',pv)+'</div>':'';
  if(dir==='none'||!b.leg){
    return '<div class="mod m1">'+head+'<div class="empty"><b>'+t('noneT')+'</b>'+t('noneP')+'</div></div>';
  }
  var L=b.leg;
  if(dir==='down'){
    return '<div class="mod m1">'+head
     +'<div class="reading"><div class="big"><small>'+t('dayPre')+'</small>'+L.day+'<small>'+t('dayPost')+'</small></div><div class="gain loss">−'+f1(L.drop_pct)+'%<small>'+t('dnGain')+'</small></div></div>'
     +'<div class="bw">'+meterHTML(L.drop_pct)+'<div class="small muted" style="margin:-18px 0 10px">'+t('meterCap')+'</div></div>'
     +'<div class="tiles"><div class="tile"><div class="k">'+t('dnPeakK')+'</div><div class="v">'+sg(L.from_peak_pct)+'</div><div class="c">'+t('dnPeakC',L)+'</div></div>'
     +'<div class="tile"><div class="k">'+t('revK')+'</div><div class="v">'+px(L.reversal_line)+'</div><div class="c">'+t('revC',L.to_reversal_pct)+'</div></div></div>'+prev+'</div>';
  }
  return '<div class="mod m1">'+head
   +'<div class="reading"><div class="big"><small>'+t('dayPre')+'</small>'+L.day+'<small>'+t('dayPost')+'</small></div><div class="gain">+'+f1(L.gain_pct)+'%<small>'+t('gainLbl')+'</small></div></div>'
   +trackHTML(L.day)
   +'<div class="tiles"><div class="tile"><div class="k">'+t('ddK')+'</div><div class="v">'+f1(L.max_dd_pct)+'%</div><div class="c">'+t('ddC')+'</div></div>'
   +'<div class="tile"><div class="k">'+t('l89K')+'</div><div class="v">'+l89Text(L.day)+'</div><div class="c">'+t('l89C')+'</div></div></div>'+prev+'</div>';
}

function cardHTML(d){
  if(!d||!d.btc_leg||!d.alt_window){return '<div class="card"><div class="errbox">'+t('err')+' · <button type="button" data-leg-retry>'+t('retry')+'</button></div></div>';}
  var stale=isStale(d.asof,TODAY);
  var top=(stale?'<div style="margin-bottom:8px"><span class="badge stale">'+t('staleB')+'</span></div>':'');
  return '<a class="card'+(stale?' is-stale':'')+'" href="'+HREF+'">'+top+btcModuleHTML(d.btc_leg)+altLegModuleHTML(d)+altModuleHTML(d.alt_window,stale)
   +'<div class="card-foot"><span>'+t('asof')+' '+d.asof+'</span><span class="cta">'+t('cta')+'</span></div></a>';
}

function liveHTML(d){
  if(!d||!d.btc_leg||!d.alt_window){return '';}
  var h='';
  var b=d.btc_leg, bdir=dirOf(b);
  if(bdir==='up'&&b.leg){
    var L=b.leg;
    h+='<div class="card panel"><div class="mod-head"><div class="mod-title">'+t('liveH')+' '+bgsHTML({badge:null},'up')+'</div><span class="small muted">'+(isStale(d.asof,TODAY)?'<span class="badge stale">'+t('staleB')+'</span> ':'')+t('asof')+' '+d.asof+'</span></div>'
     +trackHTML(L.day)
     +'<div class="tiles tiles3">'
     +'<div class="tile"><div class="k">'+t('liveDay')+'</div><div class="v">'+L.day+'</div><div class="c">'+t('startK')+' '+L.start_date+'<br>'+px(L.start_close)+'</div></div>'
     +'<div class="tile"><div class="k">'+t('liveGain')+'</div><div class="v">+'+f1(L.gain_pct)+'%</div><div class="c">'+t('highK')+' '+px(L.high_close)+'<br>'+L.high_date+'</div></div>'
     +'<div class="tile"><div class="k">'+t('liveDd')+'</div><div class="v">'+f1(L.max_dd_pct)+'%</div><div class="c">'+t('ddOn')+' '+L.max_dd_date+'</div></div></div>'
     +'<div class="small muted" style="margin-top:8px">'+t('confirmK')+' '+L.confirm_date+'</div></div>';
  } else if(bdir==='down'&&b.leg){
    var D=b.leg;
    h+='<div class="card panel"><div class="mod-head"><div class="mod-title">'+t('liveH')+' '+bgsHTML({badge:null},'down')+'</div><span class="small muted">'+(isStale(d.asof,TODAY)?'<span class="badge stale">'+t('staleB')+'</span> ':'')+t('asof')+' '+d.asof+'</span></div>'
     +'<div class="bw">'+meterHTML(D.drop_pct)+'</div>'
     +'<div class="tiles tiles3">'
     +'<div class="tile"><div class="k">'+t('liveDnDay')+'</div><div class="v">'+D.day+'</div><div class="c">'+t('liveDnPeak')+' '+px(D.start_close)+'<br>'+D.start_date+'</div></div>'
     +'<div class="tile"><div class="k">'+t('liveDnDrop')+'</div><div class="v">−'+f1(D.drop_pct)+'%</div><div class="c">'+t('liveDnLow')+' '+px(D.low_close)+'<br>'+D.low_date+'</div></div>'
     +'<div class="tile"><div class="k">'+t('liveRev')+'</div><div class="v">'+px(D.reversal_line)+'</div><div class="c">'+t('revC',D.to_reversal_pct)+'</div></div></div>'
     +'<div class="small muted" style="margin-top:8px">'+t('confirmK')+' '+D.confirm_date+'</div></div>';
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

function curLegInfo(){
  if(!DATA||!DATA.btc_leg||!DATA.btc_leg.leg){return null;}
  var dir=dirOf(DATA.btc_leg),L=DATA.btc_leg.leg;
  return dir==='up'?{dir:'up',day:L.day,mag:L.gain_pct}:dir==='down'?{dir:'down',day:L.day,mag:L.drop_pct}:null;
}
function histHTML(){
  if(!HIST||!HIST.summary){return '<p class="muted">'+t('histMissing')+'</p>';}
  var S=HIST.summary,C=t('histCols');
  var th='<tr><th></th>'+C.map(function(c){return '<th>'+c+'</th>';}).join('')+'</tr>';
  function row(label,n,st,suf,sign){
    var h='<tr><td>'+label+' <span class="muted small">'+n+t('histNUnit')+'</span></td>';
    ['p25','p50','p75','p90','max'].forEach(function(k){h+='<td>'+(st?fn(st[k],suf,sign):'—')+'</td>';});
    return h+'</tr>';
  }
  var h='<p>'+t('hist_p1',HIST)+'</p>';
  h+='<h3>'+t('histDaysH')+'</h3><table class="t">'+th+row(t('histRowUp'),S.up.n,S.up.days,'')+row(t('histRowDn'),S.down.n,S.down.days,'')+'</table>';
  h+='<h3>'+t('histMagH')+'</h3><table class="t">'+th+row(t('histRowUp'),S.up.n,S.up.gain_pct,'%','+')+row(t('histRowDn'),S.down.n,S.down.drop_pct,'%','−')+'</table>';
  var cur=curLegInfo(), legs=HIST.legs||[], pool=HIST.legs_rank||legs;
  if(cur){
    var rn=HIST.regime_now, scoped=pool.filter(function(l){return l.dir===cur.dir&&l.regime===rn;});
    var same=scoped.length>=10?scoped:pool.filter(function(l){return l.dir===cur.dir;});
    var sc=scoped.length>=10?(t('regTxt')[rn]||''):'';
    if(same.length>=10){
      var rd=pctRank(same.map(function(l){return l.days;}),cur.day);
      var rm=pctRank(same.map(function(l){return Math.abs(l.pct);}),cur.mag);
      h+='<div class="live">'+t(cur.dir==='up'?'histNowUp':'histNowDn',cur.day,rd,cur.mag,rm,sc)+'</div>';
    }
  }
  var rec=legs.slice(-8).reverse();
  if(rec.length){
    h+='<h3>'+t('histRecentH')+'</h3><table class="t small"><tr>'+t('histRecentCols').map(function(c){return '<th>'+c+'</th>';}).join('')+'</tr>';
    rec.forEach(function(l){h+='<tr><td>'+t(l.dir==='up'?'dirUp':'dirDown')+'</td><td>'+l.start_date.slice(2)+' → '+l.end_date.slice(2)+'</td><td>'+l.days+'</td><td>'+sg(l.pct)+'</td></tr>';});
    h+='</table>';
  }
  var R=S.by_regime;
  if(R){
    var rows=[['rowBU',R.bull.up,'up'],['rowBD',R.bull.down,'down'],['rowRU',R.bear.up,'up'],['rowRD',R.bear.down,'down']];
    function rrow(r,which){var st=which==='days'?r[1].days:(r[2]==='up'?r[1].gain_pct:r[1].drop_pct);
      var suf=which==='days'?'':'%', sign=which==='days'?'':(r[2]==='up'?'+':'−');
      var o='<tr><td>'+t(r[0])+' <span class="muted small">'+r[1].n+t('histNUnit')+'</span></td>';
      ['p25','p50','p75','p90','max'].forEach(function(k){o+='<td>'+(st?fn(st[k],suf,sign):'—')+'</td>';});return o+'</tr>';}
    h+='<h3>'+t('histSplitH')+'</h3><h3 class="sub">'+t('histDaysH')+'</h3><table class="t">'+th+rows.map(function(r){return rrow(r,'days');}).join('')+'</table>'
      +'<h3 class="sub">'+t('histMagH')+'</h3><table class="t">'+th+rows.map(function(r){return rrow(r,'mag');}).join('')+'</table>'
      +'<p class="muted small">'+t('histSplitNote')+'</p>';
  }
  return h;
}



/* ===== 山寨整体涨跌腿（站点自写，2026-11-09；设计稿 v3 没有这块，样式照 BTC 涨跌腿模块）=====
   数据 = leg_latest.json 的 alt_leg（schema 4）：成交额前 50 左右的山寨币等权指数，15% 折线。指数点位不展示，只用百分比。 */
var LT={
zh:{t:'山寨整体',sub:function(a){return '成交额前 50 左右的山寨币等权指数 · 15% 折线 · 今日 '+a.basket.coins_today+' 个币';},
 missing:'山寨整体数据未生成', missingP:'今天没取到足够的山寨币日线，明天自动重试。',
 dnK:'现在距高点', dnC:function(l){return '高点 '+l.start_date+' · '+l.confirm_date.slice(5)+' 确认';},
 revK:'反弹确认线', revC:'指数收盘从最低点反弹 15% ＝ 涨腿重新开始',
 upK:'腿内最大回撤', upC:'回撤到 15% 这一腿结束',
 stK:'起点', stC:function(l){return l.confirm_date.slice(5)+' 确认';},
 gainLbl:'距起点涨幅', dropLbl:'高点至最低收盘', excl:'不含 BTC、ETH、稳定币和代币化股票'},
en:{t:'Altcoins overall',sub:function(a){return 'Equal-weight index of ~50 top-volume altcoins · 15% zigzag · '+a.basket.coins_today+' coins today';},
 missing:'Altcoin index not generated', missingP:'Not enough altcoin candles today; it retries tomorrow.',
 dnK:'From the peak', dnC:function(l){return 'Peak '+l.start_date+' · confirmed '+l.confirm_date.slice(5);},
 revK:'Reversal line', revC:'A 15% bounce off the low restarts an up-leg',
 upK:'Max in-leg drawdown', upC:'A 15% pullback ends the leg',
 stK:'Start', stC:function(l){return 'confirmed '+l.confirm_date.slice(5);},
 gainLbl:'gain from start', dropLbl:'peak to lowest close', excl:'Excludes BTC, ETH, stablecoins and tokenized stocks'}};
function lt(k){var v=LT[lang][k];if(typeof v==='function'){return v.apply(null,[].slice.call(arguments,1));}return v;}
function altLegModuleHTML(d){
  var a=d.alt_leg;
  if(!a||!a.leg||!a.basket){return '<div class="mod m3"><div class="mod-head"><div class="mod-title">'+lt('t')+'</div></div><div class="empty"><b>'+lt('missing')+'</b>'+lt('missingP')+'</div></div>';}
  var dir=dirOf(a), L=a.leg, pv=prevOf(a);
  function tile(k,v,c){return '<div class="tile"><div class="k">'+k+'</div><div class="v">'+v+'</div><div class="c">'+c+'</div></div>';}
  var head='<div class="mod-head"><div class="mod-title">'+lt('t')+'</div>'+bgsHTML({badge:null},dir)+'</div><div class="mod-sub">'+lt('sub',a)+'</div>';
  var prev=pv?'<div class="prev">'+t('prevLeg',pv)+'</div>':'';
  var big='<div class="reading"><div class="big"><small>'+t('dayPre')+'</small>'+L.day+'<small>'+t('dayPost')+'</small></div>';
  var body;
  if(dir==='down'){
    body=big+'<div class="gain loss">−'+f1(L.drop_pct)+'%<small>'+lt('dropLbl')+'</small></div></div>'
      +'<div class="tiles">'+tile(lt('dnK'),sg(L.from_peak_pct),lt('dnC',L))+tile(lt('revK'),'+'+f1(L.to_reversal_pct)+'%',lt('revC'))+'</div>';
  }else{
    body=big+'<div class="gain">+'+f1(L.gain_pct)+'%<small>'+lt('gainLbl')+'</small></div></div>'
      +'<div class="tiles">'+tile(lt('upK'),f1(L.max_dd_pct)+'%',lt('upC'))+tile(lt('stK'),L.start_date,lt('stC',L))+'</div>';
  }
  return '<div class="mod m3">'+head+body+prev+'<div class="prev muted">'+lt('excl')+'</div></div>';
}
function altLegOk(a){
  if(a==null){return true;}
  if(!a.leg||!a.basket){return false;}
  var dir=dirOf(a), ks=dir==='down'?['start_date','confirm_date','day','drop_pct','from_peak_pct','to_reversal_pct']:dir==='up'?['start_date','confirm_date','day','gain_pct','max_dd_pct']:null;
  if(!ks){return false;}
  for(var i=0;i<ks.length;i++){if(a.leg[ks[i]]==null){return false;}}
  return true;
}

/* ===== 总渲染（站点版：设计稿 renderAll / load 改写，去掉预览与示例数据） ===== */
var UPK=['start_date','start_close','confirm_date','day','gain_pct','high_close','high_date','max_dd_pct','max_dd_date'];
var DNK=['start_date','start_close','confirm_date','day','drop_pct','low_close','low_date','btc_close','from_peak_pct','reversal_line','to_reversal_pct'];
function okData(d){
  if(!d||!d.asof||!d.btc_leg||!d.alt_window){return false;}
  var b=d.btc_leg,a=d.alt_window,dir=dirOf(b);
  if(dir==='up'||dir==='down'){var L=b.leg;if(!L){return false;}
    var ks=dir==='up'?UPK:DNK;for(var i=0;i<ks.length;i++){if(L[ks[i]]==null){return false;}}}
  else if(dir!=='none'){return false;}
  if(!T[lang].stg[a.stage]){return false;}
  var need={pending:['ignition_date','d0_date'],idle:[]}[a.stage]||['d0_date','d0_close','n','days_to_clear','clear_date','stop_line','btc_close'];
  for(var j=0;j<need.length;j++){if(a[need[j]]==null){return false;}}
  if(a.stage==='stopped'&&a.stopped_date==null){return false;}
  return altLegOk(d.alt_leg);
}
var DATA=null, HIST=null, TRIED=false;
function $(id){return document.getElementById(id);}
function renderPage(){
  document.querySelectorAll('#leg-page [data-i18n]').forEach(function(el){var v=t(el.getAttribute('data-i18n'));if(v!=null)el.innerHTML=v;});
  var navs=t('navs');$('legChips').innerHTML=Object.keys(navs).map(function(k){return '<a href="#'+k+'">'+navs[k]+'</a>';}).join('');
  $('liveMount').innerHTML=!TRIED?'':DATA?liveHTML(DATA)+'<div class="card panel lgalt">'+altLegModuleHTML(DATA)+'</div>':'<div class="card"><div class="errbox">'+t('err')+' · <button type="button" data-leg-retry>'+t('retry')+'</button></div></div>';
  var curDir=(DATA&&DATA.btc_leg&&DATA.btc_leg.leg)?dirOf(DATA.btc_leg):'none';
  var active=curDir==='up'?DATA.btc_leg.leg:null, down=curDir==='down'?DATA.btc_leg.leg:null;
  $('lenChips').innerHTML=['p25','p50','p75','p90'].map(function(k,i){return '<div class="tile"><div class="k">'+t('lenChipK')[i]+'</div><div class="v">'+STATS.len[k]+t('lenUnit')+'</div></div>';}).join('');
  $('lenPinMount').innerHTML=active?'<div class="pin" style="left:'+lenPos(active.day)+'%"><span>'+t('dayPre')+active.day+t('dayPost')+'</span></div>':'';
  $('lenLive').style.display=(active||down)?'':'none';
  if(active){$('lenLive').innerHTML=t('lenLive',active.day,lenBucket(active.day));}
  else if(down){$('lenLive').innerHTML=t('lenLiveDn',down.day);}
  $('ddMeter').innerHTML=meterHTML(active?active.max_dd_pct:down?down.drop_pct:null);
  $('ddLegend').innerHTML='<span>'+t('ddZone0')+' &lt; 10%</span><span>P25 '+STATS.dd.p25+'%</span><span>'+(lang==='zh'?'中位':'Median')+' '+STATS.dd.p50+'%</span><span>P75 '+STATS.dd.p75+'%</span><span>P90 '+f1(STATS.dd.p90)+'%</span>';
  $('ddLive').style.display=(active||down)?'':'none';
  if(active){$('ddLive').innerHTML=t('ddLive',active.max_dd_pct);}
  else if(down){$('ddLive').innerHTML=t('ddLiveDn',down.drop_pct);}
  $('histMount').innerHTML=TRIED?histHTML():'';
  $('l89Bars').innerHTML=l89BarsHTML();
  $('altStatic').innerHTML=altBarHTML({stage:'idle'},false);
  $('altTable').innerHTML=altTableHTML();
  $('f1Table').innerHTML=f1TableHTML();
  $('statsAsof').textContent=t('statsAsof');
}
function render(){if(root.id==='leg-card'){root.innerHTML=cardHTML(DATA);}else{renderPage();}}
function getJSON(u){return fetch(u,{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();});}
function load(){
  var p1=getJSON(SRC).then(function(j){DATA=okData(j)?j:null;},function(){DATA=null;});
  var p2=HSRC?getJSON(HSRC).then(function(j){HIST=j;},function(){HIST=null;}):Promise.resolve();
  Promise.all([p1,p2]).then(function(){TRIED=true;render();});
}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-leg-retry]');if(b){e.preventDefault();load();}});
if(root.id==='leg-page'){render();}
load();
})();
