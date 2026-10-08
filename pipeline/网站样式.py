# -*- coding: utf-8 -*-
"""链上大叔研究台 · 网站视觉系统与前端脚本（出网站.py 引用）

  SITE_CSS    全站样式。所有颜色走 CSS 变量：深色（默认，终端风）/ 浅色两套，<html data-theme> 切换。
  HEAD_JS     放在 <head> 里最先执行：读本地保存的主题，避免页面先白后黑闪一下。
  UI_JS       太阳 / 月亮单按钮切换主题（记在 localStorage）。
  CHART_JS    交互式走势图（纯 SVG，无第三方库）：时间范围按钮、阈值线、历史分位带、十字线 + 悬停读数、同页多图联动、
              堆叠面积（金额 / 份额切换）、对数坐标。数据从 /data/... 的 JSON 读。
  SHARE_JS    一键生成分享长图（html2canvas，长图固定深色水印版）。

视觉：深色底 #05070c · 卡片 #0b0e17 · 1px rgba(255,255,255,.06) 细线 · 涨 #00ffcc · 跌 #ff3366；
      浅色底 #f5f7fa · 卡片 #fff · 涨 #059669 · 跌 #e11d48。品牌青柠只用在导航和按钮上，不用在数字上。
      多序列图用经过色盲校验的 8 色分类色板（固定顺序，颜色跟着实体走，不跟排名走），第 9 个起并入「其他」。
"""

