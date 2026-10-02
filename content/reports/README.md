# 分析报告怎么发布

`/reports/` 板块放周度节奏的深度报告：针对一个方向或议题做全方位分析，给出可以当决策依据的结论。
网站是 Cloudflare Pages 静态托管，**不需要服务器**：报告文件提交进这个目录，下一次 Actions 运行（或推送后自动触发的那次）就会上线。
报告写入后不改，后续修正另起一篇。

## 三种放法（按扩展名自动识别）

1. **整篇 HTML（推荐，Notion 导出直接用）**：`content/reports/2026-10-05-l1-macro.html`
   Notion 页面 →「导出」→ HTML。报告会原样放进页面里的 iframe，自己的排版、样式、SVG 图表都不受站点样式影响，
   读者还可以点「在新窗口全屏阅读」。
2. **带图片的文件夹**：`content/reports/2026-10-05-l1-macro/index.html` + 同目录下的图片等附件
   （Notion 导出的 zip 解压后把那个 html 改名 index.html 即可，图片相对路径保持不变）。
3. **Markdown**：`content/reports/2026-10-05-xxx.md`，头部写元信息（同 content/posts 的写法），正文套站点排版。

## 元信息（摘要卡片和报告页顶部的「摘要 + 核心结论」用）

HTML 报告写在 `<head>` 里的注释，Markdown 写在开头的 `---` 之间：

```html
<!--meta
标题: BTC 全周期宏观相关性与归因研究
日期: 2026-10-02
摘要: 2022 年以来宏观 + 美股 + 稳定币只能解释 BTC 周波动约 21%；L1 是调速器，不是方向盘。
结论: 乐观度（纳指 13 周 + 信用利差）是 L1 第一指标 | 实际利率急升是独立逆风，要和信用条件一起定档 | ETF 资金流是滞后顺势指标，不是抄底信号
标签: 宏观, L1, 研究
notion: https://www.notion.so/xxxx
标题EN: BTC full-cycle macro attribution study
摘要EN: Since 2022, macro + equities + stablecoins explain ~21% of BTC's weekly moves; L1 is the throttle, not the steering wheel.
结论EN: Optimism is the first L1 gauge | A real-yield surge is an independent headwind | ETF flows lag price
-->
```

- `结论` 用 `|` 分隔多条；`标签` 用逗号分隔；`notion` 可选，填了会在摘要框里给一个「Notion 原文」链接。
- 带 `EN` 后缀的字段可选，英文站优先用；没写就显示中文并标注「written in Chinese」。
- 文件名决定网址：`2026-10-05-l1-macro.html` → `/reports/2026-10-05-l1-macro/`。
