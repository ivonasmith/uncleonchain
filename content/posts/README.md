# 手写文章怎么发布

发射台日更是自动的，不用管这里。macro / rotation / narrative 三个板块是手写内容，两种稿子都支持，
放同一个目录，按扩展名自动识别：

- `content/posts/macro/`      宏观流动性
- `content/posts/rotation/`   板块轮动复盘
- `content/posts/narrative/`  叙事币埋伏

## 方式一：轻量笔记（.md）

文件名任意，比如 `2026-09-28-btc-etf-flow.md`：

```
---
标题: 文章标题
日期: 2026-09-28
摘要: 列表页用的一句话
---
正文，支持 # 标题、**粗体**、*斜体*、`代码`、- 列表、> 引用、[链接](url)。
也可以直接写整段原样 HTML（比如拼 .callout / .kpis / .hook 这些组件，见下面）。
```

## 方式二：完整定制报告（.html）

像推特分析报告、交易计划表那种带 SVG 图表的整篇 HTML（Polar/Claude 生成的那种），整份文件原样放进去，
不用拆成 Markdown——网站只提取 `<body>` 内容套站点导航/页脚，报告自己的 `<style>` 原样保留，视觉不丢。
标题/日期/摘要从 `<head>` 里的注释读，没写就退回 `<title>` 和文件时间：

```html
<!--meta
标题: 牛市启动在减半前 15 个月
日期: 2026-08-22
摘要: 四年周期没死，死的是幅度——三波几乎一样深的下跌，$79,009 分水岭。
-->
```

网站分两套视觉语言。首页、四个板块列表、口径、更正记录、关于，以及发射台的「文字解读」深度页
（`/launchpad/report/`）用编辑体报告风格（Georgia/Songti SC 衬线大标题、暖白底、金色强调、
蓝/红/绿三色 callout），跟推特报告和交易计划表是一个系统，`pipeline/出网站.py` 里的 `SITE_CSS`
定义了 `.lead / .tldr / .hook / .kpis / .kpi / .callout(.blue/.red/.gray) / .chart-fig / .sign`
这些组件，.md 笔记想用同款视觉，直接在正文里手拼这些 class 即可。

发射台的数据页（`/launchpad/` 总览 + `/launchpad/platforms/<slug>/` 分平台页）用另一套深色终端仪表盘
风格（参考 Token Terminal / DefiLlama），`TERMINAL_CSS` 定义，总览页是全市场排行表 + 90 天走势图
（总数据），点进任意一行是该平台自己的手续费/收入/估值详情（分数据）。这套风格只服务于原始数据展示，
不影响上面的编辑体报告风格，两边各管各的，互不干扰。

两种稿子跑一次 `python3 pipeline/出网站.py`（或等每日定时任务自动跑）就会出现在对应板块页面和首页卡片上。
