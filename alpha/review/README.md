# Alpha 雷达 · 外部任务包（2026-11-14）

> **状态：T1 / T2 / T3 已于 2026-11-14 交回**（`sources_probe.json`、`d30_20261016.json`、`tokenless_checks.json`），已并入；候选池状态由 `alpha_daily.py` 读 `*_checks.json` 写进台账。新一轮补证照同一格式交 `<批次>_checks.json`。

大叔 2026-11-14 定：Alpha 雷达和核心选币互补，只研究正规项目（无币协议、新协议、新产品、新机制、升级、上所），
**不做部署后 0–6 小时 / 纯 MEME 打狗**。代码和网站由 Claude 写和推，Codex 负责查证和出数据。

- 方法论：`alpha/research/Alpha标的筛选研究体系.md`（网站版，去掉了执行纪律）
- 进度和口径：`alpha/research/研究进度.md`
- 雷达脚本：`alpha/alpha_daily.py`，输出 `data/alpha/alpha_latest.json`、`alpha_leads.json`、`alpha_history.json`

**交付规则。** 只交结果文件，放在 `alpha/review/` 下（文件名见各任务）；不要改 `site/`、`pipeline/`、`alpha/*.py`、`data/`。
每条事实带来源链接和核对日期（UTC）；查不到写 `"U"`，不要估。不写买卖、仓位、止损建议。
旧交接提示词、凭据、私群原文不要放进仓库（仓库是公开的）。

## T1 发现源验收 → `alpha/review/sources_probe.json`

逐个核对下面这些源，能不能每天无 key（或用免费 key）稳定拉到「新出现的东西」：

| 源 | 想拿到什么 |
|---|---|
| ethresear.ch（Discourse `/latest.json`、`/t/<id>.json`） | 新帖：发布时间、最后活动时间、作者、标签 |
| EIPs / ERCs 仓库 | 新提案 PR：打开时间、状态变化 |
| GitHub（指定组织 / 仓库的 releases、tags） | 新版本发布时间 |
| Snapshot Hub GraphQL、Tally | 新提案、投票结束、执行交易 |
| 交易所上新公告：Binance、OKX、Bybit、Upbit、Coinbase | 公告时间、计划开盘时间、现货 / 永续、交易对 |

每个源一条：

```json
{"source": "ethresear.ch", "endpoint": "https://…", "auth": "none|free_key|paid", "rate_limit": "…",
 "history_depth": "能往回查多久", "time_fields": ["created_at", "…"], "sample": "一条真实响应的节选（删掉无关字段）",
 "blocked_in": "在哪类机房 / 地区被拦（如有）", "verdict": "可接|需key|不可接", "checked_utc": "2026-11-xx", "notes": "…"}
```

## T2 冻结评分 D30 复查 → `alpha/review/d30_20261016.json`

2026-10-16 首批九个候选（BEM / TapeOut、FWA、Clanker Droids、Charms、Alkanes、Pearl、GODL、ZINC、TapeOut ETH）。
按方法论「附录二 C」：相对 BTC 同步峰值倍数、绝对收盘达到发现价 2 倍的完整 UTC 日数、A / B / 否 / 待判。
发现价、价格来源、链和合约照 10-16 原卡，不换池、不换起点。分数不重算，只出结果。

```json
{"id": "BEM", "chain": "…", "contract": "…", "p0_date": "2026-10-16", "p0": 0.0, "p0_source": "…",
 "rel_peak": 0.0, "days_ge_2x": 0, "label": "A|B|否|待判", "missing": ["…"], "checked_utc": "…"}
```

## T3 无币协议补证 → `alpha/review/tokenless_checks.json`

`data/alpha/alpha_latest.json` 里 `tokenless` 的前 30 名（按 rev30）。每个协议：

```json
{"key": "g:parent#polymarket", "name": "Polymarket",
 "token_stance": "官方确认不发币|有积分/空投计划|官方表态会发|没有表态|U", "token_stance_src": "链接", "token_stance_date": "…",
 "revenue_who": "协议收入归谁（公司 / DAO / LP / 用户）", "revenue_method": "DefiLlama 方法论原文要点",
 "wash_or_subsidy": "刷量 / 补贴迹象及证据，或 U", "user_role": "普通人能以什么角色参与（用户 / LP / 积分）",
 "counter": "最强反方一句话", "verdict": "待核验|研究观察|拒绝", "verdict_reason": "…", "checked_utc": "…"}
```

`verdict` 只有三档；「优先研究」「执行评估」由 Claude 和大叔定，不在这里给。
