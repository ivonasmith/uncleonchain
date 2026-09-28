> **这份文件是 Claude 会话侧的运行手册**：看板发到 claude.ai Artifact + Notion 固定页 + 聊天推送，靠人（Claude
> 定时任务）每天跑一遍下面的步骤。它和对外网站 uncleonchain.com 是两条独立的产出线，互不依赖：
> 网站由 `.github/workflows/daily.yml` 每天自动跑 `pipeline/跑日更.py --site`，读同一批脚本、写到本仓库的
> `data/` 和 `site/` 并自动提交，不需要人工操作，也不读这份 RUNBOOK 的步骤。仓库总览见根目录 `README.md`；
> 手写文章（宏观 / 板块轮动 / 叙事币埋伏三个板块）的发布方法见 `content/posts/README.md`。

# 发射台日更看板 · 运行手册（Claude 版）

每天跟踪 pump.fun、Pons（V1+V2）、StonkFun、Flap 四家发射台的手续费与收入，PONS 链上回购销毁，PUMP / PONS / STONK 回购市盈率，以及 Arc 链整链热度（对标 Robinhood Chain）。
产出：看板网页（claude.ai Artifact，固定地址，每天原地更新）+ Notion 固定页追加行并换嵌入块 + 当日 CSV + 聊天里主动推送近 7 天数值。
**给数字，不给买卖建议。**

2026-09-26 从 Polar 迁移过来。相对 Polar 版的变化：新增 StonkFun 与 Arc 链；PONS 逐日销毁改为按 UTC 日界切的链上余额差（不再需要手动补 `销毁逐日.json`）；延迟的数据源标「延迟」而不是记 0；DefiLlama 事后修订会自动追加「（修正）」行；台账随看板一起发布到 Artifact 实现跨会话持久化。

## 固定地址

| 用途 | 地址 |
|---|---|
| 看板 Artifact（台账和工具包也存在这里） | https://claude.ai/artifact/V7jsta2RNccHojBNKY5HkF |
| Notion 固定页（永远更新这一页，⛔ 不要新建） | https://app.notion.com/p/Launchpad-Daily-Tracker-2026-3ccb72fc8cae80f39f86c434f7850bc0 |
| Notion 备份资料库 | https://app.notion.com/p/Backup-Library-3cbb72fc8cae80db8330d6eb4b976ff0 |
| Claude Project「链上发射台数据分析」 | `launchpad-daily/` 目录：RUNBOOK 与每周台账备份 |

跑的时间：北京时间 19:00 前交付（定时任务 18:52 启动）。用户北京时间 20:00 发推特，必须提前一小时交付，留出看数和改文案的时间。

## ⛔ 硬口径（写死，不要改）

1. **全部用手续费（fees）口径，不用成交量口径。** DefiLlama 对发射台类目的 volume 覆盖不全，而且会把共享基础设施的成交量算给基础设施而不是品牌，用 volume 做份额会系统性低估 Solana。
2. **只报「昨天（UTC）」的完整日。** DefiLlama 当天那根永远不完整，脚本已剔除。某家没出数就标「延迟」，⛔ 绝不把半截数据当成「今天大跌」报出去，⛔ 不拿旧值冒充新值。
3. **Flap 必须单独看，不能和另外几家比大小。** 税代币模型，费用来自代币转账税。链上 `TaxProcessor.feeConfig()` 实测四个代币 `feeRate` 全部 = 1000 bps：税收 10% 归协议、90% 按 `marketBps / deflationBps / lpBps / dividendBps` 分给项目方钱包 / 销毁 / 加池 / 持币分红。DefiLlama 2026-08-31 改了 flap-sh 算法，fees 曲线在 08-31 有人为断点。
4. **绝不拿峰值比现在就说某个平台失败。** 先看份额（分母 = 赛道 Top60 当日总量），份额掉到接近零才是真死亡；绝对额跌但份额稳，是周期。
5. **（新）StonkFun 跨平台比较只用协议收入（revenue）口径。** DefiLlama 对 stonkfun 的 fees 只记平台自己那份，fees = revenue，分账比率恒为 100%；pump.fun 的 fees 含创作者费。用 fees 并排比会系统性低估 StonkFun。
6. **市值一律 burn-adjusted 流通市值。** ⛔ 不用 `totalSupply`，⛔ 不用 FDV。PONS 的 `totalSupply()` 恒为 10 亿，按它算会高估约 41%（29% 是已销毁占总量的比例，两个数别写混）。
7. **推算成交额（手续费 ÷ 费率）不做日频**，那是月度工作流（`/launchpad-monthly`）的事。pump.fun 自 2026-09-01 起按市值分档动态收费，日频推算等于每天用一个错的费率相乘。
8. **「pump.fun 手续费」不含 PumpSwap。** DefiLlama 拆成 `pump.fun`、`pumpswap`、`pump.fun-mobile-app` 三条，PumpSwap 30 天手续费比主站还大。两期之间不许换口径。

