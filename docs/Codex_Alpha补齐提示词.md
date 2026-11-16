# 给 Codex 的提示词：补齐 Alpha 方法论（复制整段）

---

你在协作链上大叔研究台（仓库 ivonasmith/uncleonchain）。暂时你连不上 GitHub，所以这次**不推送**：把每个交付文件的完整内容写好，按文件名整理，大叔会转给 Claude 核对后并入。

## 背景

我们的 Alpha 雷达要按《Alpha 标的筛选研究体系 · 全面版》（文档原文大叔已给 Claude，你可以向大叔要 `index.html`）运行。现在网站有一部分，但对照文档还缺很多。缺口清单在仓库 `docs/Alpha方法论对照缺口.md`，请先读它，再做下面的任务。

## 硬规则（每条都要守）

1. 每条事实带**来源链接**和**核对日期（UTC）**。查不到写 `"U"`，说法冲突写「说法不一」并给两边链接。不估、不编、不拿近似值冒充。
2. 证据分类写清楚：**官方规则 / 第三方数据 / 独立链上复核 / 假设代理**。官网和它自己的官方 X 不算两个独立来源；引用同一聚合数据的多篇文章也不算多份验证。
3. 拒绝、否定性结论必须有一手证据（官网、官方文档、官方 X、合约 / 链上浏览器、DefiLlama 方法论）。只有媒体、聚合站、别人的帖子 → 最多记「待核验」。
4. 不写买入、卖出、仓位、止损、目标价，不写「值得关注 / 有潜力」。
5. 只研究正规项目。不研究部署后 0–6 小时的打狗、纯 MEME 发射。
6. 交易所公告和首笔成交的时间，**原样记录**（公告时间、修订时间、计划开盘、首笔成交各一个字段，时区写 UTC），不要合并成一个时间。
7. 数据有缺口就写明缺口（哪个站打不开、哪段没有历史），不要用记忆代替来源。
8. 不要碰 `site/`、`data/`、`pipeline/`、`*.py`。只写下面列的交付文件。

## 任务一：交易所公告这条线（优先，大叔要求必须做完）

### X1 交易所公告源验收 → `alpha/review/x1_exchange_sources.json`

对下面每个交易所，核对它是否有**公开的上新 / 上币公告列表**（官方网页或公开接口），能否拿到：公告标题、发布时间、计划开盘时间、修订时间、现货 / 永续区分、交易对、报价币。

交易所：Binance、Bybit、OKX、Coinbase、Upbit、Bithumb、Kraken、Gate、MEXC、Bitget。

每家一条：
```json
{"exchange": "Binance", "list_endpoint": "URL", "fields_present": {"announce_time": true, "planned_open": true, "revision_time": false, "spot_or_perp": true, "pair": true, "quote": true}, "needs_key": false, "region_blocked": "U", "sample": [{"title": "", "url": "", "announce_utc": "", "planned_open_utc": ""}], "http_status": 200, "checked_utc": "", "verdict": "可接|需key|需换源|不可接", "notes": ""}
```
要求：每家至少抓 ≥ 20 条样本核对字段，写出 http 状态码。说不清的字段写 `"U"`。

### X2 历史 K 线源验收 → `alpha/review/x2_kline_sources.json`

为了算「上市后 30 分钟 / 1 小时 / 4 小时 / 24 小时」的价格路径，需要每家的历史 K 线（1 分钟或更细）。核对：
- Binance：官方 REST 和 `data.binance.vision` 历史归档，是否覆盖 2020 年至今、现货与永续分开。
- 其它所：各自的 K 线 API，能取到的最早日期、粒度、是否需要 key、是否有地区限制。

每家一条，格式同 X1，另写 `earliest_available`、`granularity`、`coverage_gaps`。

### X3 报价币换算日源 → `alpha/review/x3_quote_fx.json`

报价币有 USDT、USDC、BTC、ETH、KRW、USD、EUR 等。找出每种报价币换美元的**日级**来源（稳定币挂钩、BTC 价格、韩元汇率来源等），每个来源写：覆盖区间、粒度、是否免费、误差说明。

### X4 上市事件样本库 → `alpha/review/x4_listing_events.json`

以 Binance 为起点，整理**过去 12 个月**的上币事件，至少 100 条（能做到多少做多少，写明实际条数和漏掉的原因）。每条：

```json
{"event_id": "binance-YYYYMMDD-资产", "asset": "代码", "asset_name": "", "exchange": "Binance",
 "announce_utc": "", "revision_utc": "U", "planned_open_utc": "", "first_trade_utc": "",
 "first_trade_src": "K 线第一根（链接）", "market": "现货|永续|现货+永续", "pair": "", "quote": "USDT|USDC|BTC|…",
 "other_exchanges_listed": [{"exchange": "", "announce_utc": ""}],
 "evidence": [{"url": "", "fields": []}], "checked_utc": "", "notes": ""}
```