SITE_CSS = r"""
:root,:root[data-theme="dark"]{--bg:#05070c;--card:#0b0e17;--card2:#10141f;--line:rgba(255,255,255,.06);--line2:rgba(255,255,255,.11);
--ink:#e8ecf3;--ink2:#a7afc0;--muted:#7f889c;--up:#00ffcc;--dn:#ff3366;--warn:#ffb020;--cool:#5b8cff;--lime:#a3e635;--lime-ink:#a3e635;
--on-lime:#05070c;--up-bg:rgba(0,255,204,.08);--dn-bg:rgba(255,51,102,.09);--warn-bg:rgba(255,176,32,.09);--cool-bg:rgba(91,140,255,.10);
--up-bd:rgba(0,255,204,.35);--dn-bd:rgba(255,51,102,.4);--warn-bd:rgba(255,176,32,.4);--cool-bd:rgba(91,140,255,.45);
--lime-bg:rgba(163,230,53,.07);--lime-bd:rgba(163,230,53,.45);--hover:rgba(255,255,255,.035);--wash:rgba(255,255,255,.015);
--glass1:rgba(255,255,255,.035);--glass2:rgba(255,255,255,.01);--side:rgba(7,9,15,.92);--topbar:rgba(5,7,12,.9);--thead:#0d111b;
--glow1:rgba(0,255,204,.07);--glow2:rgba(163,230,53,.05);--scrim:rgba(0,0,0,.55);--toast:#11161f;--grid:rgba(255,255,255,.06);
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;--s9:#5b6274;
--l2-bull:#22c55e;--l2-risk:#f97316;--l2-pb:#fdba74;--l2-bear:#ef4444;--l2-zone:#a855f7;--l2-rec:#3b82f6;
--c-solana:#c084fc;--c-robinhood:#4ade80;--c-bsc:#fbbf24;--c-base:#60a5fa;--c-arc:#22d3ee;--c-monad:#a78bfa;--c-ethereum:#94a3b8;--c-other:#4b5364;
--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
color-scheme:dark}
:root[data-theme="light"]{--bg:#f5f7fa;--card:#ffffff;--card2:#f0f3f7;--line:rgba(15,23,42,.08);--line2:rgba(15,23,42,.15);
--ink:#0f172a;--ink2:#475569;--muted:#64748b;--up:#059669;--dn:#e11d48;--warn:#b45309;--cool:#2563eb;--lime:#a3e635;--lime-ink:#4d7c0f;
--on-lime:#14210a;--up-bg:rgba(5,150,105,.08);--dn-bg:rgba(225,29,72,.07);--warn-bg:rgba(180,83,9,.08);--cool-bg:rgba(37,99,235,.08);
--up-bd:rgba(5,150,105,.35);--dn-bd:rgba(225,29,72,.35);--warn-bd:rgba(180,83,9,.35);--cool-bd:rgba(37,99,235,.35);
--lime-bg:rgba(132,204,22,.12);--lime-bd:rgba(77,124,15,.45);--hover:rgba(15,23,42,.04);--wash:rgba(15,23,42,.02);
--glass1:rgba(255,255,255,.92);--glass2:rgba(255,255,255,.80);--side:rgba(255,255,255,.94);--topbar:rgba(255,255,255,.92);--thead:#f3f5f8;
--glow1:rgba(5,150,105,.06);--glow2:rgba(132,204,22,.07);--scrim:rgba(15,23,42,.35);--toast:#ffffff;--grid:rgba(15,23,42,.07);
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#4a3aa7;--s8:#e34948;--s9:#94a3b8;
--l2-bull:#16a34a;--l2-risk:#ea580c;--l2-pb:#f59e0b;--l2-bear:#dc2626;--l2-zone:#9333ea;--l2-rec:#2563eb;
--c-solana:#9333ea;--c-robinhood:#16a34a;--c-bsc:#b45309;--c-base:#2563eb;--c-arc:#0891b2;--c-monad:#7c3aed;--c-ethereum:#64748b;--c-other:#94a3b8;
color-scheme:light}
*{box-sizing:border-box}
html,body{background:var(--bg);margin:0}
body{color:var(--ink);font:14.5px/1.65 var(--sans);-webkit-font-smoothing:antialiased;min-height:100vh}
body:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
background:radial-gradient(700px 420px at 12% -8%,var(--glow1),transparent 70%),radial-gradient(640px 420px at 100% 108%,var(--glow2),transparent 70%)}
a{color:inherit}
a:hover{color:var(--lime-ink)}
.num,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
svg.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* ---- 外壳：左侧常驻导航 ---- */
.side{position:fixed;top:0;left:0;bottom:0;width:236px;z-index:30;background:var(--side);
border-right:1px solid var(--line);display:flex;flex-direction:column;padding:18px 14px;backdrop-filter:blur(12px)}
.brand{display:flex;align-items:center;gap:11px;text-decoration:none;padding:4px 6px 14px}
.brand .av{width:38px;height:38px;border-radius:50%;box-shadow:0 0 0 1.5px var(--lime),0 0 18px rgba(163,230,53,.25)}
.brand b{display:block;font-size:15px;font-weight:700;letter-spacing:.2px;color:var(--ink)}
.brand i{display:block;font-style:normal;font-family:var(--mono);font-size:9.5px;letter-spacing:1.4px;color:var(--muted);margin-top:2px}
.tools{display:flex;align-items:center;gap:8px;padding:0 6px 14px;border-bottom:1px solid var(--line);margin-bottom:10px}
.lang{display:inline-flex;border:1px solid var(--line2);border-radius:8px;overflow:hidden;font:600 11.5px/1 var(--sans)}
.lang a{padding:6px 10px;text-decoration:none;color:var(--ink2)}
.lang a.on{background:var(--lime);color:var(--on-lime)}
.lang a:not(.on):hover{background:var(--hover);color:var(--ink)}
.thm{display:inline-flex;align-items:center;justify-content:center;width:30px;height:28px;border:1px solid var(--line2);border-radius:8px;
background:transparent;color:var(--ink2);cursor:pointer;padding:0}
.thm:hover{color:var(--ink);background:var(--hover)}
.thm .sun{display:none}.thm .moon{display:block}
:root[data-theme="light"] .thm .sun{display:block}:root[data-theme="light"] .thm .moon{display:none}
.snav{display:flex;flex-direction:column;gap:2px;flex:1;overflow-y:auto}
.sgrp{font-family:var(--mono);font-size:10px;letter-spacing:1.6px;color:var(--muted);padding:12px 10px 6px;text-transform:uppercase}
.snav a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;text-decoration:none;color:var(--ink2);
font-size:13.5px;position:relative;transition:background .15s,color .15s}
.snav a:hover{background:var(--hover);color:var(--ink)}
.snav a.on{background:var(--lime-bg);color:var(--ink)}
.snav a.on:before{content:"";position:absolute;left:-14px;top:7px;bottom:7px;width:3px;border-radius:0 3px 3px 0;background:var(--lime)}
.snav a.on svg.ic{color:var(--lime-ink)}
.sfoot{border-top:1px solid var(--line);padding:14px 6px 0;font-size:11.5px;color:var(--muted);line-height:1.6}
.live{display:flex;align-items:center;gap:7px;font-family:var(--mono);font-size:10.5px;color:var(--ink2)}
.live i{width:7px;height:7px;border-radius:50%;background:var(--up);box-shadow:0 0 8px var(--up);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.35}}
.sfoot a{display:inline-block;margin-top:8px;color:var(--ink2);text-decoration:none;font-family:var(--mono);font-size:11.5px}
.sfoot p{margin:8px 0 0;font-size:10.5px}
.main{margin-left:236px;position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column}
.mi{width:100%;max-width:1280px;margin:0 auto;padding:26px 36px 56px;flex:1}
.mi.narrow{max-width:900px}
.foot{border-top:1px solid var(--line);color:var(--muted);font-size:11.5px;padding:18px 36px;display:flex;gap:10px 22px;flex-wrap:wrap}
.foot a{color:var(--muted)}
.topbar{display:none}
.navtg{display:none}
@media (max-width:960px){
 .side{transform:translateX(-100%);transition:transform .2s;width:264px}
 .navtg:checked~.side{transform:none}
 .navtg:checked~.scrim{display:block}
 .scrim{display:none;position:fixed;inset:0;background:var(--scrim);z-index:25}
 .main{margin-left:0}
 .topbar{display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:20;padding:10px 16px;
  background:var(--topbar);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}
 .topbar label{cursor:pointer;display:flex;padding:6px;border:1px solid var(--line2);border-radius:8px}
 .topbar .home{display:flex;align-items:center;gap:8px;text-decoration:none;font-weight:700;font-size:14px;min-width:0}
 .topbar .home span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .topbar img{width:26px;height:26px;border-radius:50%;box-shadow:0 0 0 1.5px var(--lime)}
 .topbar .sp{flex:1}
 .mi{padding:18px 16px 40px}
 .ph .stamp{text-align:left}
 .foot{padding:16px}
}

/* ---- 面包屑 ---- */
.crumbs{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;font-size:13px;color:var(--muted);margin:0 0 14px}
.crumbs a{padding:6px 0}
.crumbs a{color:var(--ink2);text-decoration:none;border-bottom:1px dashed var(--line2)}
.crumbs a:hover{color:var(--lime-ink);border-color:var(--lime-ink)}
.crumbs .sep{opacity:.6}
.crumbs .cur{color:var(--ink)}

/* ---- 页头 ---- */
.ph{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 24px;margin-bottom:22px}
.eyebrow{font-family:var(--mono);font-size:10.5px;letter-spacing:1.8px;color:var(--lime-ink);text-transform:uppercase}
h1{font:700 26px/1.25 var(--sans);letter-spacing:-.2px;margin:6px 0 0}
h2{font:600 17px/1.35 var(--sans);margin:34px 0 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
h2 .sub{font-weight:400;font-size:12.5px;color:var(--muted)}
h3{font:600 14.5px/1.4 var(--sans);margin:22px 0 8px}
.lede{color:var(--ink2);max-width:78ch;margin:10px 0 0;font-size:14px}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted);text-align:right;line-height:1.7}
.stamp b{color:var(--ink2);font-weight:500}
.note{border:1px dashed var(--line2);border-radius:10px;padding:10px 14px;font-size:12.5px;color:var(--ink2);margin:0 0 16px;background:var(--wash)}

/* ---- 卡片 ---- */
.glass{background:linear-gradient(180deg,var(--glass1),var(--glass2));border:1px solid var(--line);
border-radius:14px;backdrop-filter:blur(14px) saturate(140%);-webkit-backdrop-filter:blur(14px) saturate(140%)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px}
.grid{display:grid;gap:12px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}.g5{grid-template-columns:repeat(5,minmax(0,1fr))}
@media(max-width:1100px){.g4,.g5{grid-template-columns:repeat(2,minmax(0,1fr))}.g3{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.g4,.g3,.g2,.g5{grid-template-columns:1fr}}

.verdict{padding:20px 22px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:14px;position:relative;overflow:hidden}
.verdict:after{content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%;
background:radial-gradient(circle,var(--glow1),transparent 70%)}
.verdict .lbl{font-family:var(--mono);font-size:10px;letter-spacing:1.6px;color:var(--muted);text-transform:uppercase}
.verdict .txt{font-size:17px;font-weight:600;line-height:1.5;margin:6px 0 10px;max-width:70ch}
.verdict .body{flex:1;min-width:260px}
.l1line{font-family:var(--mono);font-size:11.5px;color:var(--ink2);line-height:1.7;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line2);word-break:break-word}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;padding:3px 9px;border-radius:999px;
border:1px solid var(--line2);color:var(--ink2);white-space:nowrap}
.chip i{width:6px;height:6px;border-radius:50%;background:currentColor}
.t-up{color:var(--up)}.t-dn{color:var(--dn)}.t-warn{color:var(--warn)}.t-cool{color:var(--cool)}.t-neutral{color:var(--ink2)}
.chip.t-up{border-color:var(--up-bd);background:var(--up-bg)}.chip.t-dn{border-color:var(--dn-bd);background:var(--dn-bg)}
.chip.t-warn{border-color:var(--warn-bd);background:var(--warn-bg)}.chip.t-cool{border-color:var(--cool-bd);background:var(--cool-bg)}
.grade{font-family:var(--mono);font-size:9.5px;border-radius:4px;padding:0 5px;border:1px solid var(--line2);color:var(--muted);white-space:nowrap;font-weight:400}
.grade.g-v{color:var(--up);border-color:var(--up-bd)}.grade.g-d{color:var(--cool);border-color:var(--cool-bd)}.grade.g-o{color:var(--warn);border-color:var(--warn-bd)}

.hero{padding:16px 18px 12px;position:relative;overflow:hidden;text-decoration:none;display:block}
.hero .k{font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between;gap:8px}
.hero .k span{font-family:var(--mono);font-size:10px;letter-spacing:.6px}
.hero .v{font:600 25px/1.2 var(--mono);letter-spacing:-.5px;margin:8px 0 4px}
.hero .s{font-size:12px;color:var(--ink2)}
.hero svg.spk{margin-top:10px;width:100%;height:34px}
a.hero:hover{border-color:var(--line2)}

.sig{padding:16px 18px;text-decoration:none;display:block;border-top:2px solid var(--line2)}
.sig:hover{background:var(--card2);color:inherit}
.sig .n{font-family:var(--mono);font-size:10px;letter-spacing:1.4px;color:var(--muted)}
.sig .q{font-size:12px;color:var(--muted);margin-top:2px}
.sig .v{font-size:15px;font-weight:600;margin:10px 0 8px;line-height:1.4}
.sig ul{list-style:none;margin:0;padding:0;font-size:12px;color:var(--ink2)}
.sig li{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-top:1px dashed var(--line)}
.sig li b{font-family:var(--mono);font-weight:500;color:var(--ink);text-align:right}
.sig.t-up{border-top-color:var(--up)}.sig.t-dn{border-top-color:var(--dn)}.sig.t-warn{border-top-color:var(--warn)}.sig.t-cool{border-top-color:var(--cool)}

/* ---- 异动预警看台 ---- */
.board{padding:0;overflow:hidden}
.board-hd{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.board-hd b{font-size:13.5px}
.board-hd .dot{width:8px;height:8px;border-radius:50%;background:var(--dn);box-shadow:0 0 10px var(--dn);animation:pulse 1.6s infinite}
.board-hd .sp{flex:1}
.ticker{overflow:hidden;white-space:nowrap;border-bottom:1px solid var(--line);background:var(--wash);
-webkit-mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent);mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent)}
.ticker-track{display:inline-flex;gap:38px;padding:9px 0;animation:tick 70s linear infinite;font-family:var(--mono);font-size:12px}
.ticker:hover .ticker-track{animation-play-state:paused}
.ticker-track span{color:var(--ink2)}.ticker-track span b{font-weight:500}
@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker-track{animation:none}}
.alerts{list-style:none;margin:0;padding:6px 0}
.alerts li{display:flex;gap:12px;align-items:flex-start;padding:8px 16px;font-size:13px;border-bottom:1px solid var(--line)}
.alerts li:last-child{border-bottom:none}
.alerts .lv{font-family:var(--mono);font-size:10px;padding:1px 6px;border-radius:4px;flex:none;margin-top:2px}
.alerts .lv.h{color:var(--dn);background:var(--dn-bg);border:1px solid var(--dn-bd)}
.alerts .lv.m{color:var(--warn);background:var(--warn-bg);border:1px solid var(--warn-bd)}
.alerts .d{font-family:var(--mono);font-size:11px;color:var(--muted);flex:none;margin-top:1px}
.quiet{padding:14px 16px;color:var(--muted);font-size:13px}

.btn{display:inline-flex;align-items:center;gap:7px;font:600 12px/1 var(--sans);padding:8px 12px;border-radius:8px;
border:1px solid var(--lime-bd);color:var(--lime-ink);background:var(--lime-bg);cursor:pointer;text-decoration:none;white-space:nowrap}
.btn:hover{filter:brightness(1.1);color:var(--lime-ink)}
.btn.ghost{border-color:var(--line2);color:var(--ink2);background:transparent}
.btn.ghost:hover{color:var(--ink);border-color:var(--ink2)}
.toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);opacity:0;z-index:99;
background:var(--toast);border:1px solid var(--line2);color:var(--ink);padding:10px 16px;border-radius:10px;font-size:13px;transition:.25s;pointer-events:none}
.toast.on{opacity:1;transform:translateX(-50%)}

/* ---- 指标卡（宏观仪表盘） ---- */
.layer{margin-top:34px;scroll-margin-top:20px}
.layer-hd{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;margin-bottom:12px}
.layer-hd .no{font-family:var(--mono);font-size:11px;color:var(--lime-ink);border:1px solid var(--lime-bd);border-radius:6px;padding:2px 7px}
.layer-hd h2{margin:0}
.layer-hd .why{font-size:12.5px;color:var(--muted);width:100%}
.grp{font-family:var(--mono);font-size:10.5px;letter-spacing:1.2px;color:var(--muted);margin:18px 0 8px;display:flex;align-items:center;gap:10px}
.grp:after{content:"";flex:1;height:1px;background:var(--line)}
a.ind{text-decoration:none;color:inherit;transition:border-color .15s,background .15s}
a.ind:hover{border-color:var(--lime-bd);background:var(--card2);color:inherit}
.ind{padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-height:168px}
.ind .top{display:flex;justify-content:space-between;align-items:flex-start;gap:6px 8px;flex-wrap:wrap}
.ind .top .chip{flex:none}
.ind .nm{font-size:13px;font-weight:600;display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center;min-width:0;flex:1 1 150px}
.ind .v{font:600 22px/1.2 var(--mono);letter-spacing:-.4px}
.ind .b{font-size:12px;color:var(--ink2)}
.ind .ft{margin-top:auto;display:flex;justify-content:space-between;gap:8px;font-size:10.5px;color:var(--muted);font-family:var(--mono)}
.ind .ft .stale{color:var(--warn)}
.ind .ft .go{color:var(--lime-ink)}
.ind svg.spk{width:100%;height:32px}
.ind.obs{opacity:.75}
.pend{padding:12px 14px;border:1px dashed var(--line2);border-radius:12px;font-size:12px;color:var(--muted)}
.pend b{display:block;color:var(--ink2);font-size:12.5px;margin-bottom:3px;font-weight:600}
.src{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}

/* ---- FAQ ---- */
.l2card{position:relative;padding:18px 20px 16px 24px;border-left:4px solid var(--l2c,var(--line2));margin-bottom:14px}
.l2card .eb{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:11.5px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase}
.l2card h3.st{margin:8px 0 4px;font-size:22px;line-height:1.3;color:var(--l2c,var(--ink))}
.l2card h3.st span{font-size:15px;color:var(--ink2);font-weight:500}
.l2card .desc{color:var(--ink2);font-size:13.5px;margin:0 0 10px}
.l2nums{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:var(--muted);margin:6px 0 4px}
.l2nums b{font-family:var(--mono);color:var(--ink);font-weight:600;margin-left:4px}
.l2sum{font-size:13px;line-height:1.75;color:var(--ink2);margin-top:10px;padding-top:10px;border-top:1px dashed var(--line2)}
.l2sum div:first-child{color:var(--ink);font-weight:600}
.l2next{margin-top:10px;padding:10px 12px;border-radius:10px;background:var(--wash);border:1px solid var(--line);font-size:13px;color:var(--ink2);line-height:1.7}
.l2next b{color:var(--ink)}
.chip.l2chg{background:var(--warn-bg);border-color:var(--warn-bd);color:var(--warn)}
.chip.l2stale{background:var(--wash);border-color:var(--line2);color:var(--muted)}
.l2val .v{font-family:var(--mono);font-size:20px;color:var(--ink)}
.l2val .k{font-size:12px;color:var(--muted)}.l2val .s{font-size:11.5px;color:var(--muted);margin-top:2px}
.l2val>div{padding:12px 14px}
@media(max-width:640px){.grid.g3.l2val{grid-template-columns:repeat(2,minmax(0,1fr))}.l2val .v{font-size:17px}}
.l2sig{padding:12px 14px}
.l2sig h4{margin:0 0 8px;font-size:13px;display:flex;justify-content:space-between;gap:8px}
.l2sig h4 span{font-weight:400;color:var(--muted);font-family:var(--mono)}
.l2sig ul{list-style:none;margin:0;padding:0;display:grid;gap:9px}
.l2sig li{display:grid;grid-template-columns:14px 1fr;gap:8px;font-size:13px;line-height:1.5}
.l2sig .dot{width:10px;height:10px;border-radius:50%;margin-top:5px;border:1.5px solid var(--muted)}
.l2sig li.on .dot{background:var(--l2d,var(--up));border-color:var(--l2d,var(--up))}
.l2sig li:not(.on) .nm{color:var(--ink2)}
.l2sig .meta{display:flex;flex-wrap:wrap;gap:4px 6px;margin-top:3px;align-items:center}
.l2sig .ev{font-size:10.5px;padding:1px 6px;border-radius:6px;border:1px solid var(--line2);color:var(--ink2)}
.l2sig .ref{font-size:10.5px;color:var(--muted);font-family:var(--mono)}
.l2sig .td{font-size:10.5px;padding:1px 6px;border-radius:6px;background:var(--warn-bg);color:var(--warn);border:1px solid var(--warn-bd)}
.l2sig .nt{font-size:12px;color:var(--muted);margin-top:2px}
.ladder{padding:8px 0}
.ladder .rw{display:grid;grid-template-columns:1fr auto 64px;gap:10px;padding:7px 16px;font-size:13px;align-items:center}
.ladder .rw+.rw{border-top:1px solid var(--line)}
.ladder .rw .val{font-family:var(--mono);color:var(--ink)}
.ladder .rw .pc{font-family:var(--mono);text-align:right}
.ladder .up .pc{color:var(--dn)}.ladder .dn .pc{color:var(--up)}
.ladder .now{background:var(--lime-bg);border-top:1px solid var(--lime-bd)!important;border-bottom:1px solid var(--lime-bd)}
.ladder .now b{color:var(--lime-ink)}
.l2leg{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--ink2);margin:4px 0 8px}
.l2leg i{display:inline-block;width:12px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px;opacity:.55}
.l2disc{font-size:12px;color:var(--muted);line-height:1.7;margin:10px 2px 0}
.faqs{display:grid;gap:8px}
.faq summary{cursor:pointer;padding:12px 16px;font-weight:600;font-size:13.5px;list-style:none;display:flex;justify-content:space-between;gap:10px}
.faq summary::-webkit-details-marker{display:none}
.faq summary:after{content:"+";color:var(--muted);font-family:var(--mono)}
.faq[open] summary:after{content:"−"}
.faq p{margin:0;padding:0 16px 14px;color:var(--ink2);font-size:13.5px;line-height:1.75}


/* ---- 综合研判（四层合成） ---- */
.verdict.comp .txt{font-size:18px}
.segd{margin-top:10px}.segd>summary{cursor:pointer;font-size:12px;color:var(--muted);padding:4px 0;list-style:none}
.segd>summary::-webkit-details-marker{display:none}.segd>summary:before{content:"▸ ";}.segd[open]>summary:before{content:"▾ "}
@media(min-width:641px){.segd>summary{display:none}}
.segs{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:8px}
.segs li{display:grid;grid-template-columns:44px 1fr;gap:10px;align-items:start;font-size:13.5px;line-height:1.65;color:var(--ink2)}
.segs li b{color:var(--ink);margin-right:6px}
.segs .num{font-family:var(--mono);color:var(--ink);font-size:12.5px}
a.chip,a.lb{text-decoration:none}
.lb{display:inline-flex;align-items:center;gap:5px;font:600 11px/1 var(--mono);padding:5px 7px;border-radius:7px;border:1px solid var(--line2);text-decoration:none;justify-content:center;min-height:26px}
.lb i{width:7px;height:7px;border-radius:50%;background:currentColor}
.lb.t-up{border-color:var(--up-bd);background:var(--up-bg)}.lb.t-dn{border-color:var(--dn-bd);background:var(--dn-bg)}.lb.t-warn{border-color:var(--warn-bd);background:var(--warn-bg)}
.chg{display:inline-block;font:600 10px/1 var(--sans);padding:3px 5px;border-radius:5px;background:var(--warn-bg);color:var(--warn);border:1px solid var(--warn-bd);margin-left:6px;vertical-align:1px;cursor:help}
.chip.rel{font-size:11px}
.stamp.tl{text-align:left;margin-top:10px}
.grade.g-x{color:var(--dn);border-color:var(--dn-bd)}
.grade.lv{color:var(--ink2);background:var(--wash)}
/* ---- 四层 Tab ---- */
.tabwrap{position:sticky;top:0;z-index:15;background:var(--bg);margin:18px -4px 0;padding:8px 4px 0;border-bottom:1px solid var(--line)}
@media(max-width:960px){.tabwrap{top:49px}}
.tabs{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:1 0 auto;min-width:150px;display:flex;flex-direction:column;gap:3px;padding:9px 12px;border:1px solid var(--line);border-bottom:none;border-radius:10px 10px 0 0;
text-decoration:none;color:var(--ink2);background:var(--card);position:relative;min-height:44px}
.tab:hover{color:var(--ink);background:var(--card2)}
.tab.on{background:var(--card2);color:var(--ink);box-shadow:inset 0 2px 0 var(--lime)}
.tab .tn{font:600 12.5px/1.3 var(--sans);display:flex;align-items:center;gap:6px;white-space:nowrap}
.tab .tn em{font-style:normal;font-weight:500;color:var(--muted)}
.tab .ts{font-size:12px;white-space:nowrap}
.tab .dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex:none}
.tab .chg{position:absolute;top:6px;right:8px;margin:0}
@media(max-width:640px){.tab{min-width:118px;padding:8px 10px}.tab .tn em{display:none}}
.tabp:focus{outline:none}
html.js .tabp{display:none}html.js .tabp.on{display:block}
.tabp{margin-top:18px}
.tabp .ptitle{margin-top:6px}
.legend-d{margin:10px 0 0;font-size:12.5px}
.legend-d summary{cursor:pointer;color:var(--ink2);display:inline-block;padding:4px 0}
.legendbox{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:8px;padding:12px 14px;border:1px dashed var(--line2);border-radius:10px;background:var(--wash)}
.legendbox ul{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:6px}
.legendbox li{display:flex;gap:8px;align-items:baseline;color:var(--ink2);font-size:12px}
.legendbox li>span{flex:none}
@media(max-width:900px){.legendbox{grid-template-columns:1fr}}
/* ---- 本层结论区 ---- */
.lhead{padding:14px 18px;margin:4px 0 14px;border-left:3px solid var(--line2)}
.lhead.t-up{border-left-color:var(--up)}.lhead.t-dn{border-left-color:var(--dn)}.lhead.t-warn{border-left-color:var(--warn)}
.lh1{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline;margin-bottom:8px}
.lh1 .big{font-size:18px;font-weight:700}
.lh1 .mean{color:var(--ink2);font-size:13.5px;line-height:1.65}
.lrow{display:grid;grid-template-columns:86px 1fr;gap:10px;padding:7px 0;border-top:1px dashed var(--line);font-size:13px;color:var(--ink2);align-items:baseline}
.lrow>b{font-weight:600;color:var(--muted);font-size:12px}
.lrow a.chip{text-decoration:none;white-space:normal}
@media(max-width:640px){.lrow{grid-template-columns:1fr;gap:4px}}
.anch{position:sticky;top:76px;z-index:14;display:flex;gap:6px;overflow-x:auto;padding:8px 0;margin:-6px 0 10px;background:var(--bg);scrollbar-width:none}
.anch::-webkit-scrollbar{display:none}
@media(max-width:960px){.anch{top:125px}}
.anch a{flex:none;font-size:12px;padding:5px 10px;border-radius:999px;border:1px solid var(--line2);text-decoration:none;color:var(--ink2);min-height:30px;display:inline-flex;align-items:center}
.anch a.on{background:var(--lime);border-color:var(--lime);color:var(--on-lime)}
.grp,h3[id],[id^="grp-"],#scen,#rotm,#l1-faq,#l2-signals,#l2-levels{scroll-margin-top:140px}
.card.flash,.ind.flash{animation:flash 1.2s ease}
@keyframes flash{0%,60%{box-shadow:0 0 0 2px var(--lime)}100%{box-shadow:none}}
details.fold,details.raw{margin:10px 0 14px}
details.fold>summary,details.raw>summary{cursor:pointer;padding:10px 14px;font-size:13px;font-weight:600;color:var(--ink2)}
details.raw>summary{padding:6px 0;font-weight:500;font-size:12px}
details.fold .l1line,details.raw .l1line{margin:0 14px 12px}
.inval{margin:6px 0 4px;font-size:13px;color:var(--ink2)}.inval b{font-family:var(--mono);color:var(--dn)}
.l2nums{padding:10px 14px;margin:0 0 6px}
/* ---- L2 信号 ---- */
.l2sig>summary{display:flex;justify-content:space-between;gap:8px;cursor:pointer;font-size:13px;margin:0 0 8px;list-style:none}
.l2sig>summary::-webkit-details-marker{display:none}
.l2sig>summary span{color:var(--muted);font-family:var(--mono)}
.l2sig .nm a{text-decoration:none;border-bottom:1px dashed var(--line2)}
.l2sig .rd{display:block;font-family:var(--mono);font-size:11.5px;color:var(--ink2);margin-top:1px}
.l2sig .st{font-size:10.5px;padding:1px 6px;border-radius:6px;border:1px dashed var(--line2);color:var(--muted)}
.l2sig .st.on{border-style:solid;color:var(--ink2)}
/* ---- 价格刻度尺 ---- */
.ruler{padding:12px 14px;position:relative}
.mcard{padding:16px 20px;font-size:13.5px;color:var(--ink2);line-height:1.75}.mcard h4{margin:16px 0 8px;font-size:13px;color:var(--ink)}.mcard ul,.mcard ol{padding-left:20px;margin:6px 0}
.anch.static{position:static;flex-wrap:wrap;margin:0 0 6px}
.ruler .rtg{position:absolute;opacity:0;pointer-events:none}
.ruler label.pill{position:absolute;right:14px;top:12px;z-index:2}
.ruler .b,.ruler .r13{display:none}
.ruler .rtg:checked~label .a{display:none}.ruler .rtg:checked~label .b{display:inline}
.ruler .rtg:checked~.r6{display:none}.ruler .rtg:checked~.r13{display:block}
.ruler-svg{display:block;width:100%;max-width:620px;height:auto;min-height:360px;margin:0 auto}
.ruler-svg .rax{stroke:var(--line2);stroke-width:2}
.ruler-svg .rsafe{fill:var(--up);opacity:.14}.ruler-svg .rres{fill:var(--dn);opacity:.12}
.ruler-svg .rbt{font-size:11px;font-family:var(--sans)}.ruler-svg .rbt.up{fill:var(--up)}.ruler-svg .rbt.dn{fill:var(--dn)}
.ruler-svg .rtk{stroke-width:2}.ruler-svg .rtk.up{stroke:var(--up)}.ruler-svg .rtk.dn{stroke:var(--dn)}
.ruler-svg .rlb{font-size:11.5px;fill:var(--ink2);font-family:var(--sans)}
.ruler-svg .rnow{stroke:var(--lime-ink);stroke-width:2.5}
.ruler-svg .rnl{font-size:12.5px;font-weight:700;fill:var(--lime-ink);font-family:var(--mono)}
/* ---- 空状态（G5） ---- */
.es{display:flex;gap:12px;align-items:flex-start;padding:14px 16px;border:1px dashed var(--line2);border-radius:12px;background:var(--wash);color:var(--ink2);font-size:13px}
.es .ic{font-size:18px;line-height:1.2;color:var(--muted);flex:none;width:auto;height:auto}
.es b{color:var(--ink);font-size:13.5px}.es p{margin:3px 0 0}.es p.c{color:var(--muted);font-size:12.5px}
.es-recording{border-color:var(--warn-bd)}.es-retired{border-color:var(--dn-bd)}
.rb{height:6px;border-radius:3px;background:var(--card2);overflow:hidden;margin-top:8px;max-width:320px}
.rb i{display:block;height:100%;background:var(--warn)}
.recbar{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin-top:10px;font-size:12px;color:var(--ink2)}
.recbar .rb{flex:0 0 140px;margin:0}
.ind .rc{align-self:flex-start;font-size:10.5px}
.pendc{border-style:dashed;background:transparent;color:var(--muted);min-height:120px}
.pendc .nm{color:var(--ink2)}
.interp{padding:14px 18px;margin:0 0 6px;border-left:3px solid var(--lime)}
.interp b{font-size:12.5px;color:var(--lime-ink)}.interp p{margin:6px 0 0;color:var(--ink2);line-height:1.75}
.chartcard{padding:14px 18px}
.pgfoot{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;justify-content:space-between;margin-top:22px}
.pgfoot .tnote{margin:0}
.btn.fb{min-height:36px}
/* ---- 今日变化 ---- */
.changes{padding:4px 0}
.changes .cg+.cg{border-top:1px solid var(--line)}
.changes .cgh{font:600 11px/1 var(--mono);letter-spacing:1px;color:var(--muted);padding:12px 16px 2px}
.changes .alerts a{text-decoration:none;border-bottom:1px dashed var(--line2)}
h2 .sp{flex:1}
.chip.frz{font-size:10.5px;color:var(--muted)}
/* ---- 日志列表 ---- */
.mgrp{margin-bottom:10px}
.mgrp>summary{cursor:pointer;padding:12px 16px;font-weight:600;font-size:14px}
.mgrp>summary .sub{font-weight:400;font-size:12px;color:var(--muted);margin-left:8px}
.list li.same>span>a{color:var(--muted);font-weight:500}
.samel{font-style:normal;font-size:11px;color:var(--muted);margin-left:6px}
.list .d small{display:block;font-size:10px;color:var(--muted)}
.chip.hl{box-shadow:0 0 0 1.5px currentColor;font-weight:600}
.list li.rsep{background:var(--warn-bg);font-size:12.5px;color:var(--warn)}
.list li.rsep a{font-weight:500;color:inherit}
@media(max-width:640px){.ticker{display:none}.list li{flex-wrap:wrap}.list .x{margin-left:0}}
/* ---- 术语 / 标签提示（G7） ---- */
.term{text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
[data-tag]{cursor:help}
.uc-pop{position:absolute;z-index:60;max-width:300px;background:var(--toast);border:1px solid var(--line2);border-radius:8px;padding:8px 10px;font-size:12.5px;line-height:1.6;color:var(--ink);box-shadow:0 8px 28px rgba(0,0,0,.3)}
.uc-pop b{display:block;font-size:12px;color:var(--lime-ink);margin-bottom:2px}


/* ---- 弹窗（G1、G2） ---- */
html.ucg-on{overflow:hidden}
.ucg{position:fixed;inset:0;z-index:90;background:var(--scrim);display:flex;align-items:center;justify-content:center;padding:16px}
.ucg-box{position:relative;background:var(--card);border:1px solid var(--line2);border-radius:16px;max-width:560px;width:100%;max-height:85vh;overflow:auto;padding:22px 24px;
box-shadow:0 20px 60px rgba(0,0,0,.45);animation:ucgIn .2s ease}
@keyframes ucgIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.ucg-box{animation:none}}
.ucg-box h2{margin:0 0 10px;font-size:19px}.ucg-box h3{margin:0 0 4px;font-size:15px}
.ucg-box p,.ucg-box li{font-size:13.5px;line-height:1.75;color:var(--ink2)}.ucg-box ul{padding-left:20px;margin:6px 0 10px}
.ucg-box .muted{color:var(--muted);font-size:12.5px}
.ucg-x{position:absolute;right:10px;top:8px;width:40px;height:40px;border:none;background:transparent;color:var(--muted);font-size:24px;cursor:pointer;border-radius:8px}
.ucg-x:hover{color:var(--ink);background:var(--hover)}
.ucg-ft{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}
.ucg-ft .btn{min-height:44px;padding:10px 18px;font-size:13.5px}.ucg-ft small{color:var(--muted);font-size:11.5px}
.ucg-v+.ucg-v{margin-top:14px;padding-top:12px;border-top:1px dashed var(--line2)}
@media (max-width:640px){.ucg{align-items:flex-end;padding:0}.ucg-box{border-radius:16px 16px 0 0;max-height:85vh;padding:20px 18px 24px;max-width:none}}
ul.cl{list-style:none;padding:0;margin:8px 0 0;display:grid;gap:8px}
ul.cl li{display:flex;gap:10px;align-items:baseline}
.cltag{flex:none;font:600 10.5px/1 var(--sans);padding:4px 7px;border-radius:5px;border:1px solid var(--line2)}
.cl-new{color:var(--up);border-color:var(--up-bd)}.cl-improve{color:var(--cool);border-color:var(--cool-bd)}.cl-fix{color:var(--warn);border-color:var(--warn-bd)}.cl-data{color:var(--dn);border-color:var(--dn-bd)}
.clv{padding:16px 20px;margin-bottom:12px}.clh{display:flex;justify-content:space-between;gap:10px;align-items:baseline}.clh b{font-family:var(--mono);font-size:15px}
.clv h3{margin:6px 0 4px}
.navbtn{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;border:none;background:transparent;color:var(--ink2);font:13.5px var(--sans);cursor:pointer;text-align:left;width:100%}
.navbtn:hover{background:var(--hover);color:var(--ink)}
.snav .ver{font-family:var(--mono);font-size:10px;color:var(--muted);margin-left:auto}
.rdot{width:7px;height:7px;border-radius:50%;background:var(--dn);box-shadow:0 0 6px var(--dn);flex:none}
.ntag{font-size:9.5px;font-family:var(--mono);color:var(--muted);border:1px solid var(--line2);border-radius:4px;padding:0 4px;margin-left:auto}
.sfb{margin-left:10px}
.foot .disc{width:100%}
/* ---- 情境格 ---- */
.scen{display:grid;grid-template-columns:150px repeat(4,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:12.5px}
.scen>div{background:var(--card);padding:10px 12px}
.scen .h{font-size:11px;color:var(--muted);font-family:var(--mono)}
.scen .r{color:var(--ink2);font-size:12px}
.scen .c b{display:block;font:600 16px/1.3 var(--mono)}
.scen .c span{font-size:11px;color:var(--muted)}
.scen .c.on{outline:2px solid var(--lime);outline-offset:-2px;background:var(--lime-bg)}
.scen .c.worst:after{content:attr(data-w);display:block;font-size:10.5px;color:var(--warn);margin-top:2px}
@media(max-width:760px){.scen{grid-template-columns:110px repeat(4,minmax(86px,1fr));overflow-x:auto}}
.scen-wrap{overflow-x:auto}

/* ---- 表格 ---- */
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px}
th{font-size:10.5px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);font-weight:600;text-align:right;
padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap;background:var(--wash)}
td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-family:var(--mono);font-variant-numeric:tabular-nums}
th.l,td.l{text-align:left}
td.l{font-family:var(--sans)}
td.wrap{white-space:normal;font-family:var(--sans)}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--hover)}
tr.cur td{background:var(--lime-bg)}
td.rk{color:var(--muted);width:1%;font-size:11.5px}
th.hl{color:var(--lime-ink)} td.hl{color:var(--ink);background:var(--lime-bg)}
.pname{display:flex;align-items:center;gap:9px;font-weight:600}
.pname img{width:18px;height:18px;border-radius:50%;background:var(--card2);flex:none}
.pname a{text-decoration:none}
.pname .deep{font-family:var(--mono);font-size:9px;color:var(--lime-ink);border:1px solid var(--lime-bd);border-radius:3px;padding:0 4px;font-weight:500}
.badge{display:inline-block;font-family:var(--mono);font-size:10px;padding:1px 7px;border-radius:999px;border:1px solid currentColor;margin-left:4px;opacity:.9;font-weight:400}
.b-solana{color:var(--c-solana)}.b-robinhood{color:var(--c-robinhood)}.b-bsc{color:var(--c-bsc)}.b-base{color:var(--c-base)}.b-arc{color:var(--c-arc)}
.b-monad{color:var(--c-monad)}.b-ethereum{color:var(--c-ethereum)}.b-other{color:var(--muted)}
.d.up{color:var(--up)}.d.dn{color:var(--dn)}.d{color:var(--ink2)}
svg.spk{display:block;width:92px;height:26px;margin-left:auto}
.tw.scroll{max-height:720px;overflow:auto}.tw.scroll thead th{position:sticky;top:0;z-index:2;background:var(--thead)}
.tnote{font-size:12px;color:var(--muted);margin:10px 2px 0;line-height:1.7}
.share{display:flex;align-items:center;gap:8px;min-width:120px}
.share .bar{flex:1;height:8px;background:var(--wash);border-radius:4px;overflow:hidden;min-width:70px}
.share .bar i{display:block;height:100%;border-radius:0 4px 4px 0}
.share b{font-weight:500;min-width:44px;text-align:right}
.zbar{display:inline-block;height:8px;border-radius:0 4px 4px 0;vertical-align:middle;margin-right:8px;opacity:.8}

/* ---- 过滤器 ---- */
.fbar{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;padding:12px 14px;margin:0 0 12px}
.fg{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.fg .fl{font-family:var(--mono);font-size:10px;letter-spacing:1.2px;color:var(--muted);text-transform:uppercase;margin-right:2px}
@media(max-width:640px){.pill{min-height:40px;padding:8px 12px}.snav a,.navbtn{min-height:44px}}
.pill{font:500 12px/1 var(--sans);padding:6px 10px;border-radius:7px;border:1px solid var(--line2);color:var(--ink2);background:transparent;cursor:pointer}
.pill:hover{color:var(--ink);border-color:var(--ink2)}
.pill.on{color:var(--on-lime);background:var(--lime);border-color:var(--lime)}
.pill small{font-family:var(--mono);font-size:10px;opacity:.75;margin-left:4px}
.fcount{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--muted)}
.chainbar{display:flex;height:8px;border-radius:5px;overflow:hidden;margin:12px 0 6px;background:var(--card2);gap:2px}
.chainbar i{display:block;height:100%}
.chainleg{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:11.5px;color:var(--ink2)}
.chainleg span{display:inline-flex;align-items:center;gap:6px}.chainleg i{width:8px;height:8px;border-radius:2px}
.chainleg b{font-family:var(--mono);font-weight:500;color:var(--ink)}

/* ---- 静态小图 / 交互图 ---- */
.plot{overflow-x:auto}
.tsvg{display:block;width:100%;min-width:520px;height:auto}
.tsvg .gl{stroke:var(--grid);stroke-width:1}
.tsvg .ax{fill:var(--muted);font-size:10.5px;font-family:var(--mono)}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12px;color:var(--ink2);margin:4px 0 8px}
.legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:10px;height:3px;border-radius:2px}
.legend i.box{width:10px;height:10px;border-radius:2px}
.legend b{font-family:var(--mono);color:var(--ink);font-weight:500}
.uc-chart{position:relative}
.uc-bar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;margin:0 0 8px}
.uc-bar .fg{gap:4px}
.uc-plot{position:relative;width:100%;touch-action:pan-y}
.uc-plot svg{display:block;width:100%;overflow:visible}
.uc-plot .gl{stroke:var(--grid);stroke-width:1}
.uc-plot .ax{fill:var(--muted);font-size:10.5px;font-family:var(--mono)}
.uc-plot .thr{stroke-width:1;stroke-dasharray:4 4;opacity:.85}
.uc-plot .thl{font-size:10px;font-family:var(--sans)}
.uc-plot .zero{stroke:var(--line2);stroke-width:1}
.uc-plot .xh{stroke:var(--ink2);stroke-width:1;opacity:.6}
.uc-tip{position:absolute;pointer-events:none;z-index:5;background:var(--card);border:1px solid var(--line2);border-radius:8px;
padding:8px 10px;font-size:12px;min-width:150px;box-shadow:0 6px 24px rgba(0,0,0,.25);display:none}
.uc-tip .td{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-bottom:4px}
.uc-tip .tr{display:flex;align-items:center;gap:8px;line-height:1.55}
.uc-tip .tr i{width:10px;height:2px;border-radius:1px;flex:none}
.uc-tip .tr b{font-family:var(--mono);font-weight:600;color:var(--ink);margin-left:auto;padding-left:10px}
.uc-tip .tr span{color:var(--ink2)}
.uc-empty{padding:30px 10px;text-align:center;color:var(--muted);font-size:12.5px;border:1px dashed var(--line2);border-radius:10px}
.uc-note{font-size:11.5px;color:var(--muted);margin-top:6px}
.uc-plot .mk{stroke:var(--ink2);stroke-width:1;stroke-dasharray:3 4;opacity:.55}
.uc-plot .mk.live{stroke:var(--lime-ink);stroke-dasharray:none;opacity:.9;stroke-width:1.5}
.uc-plot .mkl{fill:var(--muted);font-size:10px;font-family:var(--sans)}
.uc-plot .shl{fill:var(--muted);font-size:10px;font-family:var(--sans)}
.uc-plot .lastv{font-size:10.5px;font-family:var(--mono);font-weight:600}
.uc-plot .clipm{fill:var(--warn);opacity:.8}
.uc-hint{font-size:11px;color:var(--muted);margin-left:auto}
.legend{margin:8px 0 0}
.legend .lg{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line2);background:transparent;color:var(--ink2);border-radius:999px;padding:3px 9px;font:12px var(--sans);cursor:pointer}
.legend .lg.off{opacity:.45}.legend .lg.off i{background:var(--muted)!important}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.stats>div{background:var(--card);padding:12px 14px}
.stats .k{font-size:11px;color:var(--muted)}.stats .v{font:600 17px/1.3 var(--mono);margin-top:4px}.stats .s{font-size:11px;color:var(--muted)}
@media(max-width:760px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.gauge{position:relative;height:26px;margin:14px 0 4px}
.gauge .trk{position:absolute;left:0;right:0;top:10px;height:6px;border-radius:3px;background:var(--card2)}
.gauge .iqr{position:absolute;top:10px;height:6px;background:var(--cool-bg);border:1px solid var(--cool-bd);border-radius:3px}
.gauge .p90{position:absolute;top:8px;height:10px;border-left:1px solid var(--line2);border-right:1px solid var(--line2)}
.gauge .now{position:absolute;top:2px;width:3px;height:22px;background:var(--ink);border-radius:2px;transform:translateX(-1px)}
.gauge-lbl{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10.5px;color:var(--muted)}

/* ---- 列表 / 日志 ---- */
.list{list-style:none;margin:0;padding:0}
.list li{display:flex;gap:14px;align-items:baseline;padding:11px 16px;border-bottom:1px solid var(--line)}
.list li:last-child{border-bottom:none}
.list .d{font-family:var(--mono);font-size:11.5px;color:var(--muted);flex:none;min-width:92px}
.list a{text-decoration:none;font-weight:600}
.list .s{display:block;font-size:12.5px;color:var(--ink2);margin-top:3px;font-weight:400}
.list .x{margin-left:auto;flex:none}
.empty{padding:18px 20px;color:var(--ink2);font-size:13px;border:1px dashed var(--line2);border-radius:12px}
.pager{display:flex;justify-content:space-between;gap:10px;margin-top:26px;font-size:13px}
.pager a{text-decoration:none;color:var(--ink2)}
.cmt{border-left:3px solid var(--lime);padding:14px 18px;background:var(--lime-bg);border-radius:0 10px 10px 0;margin-top:12px}
.cmt p{margin:0 0 10px}.cmt p:last-child{margin:0}

/* ---- 分析报告 ---- */
.rcard{padding:18px 20px;text-decoration:none;display:flex;flex-direction:column;gap:8px}
a.rcard:hover{border-color:var(--lime-bd);color:inherit}
.rcard .d{font-family:var(--mono);font-size:11px;color:var(--muted)}
.rcard b{font-size:16px;line-height:1.4}
.rcard p{margin:0;font-size:13px;color:var(--ink2)}
.rsum{padding:18px 22px;margin:6px 0 22px}
.rsum h4{margin:0 0 8px;font-size:12px;letter-spacing:1px;color:var(--lime-ink);font-family:var(--mono);text-transform:uppercase}
.rsum ul{margin:8px 0 0;padding-left:20px}.rsum li{margin:4px 0}
.rbody{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:26px 30px;overflow-x:auto}
@media(max-width:640px){.rbody{padding:16px}}

/* ---- 板块轮动 ---- */
.cat{padding:13px 14px;display:flex;flex-direction:column;gap:4px}
.cat .nm{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cat .v{font:600 19px/1.2 var(--mono)}
.cat .s{font-size:11px;color:var(--muted);font-family:var(--mono)}
.cat .t3{font-size:10.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cat.t-up{box-shadow:inset 0 2px 0 var(--up)}.cat.t-dn{box-shadow:inset 0 2px 0 var(--dn)}

/* ---- 文章（手写 md） ---- */
.article{max-width:74ch;font-size:15px;line-height:1.8}
.article p{margin:0 0 14px}
.article blockquote{margin:0 0 14px;padding:8px 18px;border-left:3px solid var(--lime);color:var(--ink2);background:var(--wash);border-radius:0 8px 8px 0}
.article code{background:var(--hover);padding:1px 5px;border-radius:4px;font-family:var(--mono);font-size:.88em}
.article ul{padding-left:22px}.article li{margin:0 0 7px}
.callout{border-left:3px solid var(--lime);background:var(--lime-bg);padding:14px 18px;margin:20px 0;border-radius:0 10px 10px 0}
.callout h4{margin:0 0 6px;font-size:13px;color:var(--lime-ink)}
.callout.blue{border-color:var(--cool);background:var(--cool-bg)}.callout.blue h4{color:var(--cool)}
.callout.red{border-color:var(--dn);background:var(--dn-bg)}.callout.red h4{color:var(--dn)}
.callout.green,.callout.gray{border-color:var(--up);background:var(--up-bg)}.callout.green h4,.callout.gray h4{color:var(--up)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:20px 0}
.kpi{background:var(--card);padding:14px}.kpi .k{font-size:11px;color:var(--muted)}.kpi .v{font:600 22px/1.2 var(--mono)}.kpi .s{font-size:11.5px;color:var(--muted)}

/* ---- 分享长图舞台（屏幕外渲染，html2canvas 截图；长图固定深色） ---- */
.sc{position:fixed;left:-12000px;top:0;width:1080px;padding:54px 56px 40px;background:#05070c;color:#e8ecf3;font-family:var(--sans);
--ink:#e8ecf3;--ink2:#a7afc0;--muted:#6b7488;--up:#00ffcc;--dn:#ff3366;--warn:#ffb020;--cool:#5b8cff;--line:rgba(255,255,255,.06);--line2:rgba(255,255,255,.11);
--up-bg:rgba(0,255,204,.08);--dn-bg:rgba(255,51,102,.09);--warn-bg:rgba(255,176,32,.09);--cool-bg:rgba(91,140,255,.10);--card:#0b0e17;--wash:rgba(255,255,255,.015);
background-image:radial-gradient(700px 400px at 0% 0%,rgba(0,255,204,.10),transparent 70%),radial-gradient(600px 400px at 100% 100%,rgba(163,230,53,.08),transparent 70%)}
.sc-hd{display:flex;align-items:center;gap:16px}
.sc-hd img{width:64px;height:64px;border-radius:50%;box-shadow:0 0 0 3px #a3e635}
.sc-hd b{display:block;font-size:26px}.sc-hd i{display:block;font-style:normal;font-family:var(--mono);font-size:16px;color:#8c94a6;margin-top:2px}
.sc-date{margin-left:auto;font-family:var(--mono);font-size:18px;color:#a7afc0;text-align:right}
.sc-title{font-size:40px;font-weight:700;margin:34px 0 8px;letter-spacing:-.5px}
.sc-sub{font-size:19px;color:#a7afc0;margin-bottom:24px;line-height:1.5}
.sc table{font-size:20px}.sc th{font-size:14px;padding:12px 14px}.sc td{padding:13px 14px}
.sc .sc-box{border:1px solid rgba(255,255,255,.08);border-radius:18px;background:#0b0e17;overflow:hidden;margin-bottom:22px}
.sc .sc-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.sc .sc-kpi{border:1px solid rgba(255,255,255,.08);border-radius:16px;background:#0b0e17;padding:18px}
.sc .sc-kpi .k{font-size:15px;color:#8c94a6}.sc .sc-kpi .v{font:600 30px/1.2 var(--mono);margin-top:8px}.sc .sc-kpi .s{font-size:15px;margin-top:4px}
.sc .sc-al{list-style:none;margin:0;padding:6px 0;font-size:19px}.sc .sc-al li{padding:11px 20px;border-bottom:1px solid rgba(255,255,255,.06)}
.sc .sc-al li:last-child{border:none}
.sc .chip{font-size:17px;padding:6px 14px}
.sc-ft{display:flex;gap:24px;align-items:center;margin-top:26px;padding-top:18px;border-top:1px solid rgba(255,255,255,.08);font-family:var(--mono);font-size:15px;color:#6b7488}
.sc-ft b{color:#a3e635;font-size:18px}
"""