## 步骤

工作目录一律用 `/home/claude/lp/工具`（下称「工具目录」）。每次都是全新沙盒，先还原。

### 0 · 还原工具与台账

1. `Artifact` action=read，url=https://claude.ai/artifact/V7jsta2RNccHojBNKY5HkF（先读一次，后面才能原地更新）。
2. `Artifact` action=read，同一 url，`paths` = `["tools/launchpad_tools.py.txt","data/valuation.json","data/burn_daily.json","data/burn_cum.json","data/burn_ledger.json","data/burn_fixes.json","data/published.json"]`，**不传 out_dir**（用默认目录，不需要审批）。结果会说明文件落在哪个目录，记为 X。
3. `mkdir -p /home/claude/lp/工具 && python3 X/tools/launchpad_tools.py.txt /home/claude/lp/工具`
   —— 解压全部脚本，并把 `X/data/*.json` 按中文文件名放回工具目录。
4. 如果 Artifact 读不到：用 `Projects` project_read 读 `launchpad-daily/工具包_含台账.py.txt`（周日备份，最多旧 7 天），同样 `python3 <文件> /home/claude/lp/工具`。两处都没有时，脚本也能从零跑（销毁从链上重算，估值从数据源窗口重算），只是 PUMP 超过 365 天的历史会缺。

### 1 · 一键跑

```
cd /home/claude/lp/工具 && python3 跑日更.py
```

顺序：网络预检 → 拉日度 → 读销毁 → 拉估值 → 拉Arc → 出看板 → 打包，约 1–3 分钟。

- 退出码 2 = DefiLlama 被网络策略拦截：⛔ 不要换别的方法去抓（不要用 WebFetch 顶替数据源），直接在聊天里告诉用户被拦的域名清单，本期停止。
- 退出码 3 = 拉日度失败：重跑一次；还失败就报告，本期停止。
- 其余步骤失败不会拦截，看板上会标出缺哪块（例如「PONS 当日销毁未读到」）。
- 需要重算一段 PONS 销毁历史时：`python3 跑日更.py --rebuild-from YYYY-MM-DD`（和旧值不一致的写进 `销毁修正记录.json`，看板第四节会列出来）。

产出都在 `工具目录/输出/`：`看板页.html`（发 Artifact）、`发射台日更看板.html`（完整文档，给 Notion）、`发射台日更-<日期>.csv`、`摘要.md`、`notion_payload.json`、`发布/`（台账与工具包暂存）。

### 2 · 发布看板（原地更新同一个 Artifact）

`Artifact` publish：`url`=https://claude.ai/artifact/V7jsta2RNccHojBNKY5HkF，`file_path`=`/home/claude/lp/工具/输出/看板页.html`，不传 icon，`files` =

```
{"tools/launchpad_tools.py.txt": "/home/claude/lp/工具/输出/发布/tools/launchpad_tools.py.txt",
 "tools/RUNBOOK.md": "/home/claude/lp/工具/输出/发布/tools/RUNBOOK.md",
 "data/valuation.json": "/home/claude/lp/工具/输出/发布/data/valuation.json",
 "data/burn_daily.json": "/home/claude/lp/工具/输出/发布/data/burn_daily.json",
 "data/burn_cum.json": "/home/claude/lp/工具/输出/发布/data/burn_cum.json",
 "data/burn_ledger.json": "/home/claude/lp/工具/输出/发布/data/burn_ledger.json",
 "data/burn_fixes.json": "/home/claude/lp/工具/输出/发布/data/burn_fixes.json",
 "data/published.json": "/home/claude/lp/工具/输出/发布/data/published.json"}
```

