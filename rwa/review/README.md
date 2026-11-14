# RWA 板块 · Codex 任务包（2026-11-14）

大叔 2026-11-14 定：网站新增 RWA 板块（/rwa/）。**代码和网站由 Claude 写和推；查证、出数据交 Codex**（在大叔电脑上跑，能读本地研究库 `/Users/hi/Documents/ChatGPT/RWA`）。

- 方法框架：`rwa/research/方法框架.md`（判断状态、平台币四态、身份表都以这里为准）
- 进度和交接包审查结论：`rwa/research/研究进度.md`
- 自动层脚本：`rwa/rwa_daily.py`（CoinGecko + DefiLlama，每天 UTC 05:13）；研究层：`rwa/research/watchlist.json`

**交付规则。**

- 只交结果文件（文件名见各任务），写到本地研究库的 `handoff/rwa-review/` 目录；**不要 git 提交、不要推送**。由大叔上传给 Claude，Claude 核对后放进仓库 `rwa/review/` 并入网站。
- 每条事实带原始来源链接和核对时间（UTC，精确到分钟）；查不到写 `"U"`，不要估。交接包里的历史观察不能直接当事实交——要按原始来源重核，并写清重核结果和原来是否一致。
- 不写买卖、仓位、止损建议。不交大叔的持仓、地址、账户配置、API key、私群原文（仓库是公开的）。
- 本地主库是研究底稿，**不要再让旧自动化往旧路径写**（旧路径数据停在 10-20）。迁移前先备份，交付里写明以哪个路径为准。

## R1 研究库导出 → `rwa/review/universe_export.json`

把主库 225 条 + 发现队列 137 条按下面的数据契约导出。**原始值一律保留**（`raw` 字段），映射不了的不要丢、不要猜。

```json
{
 "exported_utc": "2026-11-xxTxx:xxZ", "source_paths": ["outputs/rwa-universe.json", "outputs/rwa-discovery-queue.json"],
 "source_sha256": {"outputs/rwa-universe.json": "…"},
 "counts": {"records": 362, "main": 225, "discovery": 137, "missing_id": 7, "entities": 0},
 "entities": [
  {"entity_id": "ent:域名或稳定 slug", "name": "…", "domains": ["…"], "kind": "company|dao|fund_manager|bank|exchange|unknown",
   "record_ids": ["主库原始 id（缺 id 的写 legacy:<文件>#<序号>）"], "dedupe_basis": "domain|legal_name|manual"}
 ],
 "products": [
  {"product_id": "prod:…", "entity_id": "ent:…", "name": "…", "segment": "fund|treasury|equity|commodity|credit|realestate|collectible|trading|lending|settlement|identity|oracle|derivatives",
   "eligibility": "零售可买|需 KYC|仅合格投资者|仅机构|地区限制：…|U", "eligibility_src": "…", "checked_utc": "…"}
 ],
 "tokens": [
  {"token_id": "tok:<chain>:<address>", "product_id": "prod:…", "entity_id": "ent:…",
   "role": "platform_token|asset_token|native_coin|stablecoin|nft|points|listed_equity",
   "symbol": "…（只作提示）", "chain": "…", "address": "…", "decimals": 0, "src": "…", "checked_utc": "…"}
 ],
 "platform_token_status": [
  {"entity_id": "ent:…", "status": "issued|declared_none|unverified|tradfi", "raw": "原库里的标签原文",
   "evidence": "链接", "evidence_kind": "official|onchain|third_party", "checked_utc": "…"}
 ],
 "contracts": [
  {"chain": "…", "address": "…", "role": "platform_token|asset_token|business|dex_pool|bridge|vault", "entity_id": "ent:…", "src": "…", "checked_utc": "…"}
 ],
 "markets": [
  {"token_id": "tok:…", "venue": "dex|cex", "venue_name": "…", "pool_id_or_pair": "…", "observed_utc": "…", "src": "…"}
 ],
 "enum_map": {"原标签": "四态之一或 U"},
 "unmapped": ["映射不了的原始标签和记录 id"]
}
```

要点：

1. **独立实体数**按实体 + 官网域名去重，给出去重口径和每个实体对应的原记录；362 条记录数和导出数要对得上（含 7 条缺 id 的旧记录）。
2. 平台币状态映射到四态，`explicit_no_platform_token` 这类声明无币的标签要有原文证据才映射成 `declared_none`，没证据的进 `unverified`。
3. 合约按（链 + 地址）去重，**同 symbol 不同链不合并**；原库的 `token_contracts`、`asset_contracts`、`business_contracts` 都要导，按 `role` 区分。
4. 时间字段分开：资料核实（`verified_at`）、目录核实（`directory_checked_at`）、首次发现（`first_seen_at`）、最后检查（`last_checked_at`）不要合成一个。