# 不再加载 Google Fonts：国内经常连不上，<head> 里的字体样式表会卡住整页渲染好几秒。全部用系统字体（字体栈在 SITE_CSS 的 --sans / --mono）。
FONTS = ""

# <head> 里最先跑：没存过偏好就用深色（终端风是品牌默认），存过就用存的
HEAD_JS = ("(function(){document.documentElement.classList.add('js');try{var t=localStorage.getItem('uc-theme');if(t==='light'||t==='dark')"
           "document.documentElement.setAttribute('data-theme',t)}catch(e){}})();")

UI_JS = r"""
(function(){
const root=document.documentElement;
function setT(t){root.setAttribute('data-theme',t);try{localStorage.setItem('uc-theme',t)}catch(e){}
 document.querySelectorAll('.thm').forEach(b=>b.setAttribute('aria-pressed',t==='light'?'true':'false'));
 window.dispatchEvent(new Event('uc-theme'))}
document.querySelectorAll('.thm').forEach(b=>b.addEventListener('click',()=>setT(root.getAttribute('data-theme')==='light'?'dark':'light')));
// 预取：鼠标停在站内链接上 65ms，或手指按下，就提前下载那一页
const seen=new Set([location.pathname]);let tm=null;
function pf(a){if(!a||!a.href)return;let u;try{u=new URL(a.href)}catch(e){return}
 if(u.origin!==location.origin||seen.has(u.pathname)||a.target==='_blank'||/\.(png|jpe?g|svg|json)$/.test(u.pathname))return;
 seen.add(u.pathname);const l=document.createElement('link');l.rel='prefetch';l.href=u.pathname;document.head.appendChild(l)}
document.addEventListener('mouseover',e=>{const a=e.target.closest&&e.target.closest('a[href]');if(!a)return;clearTimeout(tm);tm=setTimeout(()=>pf(a),65)},{passive:true});
document.addEventListener('mouseout',()=>clearTimeout(tm),{passive:true});
document.addEventListener('touchstart',e=>{const a=e.target.closest&&e.target.closest('a[href]');if(a)pf(a)},{passive:true});
// 语言切换时带上当前的 #筛选状态
document.querySelectorAll('.lang a').forEach(a=>a.addEventListener('click',()=>{if(location.hash)a.href=a.getAttribute('href')+location.hash}));
})();

if(innerWidth<641)document.querySelectorAll('details.segd').forEach(d=>d.removeAttribute('open'));
// ---- 宏观页四层 Tab（M1）：#layer-N 锚点直达；切换用 replaceState 不跳动；左右方向键；从详情页回来恢复原 Tab 原位置
(function(){
 const bar=document.querySelector('[data-tabs]');if(!bar)return;
 const tabs=[...bar.querySelectorAll('[role=tab]')];const KEY='uc-macro-pos';
 function panelOf(el){return el&&el.closest?el.closest('.tabp'):null}
 function act(n,focus){tabs.forEach(t=>{const on=t.dataset.tab==String(n);t.classList.toggle('on',on);t.setAttribute('aria-selected',on?'true':'false');t.tabIndex=on?0:-1;
   const p=document.getElementById(t.getAttribute('aria-controls'));if(p)p.classList.toggle('on',on)});if(focus){const t=tabs.find(t=>t.dataset.tab==String(n));t&&t.focus()}
  if(window.ucBootCharts)setTimeout(()=>window.ucBootCharts(document.getElementById('layer-'+n)),30)}
 function cur(){const t=tabs.find(t=>t.classList.contains('on'));return t?t.dataset.tab:'1'}
 function go(hash,scroll){if(!hash)return false;const id=hash.slice(1);const el=document.getElementById(id);if(!el)return false;
  let n=null;const m=/^layer-(\d)$/.exec(id);if(m)n=m[1];else{const p=panelOf(el);if(p)n=p.id.split('-')[1]}
  if(!n)return false;act(n);if(scroll){if(m){const tw=document.querySelector('.tabwrap');window.scrollTo({top:Math.max(0,tw.getBoundingClientRect().top+scrollY-8)})}else setTimeout(()=>{el.scrollIntoView({block:'start'});flash(el)},40)}return true}
 function flash(el){if(!el)return;el.classList.remove('flash');void el.offsetWidth;el.classList.add('flash')}
 tabs.forEach((t,k)=>{t.addEventListener('click',e=>{e.preventDefault();act(t.dataset.tab);history.replaceState(null,'','#layer-'+t.dataset.tab)});
  t.addEventListener('keydown',e=>{if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft')return;e.preventDefault();const j=(k+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
   act(tabs[j].dataset.tab,true);history.replaceState(null,'','#layer-'+tabs[j].dataset.tab)})});
 // 页面里指向其他 Tab 的链接（综合研判的层徽章、依据小芯片、#l2-levels 等）
 document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[href^="#"]');if(!a)return;const h=a.getAttribute('href');
  if(go(h,true)){e.preventDefault();history.replaceState(null,'',h)}});
 document.querySelectorAll('.segs a[data-tab],a.lb[data-tab]').forEach(a=>a.addEventListener('click',e=>{if(location.pathname===new URL(a.href).pathname){e.preventDefault();act(a.dataset.tab);
  history.replaceState(null,'','#layer-'+a.dataset.tab);const tw=document.querySelector('.tabwrap');window.scrollTo({top:Math.max(0,tw.getBoundingClientRect().top+scrollY-8),behavior:'smooth'})}}));
 window.addEventListener('hashchange',()=>go(location.hash,true));
 // 恢复位置：浏览器后退，或从本站指标详情页点面包屑回来
 let st=null;try{st=JSON.parse(sessionStorage.getItem(KEY)||'null')}catch(e){}
 const nav=(performance.getEntriesByType&&performance.getEntriesByType('navigation')[0]||{}).type;
 const fromDetail=/\/macro\/[a-z0-9_]+\/?$/.test(document.referrer.replace(/^https?:\/\/[^/]+/,'').replace(/^\/en/,''));
 if(!go(location.hash,false))act(st&&(nav==='back_forward'||fromDetail)?st.tab:'1');
 else if(location.hash&&!/^#layer-\d$/.test(location.hash))go(location.hash,true);
 if(st&&(nav==='back_forward'||fromDetail)&&st.tab===cur()&&st.y)setTimeout(()=>window.scrollTo(0,st.y),60);
 let tm=null;const save=()=>{try{sessionStorage.setItem(KEY,JSON.stringify({tab:cur(),y:Math.round(scrollY)}))}catch(e){}};
 window.addEventListener('scroll',()=>{clearTimeout(tm);tm=setTimeout(save,150)},{passive:true});window.addEventListener('pagehide',save);
 // 依据小芯片：跳到对应卡片并高亮 1 秒
 document.querySelectorAll('[data-hl]').forEach(a=>a.addEventListener('click',()=>setTimeout(()=>flash(document.getElementById(a.dataset.hl)),300)));
 // L1 二级锚点：滚动时当前分组高亮
 const an=[...document.querySelectorAll('.anch a')];if(an.length&&'IntersectionObserver' in window){const io=new IntersectionObserver(es=>{es.forEach(en=>{if(en.isIntersecting){
   an.forEach(a=>a.classList.toggle('on',a.dataset.anchor===en.target.id))}})},{rootMargin:'-150px 0px -65% 0px'});
  an.forEach(a=>{const t=document.getElementById(a.dataset.anchor);if(t)io.observe(t)})}
})();

// ---- 欢迎弹窗 / 版本更新弹窗（G1、G2）：本地存储记住看过哪一版；存储不可用就一律不弹
(function(){
 const meta=document.getElementById('ucg-meta');if(!meta)return;let M;try{M=JSON.parse(meta.textContent)}catch(e){return}
 const CUR=M.cur;let st=null;try{st=window.localStorage;st.getItem('_t')}catch(e){st=null}
 const get=k=>{try{return st?st.getItem(k):null}catch(e){return null}},set=(k,v)=>{try{st&&st.setItem(k,v)}catch(e){}};
 if(/\/changelog\/?$/.test(location.pathname))set('uo_log_seen',CUR);
 function dot(){const show=!!st&&!!get('uo_welcome_seen')&&get('uo_log_seen')!==CUR;document.querySelectorAll('.rdot').forEach(d=>d.hidden=!show)}
 dot();
 let open=null,back=null;
 function close(){if(!open)return;const o=open;open=null;o.remove();document.documentElement.classList.remove('ucg-on');if(o._done)o._done();if(back&&back.focus)back.focus();dot()}
 function show(id,done,filter){if(open)return;const tpl=document.getElementById(id);if(!tpl)return;back=document.activeElement;
  const wrap=document.createElement('div');wrap.className='ucg';wrap.setAttribute('role','dialog');wrap.setAttribute('aria-modal','true');wrap.setAttribute('aria-labelledby','ucg-t');
  const box=document.createElement('div');box.className='ucg-box';box.appendChild(tpl.content.cloneNode(true));
  if(filter){box.querySelectorAll('.ucg-v').forEach(v=>{if(!filter(v.dataset.v))v.remove()});const h=box.querySelector('.ucg-v h3');if(h)h.id='ucg-t'}
  const x=document.createElement('button');x.type='button';x.className='ucg-x';x.setAttribute('aria-label',document.documentElement.lang.startsWith('zh')?'关闭':'Close');x.textContent='×';box.prepend(x);
  wrap.appendChild(box);document.body.appendChild(wrap);document.documentElement.classList.add('ucg-on');open=wrap;wrap._done=done;
  wrap.addEventListener('click',e=>{if(e.target===wrap)close()});box.querySelectorAll('.ucg-ok,.ucg-x').forEach(b=>b.addEventListener('click',close));
  wrap.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();return}
   if(e.key==='Tab'){const f=[...box.querySelectorAll('a[href],button')];if(!f.length)return;const a=f[0],z=f[f.length-1];
    if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus()}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus()}}});
  setTimeout(()=>{const b=box.querySelector('.ucg-ok')||x;b.focus()},30)}
 document.querySelectorAll('[data-guide]').forEach(b=>b.addEventListener('click',()=>{const n=document.getElementById('navtg');if(n)n.checked=false;
  show('ucg-welcome',()=>{set('uo_welcome_seen','1');if(!get('uo_last_seen_version'))set('uo_last_seen_version',CUR)})}));
 window.ucGuide=()=>show('ucg-welcome');
 const supp=/[?&](noguide=1|sharepreview)/.test(location.search)||window.self!==window.top||navigator.webdriver||
  /bot|crawl|spider|slurp|bingpreview|headless|lighthouse|facebookexternalhit|twitterbot|telegrambot|whatsapp/i.test(navigator.userAgent);
 if(!st||supp)return;
 function auto(){if(document.querySelector('.sc'))return;
  const welcomed=get('uo_welcome_seen'),last=get('uo_last_seen_version');
  if(!welcomed){show('ucg-welcome',()=>{set('uo_welcome_seen','1');set('uo_last_seen_version',CUR);set('uo_log_seen',CUR)});return}
  if(last!==CUR){const unseen=M.vers.filter(v=>v.n&&(!last||v.v>last)).map(v=>v.v).slice(0,3);
   if(unseen.length)show('ucg-update',()=>set('uo_last_seen_version',CUR),v=>unseen.includes(v));else set('uo_last_seen_version',CUR)}}
 if(document.readyState==='complete')setTimeout(auto,400);else window.addEventListener('load',()=>setTimeout(auto,400));
})();
// ---- 反馈 / 纠错（G10）：一键在 X 上 @ 站长，带上当前页面标题和链接
document.querySelectorAll('[data-feedback]').forEach(a=>{const zh=document.documentElement.lang.startsWith('zh');
 a.href='https://x.com/intent/post?text='+encodeURIComponent((zh?'@Uncle_Onchain 反馈：':'@Uncle_Onchain Feedback: ')+document.title.split(' · ')[0]+' ')+'&url='+encodeURIComponent(location.href.split('#')[0]);
 a.target='_blank';a.rel='noopener'});
// ---- 术语与标签解释（G7）：术语第一次出现加虚下划线；悬停（桌面）/ 点按（手机）显示一句话
(function(){
 const g=document.getElementById('uc-gloss');if(!g)return;let G;try{G=JSON.parse(g.textContent)}catch(e){return}
 const pop=document.createElement('div');pop.className='uc-pop';pop.hidden=true;pop.setAttribute('role','tooltip');document.body.appendChild(pop);
 function place(el,title,def){pop.innerHTML='';const b=document.createElement('b');b.textContent=title;const p=document.createElement('div');p.textContent=def;pop.append(b,p);pop.hidden=false;
  const r=el.getBoundingClientRect();const w=Math.min(300,innerWidth-16);pop.style.maxWidth=w+'px';let x=r.left+scrollX;if(x+w>scrollX+innerWidth-8)x=scrollX+innerWidth-8-w;
  pop.style.left=Math.max(scrollX+8,x)+'px';pop.style.top=(r.bottom+scrollY+6)+'px'}
 const hide=()=>{pop.hidden=true};
 const words=[];(G.terms||[]).forEach(t=>t.w.forEach(w=>words.push({w:w,d:t.d,k:t.w[0]})));words.sort((a,b)=>b.w.length-a.w.length);
 const root=document.querySelector('.mi');
 if(root&&words.length){const used=new Set();const skip='A,BUTTON,SCRIPT,STYLE,CODE,H1,TEXTAREA,INPUT,SUMMARY,TEMPLATE,SVG,TEXT,LABEL,NAV';
  const esc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');const re=new RegExp('('+words.map(x=>esc(x.w)).join('|')+')');
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{let p=n.parentElement;while(p&&p!==root){if(skip.includes(p.tagName)||p.classList.contains('term')||p.classList.contains('uc-chart')||p.classList.contains('chip')||p.classList.contains('grade'))return NodeFilter.FILTER_REJECT;p=p.parentElement}return re.test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_SKIP}});
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  nodes.forEach(n=>{if(used.size>=words.length)return;const m=n.nodeValue.match(re);if(!m)return;const hit=words.find(x=>x.w===m[1]);if(!hit||used.has(hit.k))return;used.add(hit.k);
   const i=m.index,a=n.splitText(i);a.splitText(m[1].length);const sp=document.createElement('span');sp.className='term';sp.tabIndex=0;sp.dataset.def=hit.d;sp.dataset.t=m[1];
   a.parentNode.replaceChild(sp,a);sp.textContent=m[1]})}
 const tip=e=>{const t=e.target.closest&&e.target.closest('.term,[data-tag]');if(!t)return null;if(t.classList.contains('term'))return [t,t.dataset.t,t.dataset.def];
  const d=(G.tags||{})[t.dataset.tag];return d?[t,t.textContent,d]:null};
 document.addEventListener('mouseover',e=>{const x=tip(e);if(x)place(...x)},{passive:true});
 document.addEventListener('mouseout',e=>{if(tip(e))hide()},{passive:true});
 document.addEventListener('focusin',e=>{const x=tip(e);if(x)place(...x)});document.addEventListener('focusout',hide);
 document.addEventListener('click',e=>{const x=tip(e);if(x){if(x[0].closest('a'))e.preventDefault();place(...x)}else hide()});
})();
"""

