# AI Agent 赛道 · Codex 任务包（2026-11-14）

大叔 2026-11-14 定：AI Agent 是重点赛道，网站 /ai-agent/ 升级为赛道监控（现有币安 Agent ID 数据保留）。**代码和网站由 Claude 写和推；查证、找数据源、出数据交 Codex。**

- 网站现状和缺口：`aiagent/research/研究进度.md`（G1–G10）
- 自动层：`aiagent/aiagent_daily.py`（DefiLlama 四层手续费 + CoinGecko 分类市值，每天 UTC 05:13），口径 `aiagent/aiagent_config.json`
- 人工登记：`aiagent/aiagent_registry.json`（监控地图、生命周期事件、待核日期 open_items）
- 你上一轮的 v2 研究已入库：功能卡 `aiagent/research/launchpad_cards_v2.json`、报告 `/reports/2026-11-12-ai-agent-launchpad-v2/`

**v2 复核结论（你这轮要知道的）**

- 交叉核对通过：注册表 10-30 累计 143,640；AgentPad 10-23 九个新币、423 个交易地址；Virtuals 30 天费用趋势一致。
- 你记 U 的 AgentPad 10-31～11-11：网站采集（Alchemy 兜底）是完整的，每天交易地址 0～1、新币 0，不用再补。数据在 `public/ai-agent/monitor/core_series.json` 的 `by_platform`。
- 范围缺口：v2 只研究了发射台。服务 / 支付层（Agent 雇 Agent、x402、ERC-8004）、资管（DeFAI）、框架、代币市场都没覆盖。DefiLlama 上 Central City（2026-10 收录）近 30 天手续费约 159 万美元，已是全赛道第一、超过所有 Agent 发射台之和，没人核过真假。

**交付规则**

- 只交结果文件，写到本地研究库 `handoff/aiagent-review/`；**不要 git 提交、不要推送**。大叔上传给 Claude，Claude 核对后放进 `aiagent/review/` 并入网站。
- 每条事实带原始来源链接和核对时间（UTC，到分钟）；查不到写 `"U"`，不估、不填 0。证据分级沿用 v2：A 官方原文 / 可复算链上，B 第三方数据平台，C 媒体 / 社区 / 摘要，U 未知。
- 链上结论要给可复核的样本（tx hash、区块号、合约地址、事件 topic0），并说明用了哪个节点、免费节点能不能跑通（网站日更只能用免费节点 + Alchemy BSC 兜底，其他链没有 key）。
- 不写买卖、仓位、止损建议；不点名没有协议级读数的小市值币；不交大叔的持仓、地址、key。
- 每个任务单独一个文件，文件名见下。做不完的部分在文件里写 `status: partial` 和卡在哪。

## A1 服务层真实性 → `a1_commerce_checks.json`（优先）

对象：DefiLlama「AI Agents」类目里服务 / 支付层的 Central City、TermiX、Orbio、Fuci、FrostyFi、MiroShark（x402 API）。每家回答：

1. 手续费是怎么算的：读 DefiLlama 适配器源码（`DefiLlama/dimension-adapters` 仓库对应文件），写清统计的合约、事件、币种、费率，是毛额还是平台抽成。
2. 付费方是谁：取最近 30 天付费交易，统计独立付费地址数、前 10 地址占比、付费方与收款方 / 项目方 / 部署者是否有资金往来（自付、循环转账）。给 3～5 条代表性 tx。
3. 有没有补贴 / 积分 / 空投激励在推付费量（官方文档或公告原文）。
4. 结论三选一：`real_demand_likely` / `mixed` / `self_dealing_likely`，加最强反方理由。Central City 必须做完。

```json
{"checked_utc": "…", "items": [{"slug": "central-city", "fee_method": {"adapter_url": "…", "contracts": ["chain:0x…"], "events": ["topic0…"], "basis": "gross|take_rate|U"},
  "payers_30d": {"unique": 0, "top10_share": 0.0, "linked_to_project": "yes|no|U", "samples": ["tx…"]}, "incentives": "…|U",
  "verdict": "real_demand_likely|mixed|self_dealing_likely|U", "counter": "…", "grade": "A|B|C|U", "sources": ["…"]}]}
```

## A2 x402 与 ERC-8004 的链上数据源 → `a2_rails_sources.json`

目标是让网站每天自动算：x402 全网每日支付笔数 / 金额 / 独立付款方；ERC-8004 各链注册表每日新增 Agent 数。