⚠️ 台账必须随看板一起发布，否则下一天读不到今天的状态（估值序列超过 365 天的部分、Notion 已发布到哪天，都靠它）。这一步漏了，整条链就断了。

### 3 · 更新 Notion 固定页

页面结构固定：标题 → 副标题 → HTML 看板嵌入块 → 说明文字 → 表一 → 表二 → 表三 → 表四（StonkFun）→ 表五（Arc 链）→ 缺口 → 署名。

1. `notion-fetch` 固定页，看清五张表各自最后一行的日期，和 `notion_payload.json` 里 `已发布基准` 对一下。对不上时以 Notion 为准：`python3 标记已发布.py --set 表一=YYYY-MM-DD ...` 后重跑 `python3 出看板.py`。
2. **换嵌入块里的文件（不是删了重传）**：
   - `notion-create-file-upload` filename=`发射台日更看板.html` → 拿到 `upload_url` 与 headers；
   - 沙盒里 `curl -sS -X POST "<upload_url>" -H "authorization: <header 值>" -F "file=@/home/claude/lp/工具/输出/发射台日更看板.html;type=text/html"`，返回的 JSON 里有 `markdown_source`；
   - curl 被网络拦截时，改用 `notion-create-attachment`，`filename`=`发射台日更看板.html`，`content`=文件全文（文件须小于 200 KiB，脚本会打印大小）；
   - `notion-update-page` command=`update_content`：old_str = 页面里现有的那个完整 `<embed src="file://…"></embed>`，new_str = 用上一步返回的 `markdown_source` 组成的 `<embed src="…"></embed>`（形如 `file-upload://<id>`）。原地换，位置不动。
3. **追加行，⛔ 不动历史行、不新建页**：`notion_payload.json` → `表.<表名>.行` 是排好格式的 `<tr>…</tr>`。对每张有新行的表，用 `update_content`：old_str = 该表的 `</table>` 加上紧跟其后那段文字的开头（从 fetch 结果里原样复制，保证唯一），new_str = 新行 + 同一段 old_str。当前页面上的锚点：
   - 表一：`</table>\n表二 · PONS 回购与销毁`
   - 表二：`</table>\n销毁是把币转到`
   - 表三：`</table>` 后面紧跟「三条口径警告」那一段
   - 表四 / 表五：若页面上还没有，先在 `---\n已知缺口` 之前插入：一行标题 `表四 · StonkFun 日度（2026-09-26 新增）` + `新表模板.表四`，再一行 `表五 · Arc 链日度（2026-09-26 新增）` + `新表模板.表五`（模板已含表头和本期行）。
   - `表一.行` 里带「（修正）」的行是 DefiLlama 事后修订的补记，照常追加，原来那行保留。
4. 追加成功后：`python3 标记已发布.py 表一 表二 表三 表四 表五`（只写成功的表），然后**重跑 `python3 打包.py` 并重做第 2 步的发布**（只传 `data/published.json` 一个文件即可），让「已发布到哪天」持久化。
5. 改坏了：页面右上角「…」→ Version history → Restore 是唯一可靠的恢复手段。改说明文字时用 `update_content` 精确替换整段，不要整页 `replace_content`。

### 4 · 主动推送到聊天（不要只丢文件）

1. 把 `输出/摘要.md` 的内容**原样**写进聊天正文。它已经包含：一行头（UTC 完整日）→ 四家当日手续费与日环比 → pump÷Pons、V2 占 Pons、赛道 Top60 → 回购市盈率与回购收益率（PUMP / PONS / STONK ｜ Flap 不适用）→ PONS 当日销毁与累计 → Arc 一行 → 近 7 天逐日表 → 异常（≤3 行，没有就写「无异常」）。
2. 异常判定已写进脚本（「修订」只看四家平台的手续费；赛道 Top60 的成员每天按 30 日排名重选，历史分母跟着变，属结构性变化，不追加修正行）：某家日环比绝对值 > 60%；分账比率相对 7 日均变动 > 5 个百分点；pump÷Pons 穿越 1.0；PONS 当日销毁为零或超过 7 日均的 3 倍；数据源延迟；分母缺失 > 5%；DefiLlama 修订已发布的数；Arc 升级条件首次触发。⛔ 不要为了凑字数编解读。
3. ⛔ 推送里不许出现买卖建议、目标价、仓位建议。只给数字和口径。
4. `SendUserFile` 发 `输出/发射台日更-<日期>.csv` 和 `输出/发射台日更看板.html`，正文里给出看板 Artifact 的链接。

