# 全站待办与检查（2026-11-20 09:25 UTC 自动生成，别手改）

| 板块 | 待办 | 问题 |
|---|---|---|
| Alpha 雷达 | 16 | 2 |
| 发射台 | 3 | 0 |
| AI Agent | 7 | 0 |
| RWA | 0 | 0 |
| 龙头选币 | 2 | 0 |
| 事件日历 | 0 | 0 |
| 聪明钱 | 1 | 0 |
| 全站数据状态 | 0 | 0 |

## 待办

- **P1 · Codex · alpha** 机会卡补证（队列 39 个，从上往下补，M 新参与机制优先查） → `alpha/review/codex_2026-11-20_checks.json（JSON 数组，reviewer = codex）`（参考 `data/alpha/research_queue.json（prompt / schema / items）`）
- **P1 · Codex · alpha** 补「量从哪来」和关键事件（35 张已补证的卡还没有 flow / events，先做 Montra、Pons 当样板） → `alpha/review/codex_2026-11-20_checks.json（同 key 交新一条，带 flow / events / capture / next_review）`（参考 `data/alpha/research_queue.json 的 schema`）
- **P2 · Codex · aiagent** A1 服务层真实性 → `aiagent/review/a1_commerce_checks.json`（参考 `aiagent/review/README.md`）
- **P2 · Codex · aiagent** A2 x402 与 ERC-8004 的链上数据源 → `aiagent/review/a2_rails_sources.json`（参考 `aiagent/review/README.md`）
- **P2 · Codex · aiagent** A3 Virtuals ACP 逐日服务收入 → `aiagent/review/a3_acp_revenue.json`（参考 `aiagent/review/README.md`）
- **P2 · Codex · aiagent** A4 非 BNB 发射台的使用量 → `aiagent/review/a4_launch_usage.json`（参考 `aiagent/review/README.md`）
- **P2 · Codex · aiagent** A5 时间线与 C 级证据升级 → `aiagent/review/a5_timeline.json`（参考 `aiagent/review/README.md`）
- **P2 · Codex · aiagent** A6 框架与开发者清单 → `aiagent/review/a6_frameworks.json`（参考 `aiagent/review/README.md`）
- **P2 · Codex · alpha** 关键人名单核对（S2） → `alpha/review/sources_people.json`（参考 `alpha/review/sources_task.md`）
- **P2 · Codex · alpha** X4 上市事件样本库（过去 12 个月，≥100 条） → `alpha/review/x4_listing_events.json`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M1 技术与开发者雷达来源 → `alpha/review/m1_dev_sources.json`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M2 链上创世动作字段 → `alpha/review/m2_genesis_fields.md`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M3 卡片决策条件与证据分类字段 → `alpha/review/m3_card_schema.md`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M4 代币研究七项数据来源 → `alpha/review/m4_token_seven.json`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M5 监控六个观察面的数据源 → `alpha/review/m5_monitor_sources.md`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M6 社交渠道与钱包标签边界 → `alpha/review/m6_social_wallet.md`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M7 价格路径与收益口径样例 → `alpha/review/m7_return_examples.md`（参考 `alpha/review/README.md`）
- **P2 · Codex · alpha** M8 历史对照组候选 → `alpha/review/m8_control_candidates.json`（参考 `alpha/review/README.md`）
- **P2 · Codex · launchpad** 关键事件登记（近 7 天手续费前 25 的平台里 25 家还没有） → `config/launchpad_events.json（每条 日期 / 事 / 出处，必须官方出处）`（参考 `docs/接口_发射台给Alpha.md`）
- **P3 · Codex · aiagent** 监控地图待核事项（6 条） → `aiagent/aiagent_registry.json`
- **P3 · Codex · alpha** CMC 页面地址核对登记（10 个币） → `alpha/cmc_slugs.json`（参考 `AGENTS.md 第 4 节 3b`）
- **P3 · Codex · alpha** 历史案例峰值日流通量登记（21 个，估值改流通口径用） → `alpha/cases.json 每个 tokens[] 加 circ_peak {数量, 日期, 出处}`（参考 `alpha/review/fable_findings_20261115.md 第 12 条`）
- **P3 · Codex · alpha** 补失败样本 / 同期对照组（现在 3 个，目标 ≥ 10） → `alpha/review/cases_control_<日期>.json（格式同 alpha/cases.json 的 cases[]，带 why_control 和出处）`（参考 `alpha/cases.json`）
- **P3 · Codex · alpha** 英文稿（4 篇研究文档；英文站现在只有导航是英文） → `alpha/research/<同名>.en.md（Claude 接进网站）`
- **P3 · Codex · core** 六问卡草稿（30 个币没有核对过的卡；Codex 出草稿，大叔核对后才进 cards） → `core/review/cards_draft_<日期>.json（键同 core_config.json 的 _cards_说明，每栏带出处）`（参考 `core/core_config.json _cards_说明`）
- **P3 · Codex · launchpad** 平台介绍（前 25 里 1 家没有） → `按 pipeline/导入平台介绍.py 的格式`
- **P3 · 大叔 · core** 核对六问卡草稿（只有大叔核对过的才算，R1 要七栏齐）（参考 `core/review/cards_draft_*.json`）
- **P3 · Claude · launchpad** 平台质量待接入字段：交易者、发币人（参考 `docs/接口_发射台给Alpha.md 字段优先级 4（进度见文末）`）
- **P3 · 大叔 · smartmoney** 聪明钱：等立项书定稿（主体 / 证据等级 / 入选规则写死后才开 S1）（参考 `smartmoney/research/立项书.md`）

## alpha 补证状态（已覆盖 ≠ 已查证）

| 已查证 | 已处理但证据不足 | 缺来源 | 字段格式错误 | 已过期需重核 | 已交条目 | 其中Grok未经Codex复核 |
|---|---|---|---|---|---|---|
| 10 | 28 | 0 | 0 | 0 | 38 | 0 |

## 检查出的问题

- [warn] Codex · `alpha/review/codex_2026-11-15_checks.json` · x:launchpad:chain-elysium：没有任何证据链接
- [warn] Codex · `alpha/review/codex_*_checks.json`：35 条是空模板（分数全 U、最多 1 条证据、一句话是模板句）：没有并入、不算补证完成，这些 key 仍在待补证队列里。查不到就不要交，交就要有一手证据
