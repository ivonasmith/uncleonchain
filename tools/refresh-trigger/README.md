# 总调度准点触发器（Cloudflare Worker）

GitHub Actions 自带的定时（schedule）实测每天晚 6～10 小时。这个 Worker 只做一件事：到点调一次
`refresh.yml` 的 workflow_dispatch（手动触发几秒内就开跑）。计算、密钥、缓存、提交、网站部署全部还在 GitHub 上，不用搬。

| 档 | UTC | 新加坡 | 做什么 |
|---|---|---|---|
| am | 00:05 | 08:05 | 全部板块跑一遍（Coin Metrics / DefiLlama 多半还没出昨天的数，L2 / L3 沿用上一天） |
| pm | 08:30 | 16:30 | 完整版，交易用的数据应在 17:15 前后到齐 |
| retry | 09:50 | 17:50 | 交易用的数据还没到昨天才真跑，否则几秒就结束 |

Worker 没叫到时，`refresh.yml` 自己的 schedule 兜底（会晚几个小时，但不会漏）。重复叫不会重复跑：guard 看 `data/refresh_status.json`。

## 一次性设置（约 10 分钟，只在网页上点）

1. **GitHub 令牌**：github.com → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
   - Repository access：Only select repositories → `ivonasmith/uncleonchain`
   - Permissions → Repository permissions → **Actions: Read and write**（其他都不用给）
   - 有效期选最长（1 年），到期前 GitHub 会发邮件；到期后换一个填回第 3 步
2. **建 Worker**：Cloudflare 控制台 → Workers & Pages → Create → Create Worker → 名字 `uncleonchain-refresh` → Deploy →
   Edit code，把本目录 `worker.js` 全部内容粘进去 → Deploy
3. **存令牌**：这个 Worker → Settings → Variables and Secrets → Add → 类型 **Secret**，名字 `GH_TOKEN`，值 = 第 1 步的令牌
4. **定时**：Settings → Trigger Events（或 Triggers → Cron Triggers）→ 加三条：`5 0 * * *`、`30 8 * * *`、`50 9 * * *`
5. 验证：Worker 页面 → 定时那里可以点 **Trigger / Test** 手动触发一次 → 去 GitHub 仓库 Actions 页看到「总调度：一天两档全量更新」开跑就成了

用命令行也行：在本目录 `npx wrangler deploy`，再 `npx wrangler secret put GH_TOKEN`（wrangler.toml 里已写好 crons）。

## 交易程序怎么取数（新加坡 19:00）

先读 `https://uncleonchain.com/data/status.json`：

- `ready_for_trading: true` → 照常取数
- `false` → `not_ready` 列出哪些模块还没到 `expected_data_date`（= UTC 昨天）；建议每 5 分钟重读一次，最晚 19:40 还没齐就照常出，但在计划里注明哪块是旧数据
- `modules.<名>.data_date` 是每块数据截至哪个 UTC 完整日；`generated_utc` 是这一档跑完的时间

交易用的模块（`trading: true`）：L2、L3、L4、涨跌腿、宏观 L1 + 解读日志、事件日历。

## 备用：用自己的服务器再叫一次（可选）

交易服务器本来就稳定，可以在它的 crontab 里加一条同样的叫醒，和 Cloudflare 互为备份（同一档叫两次只跑一次）：

```
35 8 * * * curl -fsS -X POST -H "Authorization: Bearer <GH_TOKEN>" -H "Accept: application/vnd.github+json" https://api.github.com/repos/ivonasmith/uncleonchain/actions/workflows/refresh.yml/dispatches -d '{"ref":"main","inputs":{"slot":"pm"}}'
```

（服务器时区不是 UTC 的话换算钟点。）