### 5 · 每周一：Token Terminal 对账（需要浏览器，云端跑不了）

⚠️ 2026-09-26 实测：Token Terminal 页面是前端渲染，`WebFetch` 只能拿到页面元数据、读不到任何数值；云端沙盒也没有放行 tokenterminal.com。它给程序用的数据是 BigQuery 数据共享（调用方自付算力）或付费 API，免费档没有接口。所以定时任务**不做**这一步，别浪费步骤去抓。

周一那期只在摘要末尾加一行，给出脚本算的 pump.fun 最近 30 天 fees 与 revenue 合计（`日度数据.json` 里 `pump.fun` 最近 30 个完整日相加），写明「请打开 https://tokenterminal.com/explorer/projects/pumpfun 对照 Fees (30d) / Revenue (30d)」。对照口径：阈值 10%；已知常态（2026-08-31 基线）收入差 1.4%、手续费差约 15%（DefiLlama $45.8M vs TT $38.9M），手续费差扩大到 25% 以上才算异常。差 ≥ 阈值时先查脚本再查口径，⛔ 不改数字迁就它。

Token Terminal 覆盖情况（2026-09-26 按项目页是否存在核对）：有 pump.fun、Four.meme、Clanker、Zora、Moonshot、Raydium、Meteora；没有 Pons、Flap、StonkFun、Tolly，也没搜到 LetsBonk、Bags、Believe、Virtuals。⛔ 不要为了自动化去订 Token Terminal。

### 6 · 每周日：备份

`python3 打包.py --with-data` → `Projects` project_write，path=`launchpad-daily/工具包_含台账.py.txt`，local_path=`/home/claude/lp/工具/输出/工具包_含台账.py.txt`（覆盖同名文件）。

### 收尾检查（别漏）

- [ ] 看板 Artifact 已原地更新，台账 `data/*.json` 随同发布
- [ ] Notion 嵌入块已换、各表已追加、`标记已发布.py` 已跑且 `published.json` 已再次发布
- [ ] 聊天正文里有摘要全文 + 近 7 天表 + 看板链接；CSV 与 HTML 已发送
- [ ] 周一摘要末尾附 pump.fun 30 天对账行 / 周日备份（如适用）

## 数据源与接口备忘

- DefiLlama 协议：`https://api.llama.fi/summary/fees/{slug}?dataType=dailyFees|dailyRevenue|dailyHoldersRevenue`。⚠️ `slug` ≠ `module`，只能用 slug。⚠️ `overview/launchpads` 返回 500，不存在。⚠️ 已知 400 的 slug 脚本已跳过：jup-studio、bigpump、seiyan-fun、moonshot、vectorfun、daos.fun、pools-trade、ansem-io、americafun、user-fun。`ThreadPoolExecutor(max_workers=8)` 没有限流问题。
- DefiLlama 横截面：`https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true`（Launchpad 类目 Top60 作份额分母）。
- DefiLlama 链级：`overview/fees/{chain}`、`overview/dexs/{chain}`（带 breakdown）、`v2/historicalChainTvl/{chain}`，chain = `Arc`、`Robinhood Chain`。
- PONS 逐日销毁：公共节点不提供历史状态（连前一天都没有），脚本实际走「日界区块区间内 Transfer→dEaD 事件加总」，与日界余额差等价；首跑重算的 09-16 日末累计 312,793,919 与 Polar 当时用历史块读到的余额完全一致。
- PONS：合约 `0x39dBED3a2bd333467115dE45665cC57F813C4571`，销毁地址 `0x000000000000000000000000000000000000dEaD`，Robinhood Chain（4663），RPC `https://rpc.mainnet.chain.robinhood.com`（⚠️ 不带 User-Agent 会 403；会抛 HTTP 429，脚本已递增退避）。选择器 `balanceOf` `0x70a08231`、`totalSupply` `0x18160ddd`。出块约 0.101 秒/块，一天约 85 万块。
- PONS 价格：GeckoTerminal 网络 id `robinhood`，最深池 `0x10cc6bd38112cac182db90b6a71d8bb5939526ba`（PONS/WETH 1%），返回新到旧。实时参考价 DexScreener。
- PUMP 市值：CoinGecko `pump-fun`；STONK 市值：CoinGecko `stonk-3`（用 market_chart 的流通市值，脚本同时记下 CoinGecko 的流通量/总量做 burn-adjusted 核对）。
- ⚠️ `dailyHoldersRevenue` / `dailyProtocolRevenue` 对 pons-v1 / pons-v2 都不存在，别去试。
- 云端沙盒需要放行的域名：`api.llama.fi`、`api.coingecko.com`、`api.geckoterminal.com`、`api.dexscreener.com`、`rpc.mainnet.chain.robinhood.com`、`api.notion.com`（最后一个只用于上传嵌入块文件）。`python3 common.py` 可单独测。