## R2 判断复核 → `rwa/review/judgments_YYYYMMDD.json`

10-30 的 6 项机会判断（`outputs/rwa-opportunity-decisions-2026-10-30.*`），逐条按原始来源重核到复核当天。每条：

```json
{"id": "与 R1 的 entity_id 或 product_id 对应", "name": "…", "old_version": "2026-10-30", "old_state": "原文状态",
 "state": "pending_recheck|watch|waiting_evidence|conditions_met|invalidated|historical",
 "why": "一两句，可核对", "trigger": "触发条件（可观测）", "invalid": "失效条件（可观测）",
 "trigger_happened": "是|否|部分|U", "trigger_evidence": "链接",
 "eligibility": "谁能参与（资格 / 地区 / 门槛）", "cost": "参与成本（费用、滑点、gas、锁定期）", "exit": "退出路径和限制（赎回周期、深度）",
 "facts": [{"claim": "…", "src": "…", "kind": "official|onchain|third_party", "checked_utc": "…", "same_as_handoff": true}],
 "reviewed_utc": "…", "next_review": "…"}
```

不写「建议买入 / 卖出」；「条件齐备」只表示列出的触发条件都出现了。

## R3 案例补证 → `rwa/review/cases_YYYYMMDD.json`

`rwa/research/watchlist.json` 里 5 个案例的 `open_questions` 逐条回答（同样带来源和时间）。特别注意：

- **KYTE**：只读卖出报价要写区块高度、报价规模、gas 假设、报价时刻；池 ID 和平台币合约分开。
- **Xash**：营销补贴、可提现收益、积分预期分开算；「无平台币」要原文。
- **BUIDL × Ethena**：设施规模原文、实际使用量、使用资格、ENA 持有人是否受益——四件事分开。
- **RWA.xyz 快照下降**：只给同期可比的单项余额，不推断赎回原因。
- **TownSquare**：储备证明、借贷 TVL、TOWN 治理 / 收入权分开。

## R4 数据源条款 → `rwa/review/sources_terms.json`

```json
{"source": "rwa.xyz", "endpoint": "…", "auth": "none|free_key|paid", "price": "…", "terms_url": "…",
 "redistribution": "允许|需署名|不允许|U", "fields": ["…"], "history_depth": "…", "checked_utc": "…", "notes": "…"}
```

至少覆盖：rwa.xyz、DefiLlama RWA 看板（defillama.com/rwa 背后的接口）、CoinGecko（免费层条款）、Dune 公开查询、各发行方官方 NAV / AUM 披露页（BlackRock BUIDL、Ondo、Franklin BENJI、Superstate、Circle USYC）。

## R5 自动化迁移说明 → `rwa/review/automation.md`

写清：旧 Codex 巡检任务现在的触发方式、读写路径、是否已停；`build_universe.py` 的输入输出和整文件覆盖行为；以后本地研究库怎么把新结果交给仓库（只交 R1–R3 格式的文件）。

## 第二轮（2026-11-14 第一轮审查后）

第一轮审查结论见 `rwa/research/研究进度.md`「Codex 第一轮交付审查」。R1 已由 Claude 纠错导入，**不用重交**。下面这些要补：

1. **R2 / R3 必须真的打开原始来源核对。** 每个事实条目一个来源、一个独立的核对时间（打开那一页的时刻），不同条目不能共用同一个时间戳，也不能把同一句话配三个来源。查完还是不知道的才写 U，并写明查了哪里、为什么不知道。
2. R2 先做 Maple、Pendle 两项（有公开数据）：10-30 记录的回购强度 2.15%、持有人收入年化 1.37%，按原始来源重算，写清期间、分子、分母、年化方法；10 月收入 / 回购是否按 MIP-021 执行。
3. R3 先做 BUIDL × Ethena（新闻稿里的设施规模原文、实际使用量、使用资格、ENA 持有人是否受益）和 Xash（「无平台币」条款原文和日期、Phase B 前奖励能否提取）。
4. R4 每个源要给条款页链接和原文摘录（再分发 / 商用的那一段），不能只写 U。
5. 资格、成本、退出这三栏：至少写「需 KYC / 仅合格投资者 / 地区限制」这一级，有官方文档的附链接。
6. 交付时自查：同一时间戳出现超过 3 次、同一句 claim 出现超过 1 次，就是没核对完。