CHART_JS = r"""
(function(){
const LANG=document.documentElement.lang.startsWith('zh')?'zh':'en';
const ZH=LANG==='zh';
function nfmt(v,dp){return v.toLocaleString('en-US',{minimumFractionDigits:dp,maximumFractionDigits:dp})}
const M=s=>String(s).replace(/^-/,'−');
function usd(v){const a=Math.abs(v),s=v<0?'−':'';return a>=1e12?s+'$'+(a/1e12).toFixed(2)+'T':a>=1e9?s+'$'+(a/1e9).toFixed(2)+'B':a>=1e6?s+'$'+(a/1e6).toFixed(2)+'M':a>=1e3?s+'$'+(a/1e3).toFixed(1)+'K':s+'$'+Math.round(a)}
const sg=v=>v>0?'+':'';
const F={usd:usd,usds:v=>sg(v)+usd(v),pct:v=>M(v.toFixed(2))+'%',pct1:v=>M(v.toFixed(1))+'%',pcts:v=>sg(v)+M(v.toFixed(2))+'%',
 pp:v=>sg(v)+M(v.toFixed(2))+'pp',x:v=>M(v.toFixed(2)),xs:v=>sg(v)+M(v.toFixed(2)),x3:v=>M(v.toFixed(3)),int:v=>M(Math.round(v)+''),idx:v=>M(nfmt(v,2)),
 btc:v=>M(nfmt(Math.round(v),0))+' BTC',btcs:v=>sg(v)+M(nfmt(Math.round(v),0))+' BTC',price:v=>'$'+nfmt(Math.round(v),0)};
function axfmt(f,v){if(f==='usd'||f==='usds'||f==='price'){return usd(v)}
 if(f==='btc'||f==='btcs'){const a=Math.abs(v);return M(a>=1e6?(v/1e6).toFixed(2)+'M':a>=1e3?(v/1e3).toFixed(0)+'K':Math.round(v)+'')}
 if(f.startsWith('pct')||f==='pp')return M(Math.abs(v)<10?v.toFixed(1):v.toFixed(0))+(f==='pp'?'':'%');
 return M(Math.abs(v)>=1000?nfmt(v,0):(Math.abs(v)<10?v.toFixed(2):v.toFixed(1)))}
function nice(lo,hi,n){const span=hi-lo||Math.abs(hi)||1,step0=span/n,mag=Math.pow(10,Math.floor(Math.log10(step0))),r=step0/mag;
 const step=(r<1.5?1:r<3?2:r<7?5:10)*mag;const a=Math.floor(lo/step)*step,out=[];for(let v=a;v<=hi+step*.5;v+=step)if(v>=lo-step*.01)out.push(+v.toPrecision(12));return out}
const T0=d=>Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10));
const D0=t=>new Date(t).toISOString().slice(0,10);
const RANGES={'1M':31,'3M':92,'6M':183,'1Y':366,'3Y':1096,'5Y':1827,'ALL':0,'CYC':-1};
const RL={zh:{'1M':'1 月','3M':'3 月','6M':'6 月','1Y':'1 年','3Y':'3 年','5Y':'5 年','ALL':'全部','CYC':'本轮'},en:{'1M':'1M','3M':'3M','6M':'6M','1Y':'1Y','3Y':'3Y','5Y':'5Y','ALL':'All','CYC':'This cycle'}};
const groups={},cache={};
// 数据：旧格式 {d,s}；新格式（附录 C）{start|dates, values, level, extra}，可以是「归档 + 本月」两份拼起来
function norm(j){if(j.d)return j;let d=j.dates;const n=(j.values||[]).length||Object.values(j.extra||{}).reduce((a,x)=>Math.max(a,x.length),0);
 if(!d){d=[];if(j.start){let t=T0(j.start);for(let i=0;i<n;i++){d.push(D0(t));t+=864e5}}}
 const s={};if(j.values)s.v=j.values;if(j.level&&j.level.values)s.level=j.level.values;for(const k in (j.extra||{}))s[k]=j.extra[k];return {d:d,s:s,meta:j}}
function merge(parts){const out={d:[],s:{},meta:Object.assign({},...parts.map(p=>p.meta||{}))};
 parts.forEach(p=>{const n=p.d.length,base=out.d.length;out.d.push(...p.d);const ks=new Set([...Object.keys(out.s),...Object.keys(p.s)]);
  ks.forEach(k=>{if(!out.s[k])out.s[k]=new Array(base).fill(null);const a=p.s[k]||new Array(n).fill(null);out.s[k].push(...a)})});return out}
function get(u){if(!cache[u])cache[u]=fetch(u).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}).catch(e=>{delete cache[u];throw e});return cache[u]}
function load(src){const us=Array.isArray(src)?src:[src];return Promise.all(us.map(u=>get(u).then(norm).catch(e=>{if(us.length>1&&u!==us[0])return {d:[],s:{}};throw e}))).then(merge)}
function mk(tag,attrs){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const k in attrs)e.setAttribute(k,attrs[k]);return e}
function q(sorted,p){if(!sorted.length)return null;const k=(sorted.length-1)*p,lo=Math.floor(k),hi=Math.ceil(k);return sorted[lo]+(sorted[hi]-sorted[lo])*(k-lo)}
const TONE={up:'up',dn:'dn',warn:'warn',neutral:'ink2',cool:'ink2'};

function Chart(el,cfg){if(!cfg.v2&&cfg.last===undefined)cfg.last=false;this.el=el;this.cfg=cfg;this.range=cfg.range||'ALL';this.mode=cfg.mode||'abs';this.off={};
 (cfg.series||[]).forEach(s=>{if(s.hidden)this.off[s.k]=1});this.init()}
Chart.prototype.init=function(){
 const c=this.cfg,el=this.el,self=this;el.classList.add('uc-chart');el.innerHTML='';
 const bar=document.createElement('div');bar.className='uc-bar';this.bar=bar;
 if(c.stack){const g=document.createElement('div');g.className='fg';
  [['abs',ZH?'金额':'Amount'],['pct',ZH?'份额 %':'Share %']].forEach(([m,l])=>{const b=document.createElement('button');
   b.className='pill';b.textContent=l;b.dataset.m=m;b.onclick=()=>{self.mode=m;self.draw()};g.appendChild(b)});bar.appendChild(g)}
 el.appendChild(bar);
 this.plot=document.createElement('div');this.plot.className='uc-plot';this.plot.style.minHeight=this.H()+'px';el.appendChild(this.plot);
 this.tip=document.createElement('div');this.tip.className='uc-tip';this.plot.appendChild(this.tip);
 this.leg=document.createElement('div');this.leg.className='legend';if(c.v2)el.appendChild(this.leg);else bar.appendChild(this.leg);
 if(c.note){const n=document.createElement('div');n.className='uc-note';n.textContent=c.note;el.appendChild(n)}
 if(c.group){(groups[c.group]=groups[c.group]||[]).push(this)}
 this.fetch();
 let t;new ResizeObserver(()=>{clearTimeout(t);t=setTimeout(()=>self.data&&self.draw(),80)}).observe(this.plot);
 window.addEventListener('uc-theme',()=>self.data&&self.draw());
};
Chart.prototype.H=function(){const w=this.plot?this.plot.clientWidth:this.el.clientWidth;return this.cfg.h||((w||800)<560?240:320)};
Chart.prototype.msg=function(text,retry){this.plot.querySelectorAll('svg,.uc-empty').forEach(x=>x.remove());const d=document.createElement('div');
 d.className='uc-empty';d.style.minHeight=this.H()+'px';d.textContent=text;if(retry){d.style.cursor='pointer';d.onclick=()=>this.fetch()}this.plot.insertBefore(d,this.tip)};
Chart.prototype.fetch=function(){const self=this,c=this.cfg;this.msg(ZH?'加载中…':'Loading…');
 const jobs=[load(c.src)];if(c.btc)jobs.push(load(c.btc).catch(()=>null));
 Promise.all(jobs).then(([j,b])=>{self.data=j;self.btc=b;self.buttons();self.draw()}).catch(()=>self.msg(ZH?'数据加载失败 · 点此重试':'Failed to load data · tap to retry',true))};
Chart.prototype.buttons=function(){const c=this.cfg,self=this,j=this.data;if(!c.ranges||!c.ranges.length||!j.d.length)return;
 const span=(T0(j.d[j.d.length-1])-T0(j.d[0]))/864e5;const g=document.createElement('div');g.className='fg';
 c.ranges.filter(r=>!c.v2||r==='ALL'||(r==='CYC'?!!c.cyc:span>RANGES[r]*1.02)).forEach(r=>{const b=document.createElement('button');b.className='pill';b.textContent=RL[LANG][r]||r;b.dataset.r=r;
  b.onclick=()=>{(c.group?groups[c.group]:[self]).forEach(x=>{if(x.data&&(r==='ALL'||x.bar.querySelector('[data-r="'+r+'"]'))){x.range=r;x.draw()}})};g.appendChild(b)});
 if(!g.querySelector('[data-r="'+this.range+'"]'))this.range='ALL';
 this.bar.insertBefore(g,this.bar.firstChild);
 if(c.hint){const h=document.createElement('span');h.className='uc-hint';h.textContent=c.hint;this.bar.appendChild(h)}};
Chart.prototype.draw=function(){
 const c=this.cfg,j=this.data,self=this;
 this.plot.querySelectorAll('.uc-empty').forEach(x=>x.remove());
 this.bar.querySelectorAll('.pill[data-r]').forEach(b=>b.classList.toggle('on',b.dataset.r===this.range));
 this.bar.querySelectorAll('.pill[data-m]').forEach(b=>b.classList.toggle('on',b.dataset.m===this.mode));
 const D=j.d,N=D.length;if(!N){this.msg(ZH?'暂无数据':'No data');return}
 const last=T0(D[N-1]);let lo0=0;
 if(this.range==='CYC'&&c.cyc)lo0=T0(c.cyc);else if(RANGES[this.range]>0)lo0=last-RANGES[this.range]*864e5;
 if(c.from&&T0(c.from)>lo0)lo0=T0(c.from);
 let i0=0;while(i0<N-1&&T0(D[i0])<lo0)i0++;
 const idx=[];for(let i=i0;i<N;i++)idx.push(i);
 const ser=(c.series||[]).filter(s=>j.s[s.k]);const vis=ser.filter(s=>!self.off[s.k]);
 const pct=c.stack&&this.mode==='pct';
 let stk=null,tot=null;
 if(c.stack){tot=idx.map(i=>vis.reduce((a,s)=>a+(j.s[s.k][i]||0),0));stk=[];let base=idx.map(()=>0);
  vis.forEach(s=>{const top=idx.map((i,n)=>{const v=j.s[s.k][i]||0;return base[n]+(pct?(tot[n]?v/tot[n]*100:0):v)});stk.push({lo:base,hi:top});base=top})}
 let lo=Infinity,hi=-Infinity;const all=[];
 if(c.stack){(stk.length?stk[stk.length-1].hi:[]).forEach(v=>{hi=Math.max(hi,v)});lo=0;if(pct)hi=100}
 else{const cf=c.clipFrom?T0(c.clipFrom):null;vis.forEach(s=>idx.forEach(i=>{const v=j.s[s.k][i];if(v!=null&&isFinite(v)&&(!c.log||v>0)){all.push(v)}}));
  if(c.clip&&cf){const inw=[];vis.forEach(s=>idx.forEach(i=>{const v=j.s[s.k][i];if(T0(D[i])>=cf&&v!=null&&isFinite(v))inw.push(v)}));
   if(inw.length>200){inw.sort((a,b)=>a-b);c._lo=q(inw,.005);c._hi=q(inw,.995)}else{c._lo=c._hi=null}}}
 if(!c.stack&&all.length){all.sort((a,b)=>a-b);if(c.clip&&c._lo!=null&&c.clipFrom){lo=c._lo;hi=c._hi;const a0=j.s[vis[0].k];for(let k=idx.length-1;k>=0;k--){const v=a0[idx[k]];if(v!=null){lo=Math.min(lo,v);hi=Math.max(hi,v);break}}}
  else if(c.clip&&all.length>200){lo=q(all,.005);hi=q(all,.995)}else{lo=all[0];hi=all[all.length-1]}}
 if(!isFinite(lo)||!isFinite(hi)){this.plot.querySelectorAll('svg').forEach(x=>x.remove());return}
 const clipped=c.clip&&!c.stack&&all.length&&(all[0]<lo||all[all.length-1]>hi);
 (c.lines||[]).forEach(l=>{if(l.v>=lo-(hi-lo)*.25&&l.v<=hi+(hi-lo)*.25){lo=Math.min(lo,l.v);hi=Math.max(hi,l.v)}});
 if(c.band&&c.bandOn!==false){lo=Math.min(lo,c.band.p10);hi=Math.max(hi,c.band.p90)}
 if(c.zero&&!c.log){lo=Math.min(lo,0);hi=Math.max(hi,0)}
 const W=Math.max(300,this.plot.clientWidth),H=this.H(),L=W<560?44:58,R=(c.lines&&c.lines.length)?(W<560?8:96):(c.last!==false?(W<560?8:70):12),TP=12,B=26;
 this.plot.style.minHeight=H+'px';
 const pw=W-L-R,ph=H-TP-B;
 let yt,Y,ylo,yhi;
 if(c.log){const a=Math.log10(lo),b=Math.log10(hi);const pad=(b-a)*.05||.1;const A=a-pad,Bv=b+pad;ylo=Math.pow(10,A);yhi=Math.pow(10,Bv);
  Y=v=>TP+ph*(1-(Math.log10(v)-A)/(Bv-A));yt=[];for(let e=Math.floor(A);e<=Math.ceil(Bv);e++)[1,2,5].forEach(m=>{const v=m*Math.pow(10,e);if(Math.log10(v)>=A&&Math.log10(v)<=Bv)yt.push(v)});
  if(yt.length>7)yt=yt.filter((v,k)=>String(v).startsWith('1'))}
 else{const pad=(hi-lo)*.06||Math.abs(hi)*.1||1;let a=lo-(c.stack||c.zero&&lo>=0?0:pad),b=hi+pad;if(pct){a=0;b=100}
  yt=nice(a,b,W<560?4:5);a=Math.min(a,yt[0]);b=Math.max(b,yt[yt.length-1]);ylo=a;yhi=b;Y=v=>TP+ph*(1-(v-a)/(b-a))}
 const YC=v=>Math.max(TP,Math.min(TP+ph,Y(v)));
 const t0=T0(D[idx[0]]),t1=T0(D[idx[idx.length-1]])||t0+1,X=t=>L+pw*((t-t0)/((t1-t0)||1));
 const svg=mk('svg',{viewBox:`0 0 ${W} ${H}`,height:H,role:'img','aria-label':c.title||''});
 // 区间背景带（颜色只按 bias）
 if(c.zone&&!c.stack&&!c.log){let prev=-Infinity;c.zone.forEach(z=>{const ub=z.ub==null?Infinity:z.ub,a=Math.max(prev,ylo),b=Math.min(ub,yhi);
  if(b>a&&TONE[z.t]&&z.t!=='neutral')svg.appendChild(mk('rect',{x:L,width:pw,y:Y(b),height:Math.max(0,Y(a)-Y(b)),style:`fill:var(--${TONE[z.t]});opacity:.06`}));prev=ub})}
 // 统计窗口外 / 历史回放区：浅灰底色
 (c.shade||[]).forEach(sh=>{const a=Math.max(t0,sh.from?T0(sh.from):t0),b=Math.min(t1,sh.to?T0(sh.to):t1);if(b<=a)return;
  svg.appendChild(mk('rect',{x:X(a),y:TP,width:X(b)-X(a),height:ph,style:'fill:var(--ink2);opacity:.07'}));
  if(sh.label&&X(b)-X(a)>90){const tx=mk('text',{x:X(a)+6,y:TP+12,class:'shl'});tx.textContent=sh.label;svg.appendChild(tx)}});
 // 状态背景色
 if(c.states&&c.stk&&j.s[c.stk]){const a=j.s[c.stk];let s0=0;
  for(let n=1;n<=idx.length;n++){if(n===idx.length||a[idx[n]]!==a[idx[s0]]){const st=c.states[a[idx[s0]]];
   if(st){const xa=X(T0(D[idx[s0]])),xb=n<idx.length?X(T0(D[idx[n]])):L+pw;svg.appendChild(mk('rect',{x:xa,y:TP,width:Math.max(0,xb-xa),height:ph,style:`fill:var(--${st.c});opacity:.14`}))}s0=n}}}
 yt.forEach(v=>{svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(v),y2:Y(v),class:'gl'}));
  const tx=mk('text',{x:L-8,y:Y(v)+3.5,'text-anchor':'end',class:'ax'});tx.textContent=pct?v+'%':axfmt(c.fmt,v);svg.appendChild(tx)});
 // x 轴：3 年以上只标年；1~3 年标年-月；1 年以内标月-日
 const spanD=(t1-t0)/864e5,xt=[];
 {const d0=new Date(t0);let y=d0.getUTCFullYear(),m=d0.getUTCMonth();
  const stepM=spanD>1096?(spanD>3000?24:12):spanD>366?(spanD>700?6:3):spanD>120?1:0;
  if(stepM){m=Math.ceil(m/stepM)*stepM;while(true){const t=Date.UTC(y+Math.floor(m/12),m%12,1);if(t>t1)break;if(t>=t0)xt.push(t);m+=stepM}}
  else{for(let t=t0;t<=t1;t+=864e5*Math.max(1,Math.round(spanD/6)))xt.push(t)}}
 let lastX=-99;xt.forEach(t=>{const x=X(t);if(x-lastX<54)return;lastX=x;const d=new Date(t);
  const tx=mk('text',{x:x,y:TP+ph+18,'text-anchor':'middle',class:'ax'});
  tx.textContent=spanD>1096?d.getUTCFullYear()+'':spanD>366?d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0'):(d.getUTCMonth()+1)+'-'+String(d.getUTCDate()).padStart(2,'0');svg.appendChild(tx)});
 if(c.band&&!c.stack){const bd=c.band;
  svg.appendChild(mk('rect',{x:L,width:pw,y:YC(bd.p90),height:Math.max(0,YC(bd.p10)-YC(bd.p90)),style:'fill:var(--cool);opacity:.07'}));
  svg.appendChild(mk('rect',{x:L,width:pw,y:YC(bd.p75),height:Math.max(0,YC(bd.p25)-YC(bd.p75)),style:'fill:var(--cool);opacity:.10'}));
  svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:YC(bd.p50),y2:YC(bd.p50),style:'stroke:var(--cool);opacity:.5','stroke-dasharray':'2 3'}))}
 if(c.zero&&!c.log&&ylo<0&&yhi>0)svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(0),y2:Y(0),class:'zero'}));
 (c.lines||[]).forEach(l=>{const y=Y(l.v);if(y<TP-1||y>TP+ph+1)return;
  svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:y,y2:y,class:'thr',style:`stroke:var(--${TONE[l.tone]||'ink2'})`}));
  if(R>40){const tx=mk('text',{x:L+pw+6,y:y+3.5,class:'thl',style:`fill:var(--${TONE[l.tone]||'ink2'})`});tx.textContent=l.label;svg.appendChild(tx)}});
 // 竖线标记：减半、实时记录起点等
 (c.markers||[]).forEach(mm=>{const t=T0(mm.date);if(t<t0||t>t1)return;const x=X(t);
  svg.appendChild(mk('line',{x1:x,x2:x,y1:TP,y2:TP+ph,class:mm.type==='live'?'mk live':'mk'}));
  const tx=mk('text',{x:x+4,y:TP+ph-6,class:'mkl'});tx.textContent=mm.label||'';svg.appendChild(tx)});
 const col=s=>`var(--${s.c||'s1'})`;
 // 折线：点数远多于像素时按像素列取最小 / 最大值，形状不变
 function path(arr,clip){let p='',pen=false,n=0;const step=idx.length>pw*2?Math.ceil(idx.length/(pw*2)):1;
  for(let a=0;a<idx.length;a+=step){let bmin=null,bmax=null,imin=0,imax=0;for(let b=a;b<Math.min(idx.length,a+step);b++){const v=arr[idx[b]];
    if(v==null||!isFinite(v)||(c.log&&v<=0))continue;if(bmin==null||v<bmin){bmin=v;imin=b}if(bmax==null||v>bmax){bmax=v;imax=b}}
   if(bmin==null){if(c.gaps)pen=false;continue}
   const pts=imin<=imax?[[imin,bmin],[imax,bmax]]:[[imax,bmax],[imin,bmin]];
   pts.forEach(([b,v])=>{const yy=clip?YC(v):Y(v);p+=(pen?'L':'M')+X(T0(D[idx[b]])).toFixed(1)+','+yy.toFixed(1);pen=true;n++})}
  return p}
 if(c.stack){stk.forEach((st,k)=>{const s=vis[k];let p='';idx.forEach((i,n)=>{p+=(n?'L':'M')+X(T0(D[i])).toFixed(1)+','+Y(st.hi[n]).toFixed(1)});
   for(let n=idx.length-1;n>=0;n--)p+='L'+X(T0(D[idx[n]])).toFixed(1)+','+Y(st.lo[n]).toFixed(1);
   svg.appendChild(mk('path',{d:p+'Z',style:`fill:${col(s)};stroke:var(--card);stroke-width:${idx.length>200?0.5:1}`}))})}
 else vis.forEach(s=>{const arr=j.s[s.k];const p=path(arr,clipped);if(!p)return;
   if(s.area&&!c.log){const base=Y(Math.max(Math.min(0,yhi),ylo));svg.appendChild(mk('path',{d:p+`L${(L+pw).toFixed(1)},${base}L${L},${base}Z`,style:`fill:${col(s)};opacity:.10`}))}
   svg.appendChild(mk('path',{d:p,style:`fill:none;stroke:${col(s)};stroke-width:${s.w||1.8};stroke-linejoin:round;stroke-linecap:round`}))});
 // 被截掉的异常值：边缘画小三角，悬停看真实值
 if(clipped){const arr=j.s[vis[0].k];let lastx=-9;idx.forEach(i=>{const v=arr[i];if(v==null)return;const x=X(T0(D[i]));if(x-lastx<4)return;
   if(v>hi){svg.appendChild(mk('path',{d:`M${x-3},${TP+5}L${x+3},${TP+5}L${x},${TP}Z`,class:'clipm'}));lastx=x}
   else if(v<lo){svg.appendChild(mk('path',{d:`M${x-3},${TP+ph-5}L${x+3},${TP+ph-5}L${x},${TP+ph}Z`,class:'clipm'}));lastx=x}})}
 // 最新一个点：实心圆 + 当前值
 if(!c.stack&&c.last!==false&&vis.length){const s=vis[0],arr=j.s[s.k];let li=idx.length-1;while(li>=0&&(arr[idx[li]]==null))li--;
  if(li>=0){const v=arr[idx[li]],x=X(T0(D[idx[li]])),y=YC(v);svg.appendChild(mk('circle',{cx:x,cy:y,r:3.5,style:`fill:${col(s)};stroke:var(--card);stroke-width:1.5`}));
   if(R>40&&!(c.lines&&c.lines.length)){const tx=mk('text',{x:x+7,y:y+3.5,class:'lastv',style:`fill:${col(s)}`});tx.textContent=F[c.fmt](v);svg.appendChild(tx)}}}
 const xh=mk('line',{y1:TP,y2:TP+ph,class:'xh',visibility:'hidden'});svg.appendChild(xh);
 const dots=vis.map(s=>{const d=mk('circle',{r:4,style:`fill:${col(s)};stroke:var(--card);stroke-width:2`,visibility:'hidden'});svg.appendChild(d);return d});
 const hit=mk('rect',{x:L,y:TP,width:pw,height:ph,fill:'transparent'});svg.appendChild(hit);
 this.plot.querySelectorAll('svg').forEach(x=>x.remove());this.plot.insertBefore(svg,this.tip);
 // 图例（在图下方）：值跟最新一天；可开关的线点一下切换
 this.leg.innerHTML='';const li=idx[idx.length-1];
 if(ser.length>1||c.stack)ser.forEach(s=>{const sp=document.createElement(c.toggle?'button':'span'),i=document.createElement('i');i.className=c.stack?'box':'';i.style.background=col(s);
  if(c.toggle){sp.type='button';sp.className='lg'+(self.off[s.k]?' off':'');sp.setAttribute('aria-pressed',self.off[s.k]?'false':'true');sp.onclick=()=>{self.off[s.k]=self.off[s.k]?0:1;self.draw()}}
  sp.appendChild(i);sp.appendChild(document.createTextNode(s.n+' '));const b=document.createElement('b');let v=null;for(let k=idx.length-1;k>=0&&v==null;k--)v=j.s[s.k][idx[k]];
  b.textContent=v==null?'—':(c.stack&&pct?((tot[tot.length-1]?v/tot[tot.length-1]*100:0).toFixed(1)+'%'):F[c.fmt](v));sp.appendChild(b);this.leg.appendChild(sp)});
 const tsv=idx.map(i=>T0(D[i]));
 const bd=this.btc;let bts=null;if(bd&&bd.s.v)bts=bd.d.map(T0);
 function btcAt(t){if(!bts)return null;let a=0,b=bts.length-1;if(t<bts[0])return null;while(b-a>1){const m=(a+b)>>1;if(bts[m]<=t)a=m;else b=m}const k=bts[b]<=t?b:a;return bd.s.v[k]}
 function at(px){let a=0,b=tsv.length-1;const t=t0+(px-L)/pw*(t1-t0);while(b-a>1){const m=(a+b)>>1;if(tsv[m]<t)a=m;else b=m}return Math.abs(tsv[a]-t)<Math.abs(tsv[b]-t)?a:b}
 this.show=n=>{if(n==null||n<0){xh.setAttribute('visibility','hidden');dots.forEach(d=>d.setAttribute('visibility','hidden'));self.tip.style.display='none';return}
  const i=idx[n],x=X(tsv[n]);xh.setAttribute('x1',x);xh.setAttribute('x2',x);xh.setAttribute('visibility','visible');
  self.tip.innerHTML='';const hd=document.createElement('div');hd.className='td';hd.textContent=D[i]+' UTC'+(c.weekly?(ZH?' · 本周五读数':' · Friday reading'):'');self.tip.appendChild(hd);
  vis.forEach((s,k)=>{const v=j.s[s.k][i];const yv=c.stack?stk[k].hi[n]:v;
   if(yv!=null&&isFinite(yv)&&(!c.log||yv>0)){dots[k].setAttribute('cx',x);dots[k].setAttribute('cy',c.stack?Y(yv):YC(yv));dots[k].setAttribute('visibility','visible')}else dots[k].setAttribute('visibility','hidden');
   const r=document.createElement('div');r.className='tr';const ii=document.createElement('i');ii.style.background=col(s);const sp=document.createElement('span');sp.textContent=s.n;
   const b=document.createElement('b');b.textContent=v==null?'—':F[c.fmt](v)+(c.stack&&tot[n]?'  '+(v/tot[n]*100).toFixed(1)+'%':'');r.append(ii,sp,b);self.tip.appendChild(r)});
  if(c.stack){const r=document.createElement('div');r.className='tr';const sp=document.createElement('span');sp.textContent=ZH?'合计':'Total';
   const b=document.createElement('b');b.textContent=usd(tot[n]);r.append(document.createElement('i'),sp,b);self.tip.appendChild(r)}
  if(c.zone&&vis.length){const v=j.s[vis[0].k][i];if(v!=null){const z=c.zone.find(q=>q.ub==null||v<q.ub);if(z){const r=document.createElement('div');r.className='tr';
   const sp=document.createElement('span');sp.textContent=(ZH?'区间：':'Zone: ')+z.n;sp.style.color=`var(--${TONE[z.t]||'ink2'})`;r.append(sp);self.tip.appendChild(r)}}}
  if(c.states&&c.stk&&j.s[c.stk]){const st=c.states[j.s[c.stk][i]];if(st){const r=document.createElement('div');r.className='tr';
   const sp=document.createElement('span');sp.textContent=st.n;sp.style.color=`var(--${st.c})`;r.append(sp);self.tip.appendChild(r)}}
  if(bts){const bv=btcAt(tsv[n]);if(bv!=null){const r=document.createElement('div');r.className='tr';const sp=document.createElement('span');sp.textContent=ZH?'当天 BTC':'BTC that day';
   const b=document.createElement('b');b.textContent=F.price(bv);r.append(document.createElement('i'),sp,b);self.tip.appendChild(r)}}
  self.tip.style.display='block';const tw=self.tip.offsetWidth;let lx=x+14;if(lx+tw>W)lx=x-tw-14;self.tip.style.left=Math.max(0,lx)+'px';self.tip.style.top=(TP+4)+'px'};
 const move=e=>{const r=svg.getBoundingClientRect(),px=(e.clientX-r.left)*W/r.width;const n=at(px);const day=D[idx[n]];
  (c.group?groups[c.group]:[self]).forEach(g=>g.showDate?g.showDate(day):0)};
 const leave=e=>{if(e.pointerType==='touch')return;(c.group?groups[c.group]:[self]).forEach(g=>g.show&&g.show(null))};
 hit.addEventListener('pointermove',e=>{if(e.pointerType!=='touch')move(e)});hit.addEventListener('pointerdown',move);hit.addEventListener('pointerleave',leave);
 this.showDate=day=>{if(!self.show)return;const tt=T0(day);let best=-1,bd=Infinity;for(let n=0;n<tsv.length;n++){const d=Math.abs(tsv[n]-tt);if(d<bd){bd=d;best=n}}
  self.show(bd<=8*864e5?best:null)};
};
// 手机：点按图表显示读数，再点空白处关闭
document.addEventListener('pointerdown',e=>{if(e.target.closest&&e.target.closest('.uc-plot'))return;Object.values(groups).flat().forEach(g=>g.show&&g.show(null));
 document.querySelectorAll('.uc-chart').forEach(el=>{const t=el.querySelector('.uc-tip');if(t)t.style.display='none'})},{passive:true});
window.ucChart=function(el,cfg){return new Chart(el,cfg)};
// 进入视口才初始化（Tab 里隐藏的图不抢首屏）
function boot(el){if(el._uc)return;el._uc=1;try{window.ucChart(el,JSON.parse(el.getAttribute('data-chart')))}catch(e){console.error(e)}}
const io='IntersectionObserver' in window?new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){io.unobserve(e.target);boot(e.target)}}),{rootMargin:'200px'}):null;
document.querySelectorAll('[data-chart]').forEach(el=>{if(io)io.observe(el);else boot(el)});
window.ucBootCharts=root=>(root||document).querySelectorAll('[data-chart]').forEach(el=>{if(el.offsetParent!==null)boot(el)});
})();
"""