## 平台与代币备忘

- **PONS 回购**：官方口径协议费 80% 用于回购，**人工在跑、不是合约强制**，逐日销毁呈批次跳跃就是链上证据。销毁是转到 dEaD，不是 `burn()`。
- **PUMP 回购**：DefiLlama `dailyHoldersRevenue`（链上销毁，汇总 pump 全部产品线）。理论回购按协议收入 100%。
- **STONK（2026-09-26 新增）**：StonkFun 2026-08-03 上线，STONK 2026-07-23 发行，总量 10 亿、铸币权已放弃。官网政策约 60% 平台收入在公开市场买回 STONK 并销毁（**官网政策，不是链上规则**）。DefiLlama 的 fees 口径 = 联合曲线 1% 平台费 + 毕业后 Raydium CPMM 池的创建者费 + 永久锁仓流动性分成；holdersRevenue = Jupiter 上买回 STONK、回到运营钱包的 swap。2026-09-06 接入 Raydium LaunchLab。第三方报道 9 月下旬累计销毁约 17%（未链上核实）。
- **Flap**：没有权益型平台币，市盈率一律「不适用」，表三那一行每天照留，它本身就是「这家没有平台币」的持续声明。bBroker（BSC `0xf1969F437Fe3C485468FB17B0d9861c24DCd7777`，市值约 9 万美元、流通 7.45 亿）是 bBroker Vault 的 NFT 金库配套代币，不是 Flap 的股票。
- **pump.fun 分档**：8.5 万美元市值是分账断点，以下协议费 0.93–0.95%、创建者 0.30%；以上协议费 0.05%、创建者 0.95%。权威值在链上 FeeConfig（费用程序 `pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ`）。自 09-01 起「手续费下降」不一定等于「成交量下降」。分账比率图上的台阶是最早的信号。

## Arc 链

- Circle 的 Arc，Chain ID 5042（测试网 5042002），gas 是 USDC，2026-09-16 主网上线。官方 RPC `https://rpc.mainnet.arc.io`，浏览器 `https://explorer.arc.io`。
- 2026-09-16 时 DefiLlama 的 fees / dexs 为空；2026-09-26 核实已索引，fees 协议列表里有 Argus World（目前 Arc 最大的发射台，占发射台手续费八成以上）、Wonk Fun、Foci、Peach Launchpad、o1 Launchpad、Tolly、SolonPad、RadarDEX 等 23 家发射台。
- ⚠️ **DefiLlama 链级 overview 的逐日图会漏协议**：2026-09-26 实测 Arc 漏了 Argus World、Wonk Fun、Foci，Robinhood Chain 漏了 Pons V1、NOXA Fun 等 29 家。`拉Arc.py` 会把 protocols 列表里有数、逐日图里没有的协议逐个从 summary 接口补回（手续费补全部应用层协议；成交额只补 Dexs / Launchpad，交易终端与聚合器的成交是转发给 DEX 的，补了会重复计算；链自身 gas 与基金会分成不补）。不补的话 Arc 发射台合计会少八成以上。
- Robinhood Chain 的 DEX 成交在 DefiLlama 上约 14–19 亿美元/日，大头是 Uniswap V3/V4（含股票代币池与 Pons 毕业池），这是 DefiLlama 自己的口径。
- ⚠️ Arc 上不少发射台的 swap 走 Uniswap 底层池，DEX 成交记在 Uniswap 名下，发射台的成交额系统性偏低；发射台看手续费。Dune 口径（首日发射台占 DEX 成交 82%）与 DefiLlama 对不上是已知问题。
- **升级条件**（任一满足 → 挑出头部发射台做逐家平台收入监控，初始阈值可调，写在 `出看板.py` 的 `TH_A / TH_B / TH_C`）：
  - A：Arc 发射台合计手续费，最近 7 天每天都 ≥ $300K；
  - B：任一 Arc 发射台手续费，最近 7 天每天都 ≥ $100K；
  - C：Arc 全链 DEX 成交 7 日合计 ≥ Robinhood Chain 的 25%。
  首次触发会进异常提示。触发后先征求用户同意再加逐家监控，⛔ 不要自己动手接。