要求：`first_trade_utc` 由**我们的程序**从 K 线算出，你只核对公告链接和计划开盘字段；如果你直接能确认首笔成交，也写上并注明来源。

### X5 多所聚类规则草案 → `alpha/review/x5_cluster_draft.md`

同一资产在多家交易所上线时怎么归成一个事件：时间窗口多长、同名不同币怎么排除（如 MASK、MEME 之类撞名）、现货与永续怎么并、先上哪家算「首发」（只限已观测集合）。给 2–3 个你查到的真实例子。写成草案，大叔定。

## 任务二：补方法论里的其它缺口

### M1 技术与开发者雷达 → `alpha/review/m1_dev_sources.json`

核对 EIPs / ERCs 提案仓库、GitHub 版本 release 与 tag 的公开接口：能否拿到新提案的首次出现时间、状态变化、版本发布时间。每个源写：是否需要 key、速率限制、样本。另写「概念 → 原作者 → 论文 / 仓库 → 实现版本 → 部署 / 测试网 → 参与角色」链条的字段建议（每个字段能从哪拿到）。

### M2 链上创世动作字段 → `alpha/review/m2_genesis_fields.md`

文档要求：部署、初始化、参数变更、奖励启动、建池、迁移，每个动作保存链、交易哈希、区块、日志序号、事件时间、系统发现时间。请列出每条链（Robinhood、Arc、BSC、Base、Ethereum、Elysium、Solana 如有）的区块浏览器 API 能否按合约查事件，写出样例事件签名（topic0）和需要解码的字段，并标出哪些动作能靠事件区分、哪些只能靠函数解码。

### M3 卡片缺的字段：决策条件与证据分类 → `alpha/review/m3_card_schema.md`

对照文档第十四节（完整研究结论应当回答的 9 件事）和附录三 A（证据分类），给一份字段建议：每个字段的名字、含义、举例、来源从哪拿。特别要把「决策条件（什么事实晋级 / 失效 / 退出 / 重开）」和「结果复查（何时复查、评用户还是评价格还是评净收益）」写清楚。

### M4 代币研究七项的数据来源 → `alpha/review/m4_token_seven.json`

文档附录一 E 的七项（安全筹码、交易结构、重估逻辑、社区组织、产品捕获、供给、外部验证），对每项列出能用的公开数据来源、它能支持什么、不能支持什么。不要替我们打分，只列来源。

### M5 监控的六个观察面 → `alpha/review/m5_monitor_sources.md`

文档第十二节的观察面：机制与产品、价值捕获、反身性循环、权限与资产安全、筹码与流动性、社区与参与、交易结构、信息与数据。每个面列出：要盯哪个公开数据、频率、能否自动拿、需要的 key。

### M6 社交渠道与钱包标签的边界 → `alpha/review/m6_social_wallet.md`

文档第三节第 5 条和附录三 C：官方 TG / Discord / X / Farcaster，Cielo、GMGN、Arkham 之类。每个来源：有没有免费接口、能拿到什么、服务条款是否允许、标签准确性有什么已知问题。不要给「喊单胜率」这类结论。

### M7 价格路径与收益口径样例 → `alpha/review/m7_return_examples.md`

挑 3 个已经发生的上市事件（X4 里取），按文档附录二 B、C 的定义算一遍：发现参考价、可执行买卖价、30 分钟 / 1 / 4 / 24 小时窗口、D60 价格与交易状态。写清每一步用的数据和它的延迟。把算法的每一步写成伪代码，我按它实现。

### M8 历史对照组 → `alpha/review/m8_control_candidates.json`

文档要求用「同来源全体 / 仅通过门槛 / 加复杂筛选」做简单基准。从 `data/alpha/alpha_leads.json`（大叔可提供）里取同期同类、后来表现差或没有继续的项目，列 ≥ 10 个候选做对照，每个写：为什么它是对照、当时可观测的信息、后来的结果（带来源）。

## 交付要求

- 所有文件放 `alpha/review/`，文件名按上面写的，不要改名。
- JSON 必须能解析（写完用 `python3 -m json.tool 文件名 > /dev/null` 自查）。
- 每个文件开头或首条写一句：核对日期、用到的工具、哪些没有做完、为什么。
- 做不完也要交：已完成的交，没完成的在 `missing` 或 `notes` 里写明，不要空着。
- 最后在 `docs/协作记录.md` 末尾追加一行：日期 · Codex · 做了哪些 / 没做完的 / 查不到的。

## 优先级

X1 → X2 → X4 → X3 → X5 → M3 → M4 → M1 → M2 → M5 → M7 → M8 → M6。

X 系列是交易所事件这条线，大叔说必须做完；先做完 X1、X2 再进入其它。

---

（给大叔的说明：Codex 交完后，你把每个文件的内容转给我，我逐个核对再并入仓库。这些任务已经登记在 `alpha/review/README.md`，之后也会出现在全站待办里。）
