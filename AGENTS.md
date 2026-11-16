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

## 4. 每天做什么（全站一套，大叔 11-15 定：一边一个定时任务）

**不要再看零散的任务包找活干**。全站待办和检查每天由总调度自动生成（新加坡 08:05、16:30 两档，Alpha 补证推上去后也会马上重算）：

| 文件 | 是什么 |
|---|---|
| `data/check_report.json` | 已交文件的机器检查结果：`who = codex` 的是你交的东西有问题（格式、分数超范围、缺来源、拒绝没证据……），**先改这些** |
| `data/tasks.json` | 全站待办，已按优先级排好（P1 今天、P2 本周、P3 有空）。每条写了 谁做（`who`）、交到哪（`deliver`）、参考哪（`ref`）、具体清单（`items`） |
| `data/tasks.md` | 上面两份的人读版 |

推送补证 / 登记文件后，工作流「补证检查」几分钟内重算这两份（只改这三个文件，不出网站、不触发日更）；Alpha 的结果同时由 alpha-daily 并进网站，其它板块等下一档总调度。
`check_report.json` 的 `summary` 把补证分成 已查证 / 已处理但证据不足 / 缺来源 / 字段格式错误 / 已过期需重核——**写进文件不等于查证完成**，「证据不足」的下一轮继续补。
`tasks.json` 的 `queue` 是逐条待办（key、priority、task_type、missing、status、last_checked_utc），做的时候按它走。
**先把 Alpha 跑稳一周**（每天都能交、检查报告没有 error），再按 发射台 / AI Agent → 龙头选币 / RWA / 日历 的顺序加量。

### Codex 定时任务的提示词（复制到 Codex 的定时任务里，建议每天新加坡 10:00 和 18:00 各一次）

```
你在 GitHub 仓库 ivonasmith/uncleonchain 协作（链上大叔研究台）。
1. git pull origin main。先读根目录 AGENTS.md（分工、提交方式、数据规矩），再读 data/check_report.json 和 data/tasks.json。
2. 先修 check_report.json 里 who = codex 的问题：改你之前交的文件；已交的 *_checks.json 不回改，交新批次覆盖同一个 key。
3. 再按 tasks.json 从上往下做 who = codex 的条目，交到每条写的 deliver 位置，格式看 ref。P1 每次都要推进，P2 / P3 有余力再做。
   Alpha 补证：按 data/alpha/research_queue.json 的 prompt 和 schema，M（新参与机制）优先查；可以加 events（关键事件，日期 + 官方出处）、
   flow（流量来源：积分空投 / 新链首发 / 补贴 / 自然需求，各写 高 / 中 / 低 / 待验证 + 证据）、next_review（下次复核日）。
   查不到的不要交空模板（分数全 U、证据 ≤ 1 条的不会并入，11-15 首批 41 条里 35 条是这样）；每条至少有一条一手证据链接；
   写数字趋势要写具体数和时间段并带链接（如「9 月 $1.32 亿 → 10 月 $1,623 万」），不写「降到百万级」这类概括。
4. 规矩：每条事实带链接和核对日期（UTC），查不到写 "U"，不估不编；拒绝要一手证据；不写买卖 / 仓位 / 止损；不提交 site/ 和 data/ 下的生成文件；仓库公开，不放 key。
5. 只改 AGENTS.md 第 1 节 Codex 那一行的文件时直接推 main（推之前 git pull --rebase origin main，冲突以远端为准）；要改代码就开 codex/<主题> 分支发 PR。
6. 最后在 docs/协作记录.md 末尾追加一行：日期 · Codex · 做了哪些 / 没做完的 / 查不到的。
```

### 谁做什么
- `who = codex`：你。
- `who = claude`：要改代码、接新数据源的，攒着由 Claude 每周处理；你发现需要 Claude 配合的，在 `docs/协作记录.md` 写一行。
- `who = 大叔`：要大叔拍板或核对的（比如六问卡、聪明钱立项书），不要替他定。

### 新板块接入
在 `pipeline/任务清单.py` 的 `BOARDS` 里加一个函数，返回（待办，问题）。任务包 README 里写成 `## 标题 → \`交付文件\`` 的条目会自动进待办，交付文件出现就算做完。

## 5. 交接

- 每次交回在提交信息或 PR 里写：做了哪些、哪些没做完、哪些查不到。
- 需要 Claude 改代码配合的，写进 `docs/协作记录.md`（只追加，一行一条：日期 · 谁 · 要什么 · 状态）。