SHARE_JS = r"""
(function(){
const H2C=['/assets/vendor/html2canvas.min.js','https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js','https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js'];
const ZH=document.documentElement.lang.startsWith('zh');
function toast(t){let e=document.querySelector('.toast');if(!e){e=document.createElement('div');e.className='toast';document.body.appendChild(e)}
 e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2600)}
function one(u){return new Promise((ok,no)=>{const s=document.createElement('script');s.src=u;s.onload=ok;s.onerror=()=>{s.remove();no()};document.head.appendChild(s)})}
async function lib(){if(window.html2canvas)return;for(const u of H2C){try{await one(u);if(window.html2canvas)return}catch(e){}}throw new Error(ZH?'截图库加载失败，请检查网络':'Could not load the screenshot library')}
window.ucShare=async function(o){
 toast(ZH?'正在生成长图…':'Rendering image…');
 const st=document.createElement('div');st.className='sc';
 st.innerHTML='<div class="sc-hd"><img src="/assets/avatar-96.png" alt=""><div><b>'+(ZH?'链上大叔研究台':'Uncle Onchain')+'</b><i>uncleonchain.com · @Uncle_Onchain</i></div>'+
  '<div class="sc-date">'+(o.date||'')+'</div></div><div class="sc-title">'+o.title+'</div>'+(o.sub?'<div class="sc-sub">'+o.sub+'</div>':'')+o.html+
  '<div class="sc-ft"><b>uncleonchain.com</b><span>@Uncle_Onchain</span><span style="margin-left:auto">'+(o.src||(ZH?'只给数据 · 不构成投资建议':'Data only · not investment advice'))+'</span></div>';
 document.body.appendChild(st);
 if(location.search.includes('sharepreview')){st.style.left='0';st.style.zIndex='999';return}
 try{await lib();await new Promise(r=>setTimeout(r,120));
  const c=await html2canvas(st,{scale:2,backgroundColor:'#05070c',useCORS:true,logging:false});
  const a=document.createElement('a');a.download=o.file||'uncleonchain.png';a.href=c.toDataURL('image/png');document.body.appendChild(a);a.click();a.remove();
  toast(ZH?'长图已下载 ✓ 直接发推':'Image downloaded ✓');
 }catch(e){toast((ZH?'生成失败：':'Failed: ')+e.message)}finally{st.remove()}
};
window.ucToast=toast;
})();
"""

