# uncleonchain · 给 Claude 的项目说明

链上大叔研究台（uncleonchain.com）：个人 web3 链上数据情报终端。大叔（仓库主人）只给方向，
Claude 是这个产品的操盘手：自己判断、自己做完、自己提交推送，尽量不回头问人。

## 工作方式

- 用中文沟通。改完直接 commit + push 到 `main`，不开 PR。Cloudflare Pages 从 `site/` 自动部署，1～2 分钟上线。
- 推送前本地跑一遍 `LP_DATA=$PWD/data LP_OUT=$PWD/build python3 pipeline/出网站.py`，用 Playwright 截图自查（Chromium 在 /opt/pw-browsers/chromium）。
- 数字先自己核对再说；拿不到真实数据的指标标「待接入」，绝不编数字或拿近似值冒充。
- 只给数据和过程记录，不写买卖建议。

## 结构

- `pipeline/跑日更.py --site`：GitHub Actions 每天 UTC 10:20 跑（推送 pipeline/content/assets 也会触发）。
  拉日度 → 读销毁 → 拉估值 → 拉Arc → 出看板 → 拉宏观 → 写日志 → 出网站，结果提交回 `data/` 和 `site/`。
- `pipeline/宏观规则.py`：四层框架（L2 除外，见 `l2/`）（流动性 / 周期 / 筹码 / 情绪）的指标注册表、区间规则、层结论、预警、日志与周月复盘生成。
  每个指标 = 一条「判定序列」（原始或派生，如 13 周变化，W-FRI 对齐）+ 一张 cuts 区间表，卡片、详情页全历史图、正常波动范围都用它。
  L1 按《L1 宏观层数据维度规格》（2026-10-02，10-04 修订）：乐观度 / 信用 / 实际利率四态 / 情境格 / 净流动性闸门；
  L1-B 加密资金通道（只确认不预测）：稳定币主线（去重）/ 交易子弹（剔除 Tron + 含 Tron 并列）/ ETF / 升水 / 资金轮动矩阵；
  判定 = 顺风 / 中性 / 中性偏谨慎 / 逆风。规则改动写进 `RULE_CHANGES`（更正记录页自动展示），已写入的历史日志不改。
  日志里中英文字段并存（…EN），英文站直接读。
- `l2/`：L2 周期状态机（大叔给的方案，和《BTC周期层L2研究》§7 同一份代码，**规则别在网站里重写**）。`.github/workflows/l2-daily.yml`
  每天 UTC 02:17 跑 `l2/l2_daily.py`（Coin Metrics + bitview.space，需要 pandas）→ `data/l2/l2_latest.json` + `l2_history.json` → 出看板 → 出网站。
  缓存 `l2/cache/` 走 actions/cache，不进仓库。宏观页 L2 段、日志里的 L2 层结论 / 「L2」快照 / 状态切换预警都只读这两个 json；
  原 L2 单指标卡（MVRV / MVRV Z / Realized Price / NUPL / Mayer / Puell / Pi Cycle）2026-10-08 撤掉，旧链接 `_redirects` 301 到 /macro/#layer-2。
  本地沙箱连不上 Coin Metrics / bitview（代理拒绝），L2 首跑只能在 Actions 里验。
- **指标注册表**（M12）= `宏观规则.REGISTRY`：每条带 层 / 组 / 序 / 状态（live · pending · retired；自录的满 90 天前自动「记录中」）/ cuts（tone 即 bias：up 顺风 · neutral · dn 逆风 · warn 留意）/
  fmt / 出处 / 界（边界文字）/ 解读。宏观页各 Tab 的卡片分组、待接入占位卡、详情页、上一个 / 下一个、口径页指标表、停用说明页全部从它生成——改层的数据维度只改注册表 + 数据。
  L2 六个「估值与持有者」指标读 `data/l2/l2_series.json`（`R.attach_l2` 挂到 S 上）。
- `config/`：`composite.json` 综合研判短句表（附录 D，四层合成，`pipeline/综合研判.py` 拼接）、`site.json`（定时任务说明；时间从 workflow cron 读）、
  `glossary.json` 术语表与标签定义（G7）、`l1_rules.json`（宏观总文档 §10.2 逐条照抄）。改措辞只改配置。
- `content/changelog.json`：更新日志（附录 B）。**每次上线新功能 / 改口径都在最前面加一条**（`notify: true` 才弹窗；`data` 类带 `corrections_anchor` 并在 `RULE_CHANGES` 里加原因）。
- 全历史数据：`site/data/series/<id>.json`（归档，截至上月末，每月 1 日重写；数据源回改时重写）+ `<id>.recent.json`（本月）。
  构建时和上一版比较，7 天以前的数据变动 > 0.5% 记进 `data/data_revisions.json`（更正记录页展示）。`site/data/latest.json` = 全站当前读数唯一来源。
- 页面上的「当前读数」一律读本次构建的最新值（`G["RS"]`），日志只在日志页和标「日志 · 冻结」的位置出现；统计窗口规则在 `宏观规则.stats_window`（D3）。
- `pipeline/出网站.py` + `pipeline/网站样式.py`：中英双语（英文挂 /en/，`T(中, 英)` 包所有文案）、深 / 浅主题（CSS 变量，
  别写死颜色）、面包屑、交互走势图（`chart_div` + /data/*.json）。指标详情页 /macro/<key>/。
- `data/解读日志/{日,周,月}/`：写入即冻结。同日重跑且核心缺失变少才覆盖并标「补录」。
- `content/posts/<macro|rotation|narrative>/`：手写文章（.md 或整篇 .html）；`content/journal/<日期|周|月>.md`：人工点评。
- `content/reports/`：分析报告。大叔给排好的浅色 HTML（中文 `<slug>.html`，英文 `<slug>.en.html`），iframe 原样嵌入、不加摘要框；
  深色版出网站时自动生成（颜色明度翻转），不用手调。元信息写 `<!--meta-->`，流程见目录 README。
- `assets/`：头像、favicon、og 卡（`pipeline/做图标.py` 生成），`assets/vendor/html2canvas.min.js` 由 Actions 自托管。
- 视觉：底 #05070c、卡片 #0b0e17、1px rgba(255,255,255,.06) 细线、涨 #00ffcc、跌 #ff3366、品牌青柠 #a3e635（只用于导航和按钮）。
  浅色主题（太阳 / 月亮按钮切换）的配色在 `网站样式.py`。左侧常驻导航，每个板块独立 URL（方便推特直链）；子页面顶部有面包屑。

## 待办（按优先级）

1. 核对 2026-10-02 L1 改版后的 Actions 首跑：FRED 新序列（NASDAQ100 / VIXCLS / T10YIE / BAA10Y / NFCI / BAMLH0A0HYM2 / WTREGEN）、
   DefiLlama 稳定币分组（附注里有实际匹配到的币）、ETF（haturatu 镜像）、CME 升水（Yahoo 合约代码能否取到）是否都通；
   乐观度 z 在 2026-09-25 应约为 +0.49、净流动性约 $5.77T（研究报告 §7.1），对不上就查口径。
2. 宏观 v2：Coinglass（多空比 / 爆仓，需 key）、Deribit 期权 P/C 与 IV。2026 年底复核净流动性闸门（规格 D1）。
3. 叙事雷达：DefiLlama 无代币协议 × 收入增速筛选；Robinhood Chain / Arc 发射台大户地址追踪。