1. x402：主要 facilitator（Coinbase CDP 及其他公开 facilitator）在 Base / Solana / 其他链的结算地址清单，怎么从链上识别一笔 x402 支付（USDC `transferWithAuthorization` + facilitator 发起？事件特征？），给 10 条已确认样本和 10 条容易误判的反例。公开的统计站（x402scan 等）数字可作 B 级对照，写清它们的口径。
2. ERC-8004：标准当前版本、Identity / Reputation / Validation 三个注册表在各链的官方部署地址（Ethereum、Base、BNB、Arc 等，以官方仓库或文档为准）、注册事件签名、首个注册区块、截至核对日的累计注册数。币安 Agent ID 注册表（0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F）是不是 ERC-8004 实现，要有源码依据。
3. 对每个数据源注明：免费节点按日扫是否可行（单日日志量估计、`eth_getLogs` 区块范围限制）。

## A3 Virtuals ACP 逐日服务收入 → `a3_acp_revenue.json`

v2 复核是 0/90 天可得。这轮换路线：ACP 的托管 / 结算合约地址（Base，按版本）、任务创建 / 付款 / 完成 / 退款的事件签名，能否从链上重建逐日「已完成任务的付款金额 − 退款」。给 2026-08-14 起能复算的日表（不能复算的日子写 U）、5 个样本任务从创建到结算的完整 tx 链，以及和 Virtuals 官网 aGDP / 收入面板的口径差异。ChainWard 的 money in 不能当收入（v2 已说明）。

## A4 非 BNB 发射台的使用量 → `a4_launch_usage.json`

Virtuals（Base 默认引擎）、Clanker（v4 / v5）、Bankr（Doppler，Base 与 Robinhood Chain）：工厂合约地址（按版本）、创建 / 毕业事件签名、2026-10-15～11-13 每日发币数、毕业数（适用的话）、独立买家数口径。能做到 Clanker 的 Agent 相关子集（例如通过 Bankr / Virtuals / 带 Agent 身份的部署者）就分开给，做不到写 U。

## A5 时间线与 C 级证据升级 → `a5_timeline.json`

1. `aiagent/aiagent_registry.json` 的 `open_items` 六条逐条给官方日期和原文链接（Clanker v5 发布、Neynar 接手 Farcaster / Clanker、Olas Pearl Mini 停服、Giza 旧版迁移、Flap ID Agent Curve 与 Four.meme OpenFour 上线、Bankr 默认链改 Robinhood Chain、elizaOS / auto.fun 收尾、DataHaven / Yupp 关停、Binance AI Pro beta）。
2. 已登记事件里 C 级的（Pump.fun Tokenized Agent 上线 / 停新、MoonFun 转型、Top Hat 失效）找官方原文升级；找不到保留 C 并写尝试过的来源。
3. K06 Flap ID Agent Curve、K07 Four.meme OpenFour 两张卡目前是 C 级：用链上合约（网站采集里已用的 Flap Portal 0xe2cE…9De0 `FlapNFTGated`、Four.meme TokenManager2 模板位）核实当前参数（阈值、费率、毕业去向、门禁范围），能升 A 的升 A。
4. 新发现的赛道事件（上线 / 停新 / 转型 / 收购 / 安全事故），同样要日期 + 原文，格式：

```json
{"events": [{"date": "YYYY-MM-DD", "who": "…", "kind": "launch|stop|pivot|peak|incident|acquisition", "zh": "一句话", "en": "one line", "grade": "A|B|C", "src": "链接"}],
 "open_items_resolved": [{"item": "…", "date": "…|U", "src": "…", "tried": ["…"]}]}
```

## A6 框架与开发者清单 → `a6_frameworks.json`

elizaOS、Virtuals GAME、Coinbase AgentKit、Solana Agent Kit、Fetch uAgents / Agentverse、Olas（open-autonomy）、OKX Agent Trade Kit、x402 SDK、ERC-8004 参考实现，以及你认为该加的（≤ 15 个）：GitHub 组织 / 主仓库名、对应链、npm / PyPI 包名、是否已归档或改名（附原文）。Claude 用 GitHub Actions 的 token 每周跑提交数 / 贡献者 / 发版，包下载量走 npm / PyPI 公开接口。

## 优先级

A1 > A5（第 3 点）> A2 > A3 > A4 > A6。A1 和 A5 尽量一起交，其余可以分批。