# 出看板.py 的叙事报告嵌入：它自带一套 CSS 变量，这里在同一选择器上按主题覆盖
REPORT_OVERRIDE = r"""
:root,:root[data-theme="dark"]{--bg:#05070c;--panel:#0b0e17;--ink:#e8ecf3;--ink2:#a7afc0;--muted:#6b7488;--rule:rgba(255,255,255,.07);
--rule2:rgba(255,255,255,.12);--grid:rgba(255,255,255,.06);--accent:#a3e635;--accent-soft:rgba(163,230,53,.07);--up:#00ffcc;--dn:#ff3366;
--s1:#00ffcc;--s2:#ff7a45;--s3:#5b8cff;--s4:#ffb020;--s7:#c084fc;--sk:#6b7488;--good:#00ffcc;--warn:#ffb020;color-scheme:dark}
:root[data-theme="light"]{--bg:#f5f7fa;--panel:#ffffff;--ink:#0f172a;--ink2:#475569;--muted:#64748b;--rule:rgba(15,23,42,.08);
--rule2:rgba(15,23,42,.15);--grid:rgba(15,23,42,.07);--accent:#4d7c0f;--accent-soft:rgba(132,204,22,.12);--up:#059669;--dn:#e11d48;
--s1:#0d9488;--s2:#ea580c;--s3:#2563eb;--s4:#b45309;--s7:#9333ea;--sk:#94a3b8;--good:#059669;--warn:#b45309;color-scheme:light}
.rpt body,.rpt{font-family:Inter,"Noto Sans SC",-apple-system,"PingFang SC",sans-serif}
.rpt h1{font:700 26px/1.25 Inter,"Noto Sans SC",sans-serif}.rpt h2{font:600 18px/1.35 Inter,"Noto Sans SC",sans-serif}
figure.chart{margin:0;min-width:0}.rpt .plot{position:relative;overflow-x:auto}.rpt .plot svg{display:block;width:100%;min-width:520px;height:auto}
"""
