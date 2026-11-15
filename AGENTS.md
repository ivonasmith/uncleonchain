# AGENTS.md · 给 Codex（和其它代理）的协作说明

链上大叔研究台（uncleonchain.com）。仓库主人是「大叔」，只给方向。**Claude 是网站和代码的操盘手；Codex 负责查证、出数据、复核**，
两边都直接连 GitHub 干活。项目全貌、每个板块的规则在 `CLAUDE.md`，开工前先读它和 `docs/SEO规范.md`（改页面才需要）。

## 1. 分工

| 谁 | 做什么 | 改哪些文件 |
|---|---|---|
| Codex | 查证、补证、找数据源、核对数字、复核代码和口径、写研究文档 | 各板块的 `*/review/`（结果 JSON / md）、`*/research/`（研究文档）、人工登记文件（见第 3 节） |
| Claude | 网站、管线代码、工作流、把 Codex 的结果并进网站 | `pipeline/`、`*/web/`、`*/*.py`、`.github/`、`site/`、`config/`、`content/changelog.json`、`CLAUDE.md` |

Codex 发现代码有错：写进 `*/review/` 的复核文件（`文件:行号 · 问题 · 建议改法`），或开 PR 并在描述里写清楚；**不要直接改别人正在用的管线代码再推 main**。

## 2. 怎么提交

- 只动第 1 节「Codex」那一行的文件时：可以直接推 `main`（提交前 `git pull --rebase origin main`，冲突以远端为准，别 force push）。
- 要改代码、工作流、页面：开分支 `codex/<主题>`，发 PR，描述写「改了什么、为什么、怎么验证的」，等 Claude 或大叔合并。
- 不要提交 `site/`、`data/` 下的生成文件（日更会重出），也不要提交缓存（`*/cache/`、`leg/leg_alt_cache.csv`）。
- 提交信息用中文，第一行说清做了什么。
- 所有定时工作流共用 concurrency 组 `daily-pipeline`，手动触发一次只排一个，别连续触发。

## 3. 数据规矩（所有人都要守）

- 每条事实带来源链接和核对日期（UTC）。查不到写 `"U"`，说法冲突写「说法不一」并给两边链接。**不估、不编、不拿近似值冒充。**
- 一手证据 = 官网、官方文档、官方 X、合约 / 链上浏览器、DefiLlama 方法论；媒体、聚合站、别人的帖子是二手。拒绝 / 否定性结论必须有一手证据。
- 不写买入、卖出、仓位、止损、目标价，不写「值得关注 / 有潜力」。网站只给数据和过程记录。
- 写入即冻结的文件不回改：`*_history.json`、`data/解读日志/`、`aiagent/research/launchpad_cards_v2.json`、已交的 `*_checks.json`（要更正就交新批次）。
- 仓库是公开的：不要放 key、凭据、私群原文、个人信息。
- 人工登记文件（Codex 可以直接改，改完在提交信息里写出处）：`alpha/manual_leads.json`（新线索）、`alpha/sources.json`（来源台账）、
  `core/core_config.json`（观测池登记）、`aiagent/aiagent_registry.json`（生命周期事件）、`cal/reg_events.json`（立法表决）。

## 4. 现在可以接的任务

按优先级。做完在对应 README 里把状态改成「已交回」，结果文件放在写明的位置。

1. **Alpha · 关键人名单**：`alpha/review/sources_task.md`（S2：核对 Grok 列的 X 原帖 → `alpha/review/sources_people.json`；S1 Grok 的原始回答大叔会放进 `alpha/review/`）。
2. **Alpha · 复核 Grok 自动补证**：每天日更会写 `alpha/review/grok_<日期>_checks.json`（便宜模型，结论偏乐观）。逐条打开 evidence 核对，
   交 `alpha/review/codex_<日期>_checks.json`（同一格式，reviewer = codex；后交的覆盖先交的）。优先核「研究观察」和带 ★（本站板块 / 手动线索）的卡。
   队列和格式：`data/alpha/research_queue.json`（prompt、schema、items）。
3. **Alpha · 补证队列**：同上格式，直接从 `research_queue.json` 前面往后补，Grok 每天只补 1 个左右。
4. **Alpha · T4 / T5**：`alpha/review/README.md`（待核验的补缺口、Bybit / Upbit 替代源）。
5. **AI Agent · A1–A6**：`aiagent/review/README.md`。
6. **核心选币 · 评分复核与 M3**：`core/review/README.md`、`core/review/M3_分工.md`。
7. **Alpha · 复核结果里还没处理的**：`alpha/review/fable_findings_20261115.md`（估值改流通口径要在 `alpha/cases.json` 手工登记峰值日流通量，每条带来源）。

## 5. 交接

- 每次交回在提交信息或 PR 里写：做了哪些、哪些没做完、哪些查不到。
- 需要 Claude 改代码配合的，写进 `docs/协作记录.md`（只追加，一行一条：日期 · 谁 · 要什么 · 状态）。
