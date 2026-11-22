# 交接：Claude 新会话（2026-11-16 起，复制下面整段给新会话）

---

你接手 uncleonchain 仓库（链上大叔研究台）。先读根目录 `CLAUDE.md`（项目说明，必须遵守）、`AGENTS.md`（和 Codex 的分工），再读 `docs/协作记录.md` 最后 10 行。不用重读别的，需要时再查。

## 这周的工作方式（大叔定）

- Claude 额度紧：**查证、找数据源、出数据交 Codex / Grok**，Claude 只做代码、页面、审核和并入。能交给 Codex 的不要自己查。
- **Codex 一律推分支 `codex/review`**，你审核后再并进 main：`git fetch origin codex/review`，看 diff、跑 `python3 pipeline/任务清单.py --print | tail -40` 看检查结果，没问题就合并推 main；有问题写进 `docs/协作记录.md`（一行一条：日期 · Claude → Codex · 问题 · 待改）。补证合并规则在 `alpha/checks_util.py`（空模板不并入，按核对时间新盖旧，更正用 `alpha/review/patches.json`）。
- **页面改动先做本地稿，截图发给大叔，他点头再推**（11-16 他明确说过：没定下来不要推）。后台数据 / 程序可以直接推。
- 用中文，简短，不写买卖建议（`docs/表达规范.md`）。

## 当前在做：Alpha 雷达的「交易所上币」线（大叔要求必须做完）

已完成（都在 main）：
- Binance 完整事件库：`alpha/listings.py` → `data/alpha/listings.json`。公告 / 修订 / 计划开盘 / 首笔成交分字段，窗口 30m / 1h / 4h / 24h。12 个月 114 个事件、107 个有窗口。没算出的 7 个：今天开盘的 HYPEUSDC、TRXUSDC 永续（归档明天才有，日更会自动补）；PREDICT 现货（公开 K 线接口查不到这个交易对）；牛来、龙虾等中文代码和 GAIB 合约（原因未查）。另有 5 篇 HODLer 空投公告、1 篇多合约公告没解析出交易对。
- 其它所公告流水：`alpha/exch_announce.py` → `data/alpha/exch_announce.json`，来源台账 `alpha/exch_sources.json`（10 家）。OKX / Bitget / Kraken 已接；Bybit / Coinbase / Upbit / Bithumb / Gate / MEXC 在 Actions 被拦，计划走官方 X 账号（`X_BEARER_TOKEN` 已验通，X 接口按次付费，大叔同意试用、上限约 10 美元 / 月，开之前先报调用量）。
- 两个都在 `alpha/alpha_daily.py` 末尾调用；探测工作流 `probe-exchanges.yml`（手动）。

等别人交的：
- Codex / Grok 按 `docs/提示词_交易所公告源.md` 交 `alpha/review/x1_exchange_sources.json`（被拦 6 家的官方 X 用户名、替代入口、K 线接口）。到了以后：核对 → 把 X 用户 ID 填进 `alpha/exch_sources.json`（`x_user_id`，可用 `/2/users/by/username/<名>` 查）→ 改 state = on。

你接下来要做的（按顺序）：
1. 审核 Codex 在 `codex/review` 的提交并并入。
2. x1 到了就开被拦的所（上面那步）。
3. OKX / Bitget / Kraken 的正文解析（计划开盘时间、交易对）和 K 线窗口，并进 `listings.json`（OKX、Bitget 的公开 K 线接口在 Actions 实测能通）。
4. 页面：在 Alpha 雷达加「交易所上币」一块（公告 → 开盘 → 首笔 → 窗口，各所来源状态），做本地稿截图给大叔看，他点头再推。

## 待大叔定的

- 交易所名单要不要增减（KuCoin、HTX 官网接口也通，没接）。
- 第 6 条：新的筛选框架（创新层 → 有用 vs 炒作 → 资金持续 → 解锁砸盘 → 团队评分），大叔说要再深度想，别先做。
- 第 7 条：P / L 两个维度公开还是私有，待定。

## 小坑

- 本地出网站：`LP_DATA=$PWD/data LP_OUT=$PWD/build python3 pipeline/出网站.py`，提交前 `git checkout -- site/data/launchpad`；站点输出在 `site/`。
- 本地沙盒连不上大部分交易所域名（代理 403），要在 Actions 上试（`probe-exchanges.yml` 可改了手动跑）。
- 推送前 `git pull --rebase -X theirs origin main`；不要 git stash。

---