- **Tolly Labs**（用户 2026-09-16 提出的待办）：平台币 $TOLLY `0xbc43ce8dec648ea298c4275559b81d6261c90b67`。手续费现在由 Arc 面板按 DefiLlama `tolly` 自动跟踪。已核实机制：不走 bonding curve，全部供应直接进永久锁定的 USDC 池，底层 Uniswap；每笔 1% 池费，买入（USDC）64% 创建者 / 12% 持币分红 / 10% 协议 / 9% 买 TOLLY 销毁 / 5% 销毁项目代币；卖出（项目代币）100% 销毁。**还缺**：协议金库、持币分红池、销毁去向（dead 地址还是 `burn()`）三个地址 —— 要去 GitHub 仓库（14 个已验证合约，含 `TollyPad`）或 Arc 浏览器核实，之后才能照 PONS 的方法做销毁与分红监控。机制拆解可单独走 `/launchpad-teardown`。

## 已知缺口（每期看看有没有补上）

- Flap 的成交额反推不了（税代币模型），需要链上扫。
- Pons V2 存活率未测，V1 是 2.37%。
- pump.fun 毕业前后的手续费拆分要读链上 FeeConfig + 分池统计，日频做不了，放周频。
- 赛道总量只加总 Top60（Launchpad 类目 170+ 个），尾部未计入，实际总量略高。
- Bags、Binance Alpha、Meteora DBC、four.meme、clanker、BONK.fun 的费率未核实。
- STONK 已核对（2026-09-26）：CoinGecko 总量 8.17 亿（10 亿减去已销毁，说明走的是 SPL burn，总量真的在减少），流通量与总量几乎相等，CoinGecko 市值已经是 burn-adjusted，可以直接用。以后若流通量明显回到 10 亿附近再复核。
- Notion 历史行里有 Polar 留下的笔误（表一 09-21「33.8%2」、表三 09-20「14.89%2」与一行空 PONS），按「不动历史行」原则保留。

## 参考基准（写摘要时对照，不用每次重查）

- 2026-08-29 首日基线：pump.fun 1,938,968 ｜ Pons 合计 3,827,609（V2 占 90.4%）｜ Flap 328,093 ｜ pump÷Pons 0.51。2026-08-29 起 Pons 合计单日超过 pump.fun，这是本轮最重要的结构变化。
- 2026-09-22（迁移前最后一期）：pump.fun 1,746,896 ｜ Pons 合计 2,580,573 ｜ Flap 1,251,075 ｜ 赛道 Top60 9,052,576 ｜ pump÷Pons 0.68；PONS 销毁地址累计 315,687,280（31.6%）；回购市盈率 PUMP 6.91x / PONS 2.41x。
- 估值基线 2026-08-29：PUMP 回购市盈率 5.8x、PONS 6.1x。
- Robinhood Chain 90 天免 gas 补贴 2026-09-29 到期（通过 Robinhood Wallet 的交易），到期后是真正的压力测试，前后一周的 Pons 数字要特别看。

## 长期留存

`估值序列.json`、`销毁逐日.json`、`销毁累计.json`、`销毁台账.json`、`销毁修正记录.json`、`已发布.json` 六个文件逐日累加，用户要看一到两年。每天随看板发布到 Artifact 的 `data/`（第 2 步），每周日再备份一份到 Project（第 6 步）。

最后更新 2026-09-26（从 Polar 迁移；新增 StonkFun、Arc 链、日界销毁口径、延迟与修订处理）
