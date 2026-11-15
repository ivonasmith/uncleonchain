# 给 Codex 的定时任务提示词（复制整段到 Codex 的定时任务里）

建议频率：每天两次，新加坡时间 10:00 和 18:00。

---

你在 GitHub 仓库 ivonasmith/uncleonchain 协作（链上大叔研究台）。
1. git pull origin main。先读根目录 AGENTS.md（分工、提交方式、数据规矩），再读 data/check_report.json 和 data/tasks.json。
2. 先修 check_report.json 里 who = codex 的问题：改你之前交的文件；已交的 *_checks.json 不回改，交新批次覆盖同一个 key。
3. 再按 tasks.json 从上往下做 who = codex 的条目，交到每条写的 deliver 位置，格式看 ref。P1 每次都要推进，P2 / P3 有余力再做。
   Alpha 补证：按 data/alpha/research_queue.json 的 prompt 和 schema，M（新参与机制）优先查；可以加 events（关键事件，日期 + 官方出处）、
   flow（流量来源：积分空投 / 新链首发 / 补贴 / 自然需求，各写 高 / 中 / 低 / 待验证 + 证据）、next_review（下次复核日）。
4. 规矩：每条事实带链接和核对日期（UTC），查不到写 "U"，不估不编；拒绝要一手证据；不写买卖 / 仓位 / 止损；不提交 site/ 和 data/ 下的生成文件；仓库公开，不放 key。
5. 只改 AGENTS.md 第 1 节 Codex 那一行的文件时直接推 main（推之前 git pull --rebase origin main，冲突以远端为准）；要改代码就开 codex/<主题> 分支发 PR。
6. 最后在 docs/协作记录.md 末尾追加一行：日期 · Codex · 做了哪些 / 没做完的 / 查不到的。

---

## 我们怎么协作（一句话版）

- GitHub 每天自动生成两份清单：`data/tasks.json`（要补什么）和 `data/check_report.json`（已交的哪里不合格）。
- Codex 按清单查资料、补证据，交到 `*/review/` 下的文件，推到 main。
- 推上去几分钟内自动检查，Alpha 的结果马上进网站，其它板块等下一次总调度。
- 需要改代码、改页面的事，Codex 写进 `docs/协作记录.md`，Claude 每周一处理。
- 需要大叔拍板的事（比如六问卡、聪明钱立项书），两边都不替你定。
