# uncleonchain · 给 Claude 的项目说明

链上大叔研究台（uncleonchain.com）：个人 web3 链上数据情报终端。大叔（仓库主人）只给方向，
Claude 是这个产品的操盘手：自己判断、自己做完、自己提交推送，尽量不回头问人。

## 工作方式

- 用中文沟通。改完直接 commit + push 到 `main`，不开 PR。Cloudflare Pages 从 `site/` 自动部署，1～2 分钟上线。
- 推送前本地跑一遍 `LP_DATA=$PWD/data LP_OUT=$PWD/build python3 pipeline/出网站.py`，用 Playwright 截图自查（Chromium 在 /opt/pw-browsers/chromium）。
- 数字先自己核对再说；拿不到真实数据的指标标「待接入」，绝不编数字或拿近似值冒充。
- 只给数据和过程记录，不写买卖建议。

## 结构

- `pipeline/跑日更.py --site`：GitHub Actions 每天 UTC 10:20 跑（推送 pipeline/content/assets 也会触发）。
  拉日度 → 读销毁 → 拉估值 → 拉Arc → 出看板 → 拉宏观 → 写日志 → 出网站，结果提交回 `data/` 和 `site/`。
- `pipeline/宏观规则.py`：四层框架（L2 除外，见 `l2/`）（流动性 / 周期 / 筹码 / 情绪）的指标注册表、区间规则、层结论、预警、日志与周月复盘生成。
  每个指标 = 一条「判定序列」（原始或派生，如 13 周变化，W-FRI 对齐）+ 一张 cuts 区间表，卡片、详情页全历史图、正常波动范围都用它。
  L1 按《L1 宏观层数据维度规格》（2026-10-02，10-04 修订）：乐观度 / 信用 / 实际利率四态 / 情境格 / 净流动性闸门；
  L1-B 加密资金通道（只确认不预测）：稳定币主线（去重）/ 交易子弹（剔除 Tron + 含 Tron 并列）/ ETF / 升水 / 资金轮动矩阵；
  判定 = 顺风 / 中性 / 中性偏谨慎 / 逆风。规则改动写进 `RULE_CHANGES`（更正记录页自动展示），已写入的历史日志不改。
  日志里中英文字段并存（…EN），英文站直接读。
- `l2/`：L2 周期状态机（大叔给的方案，和《BTC周期层L2研究》§7 同一份代码，**规则别在网站里重写**）。`.github/workflows/l2-daily.yml`
  每天 UTC 02:17 跑 `l2/l2_daily.py`（Coin Metrics + bitview.space，需要 pandas）→ `data/l2/l2_latest.json` + `l2_history.json` → 出看板 → 出网站。
  缓存 `l2/cache/` 走 actions/cache，不进仓库。宏观页 L2 段、日志里的 L2 层结论 / 「L2」快照 / 状态切换预警都只读这两个 json；
  原 L2 单指标卡（MVRV / MVRV Z / Realized Price / NUPL / Mayer / Puell / Pi Cycle）2026-10-08 撤掉，旧链接 `_redirects` 301 到 /macro/#layer-2。
  云端会话用个人环境「uncleonchain」（放行 bitview.space、community-api.coinmetrics.io），本地能直接跑 L2 / L3 验证；Default 环境仍连不上。
  bitview 2026-10-31 前后升到 v0.13：参数 from→start、分龄 utxos_X_old_* → age_X_*、地址 addrs_* → balance_*、URPD 无 /dates，接口说明 bitview.space/openapi.json。
- `l3/`：L3 筹码层（依据《BTC筹码层L3研究》《L3网页数据维度规格》，2026-10-11）。`.github/workflows/l3-daily.yml` 每天 UTC 02:47 跑 `l3/l3_daily.py`
  （Coin Metrics + bitview，含 URPD `/api/urpd/all/{date}?agg=log500`）→ `data/l3/l3_latest.json`、`l3_history.json`（样本外，每天一行不回填）、`l3_series.json`（全历史）、
  `l3_conc.json`（筹码集中度：2012 年起每周日一张种子，每次最多补 14 分钟，之后每天追加）。只有三条通过检验：STH 成本 +1σ 压力区、STH 成本参考支撑、
  低波动 + 集中 = 大波动预警（只说幅度不说方向）；其余（筹码分布、STH 状态、交易所 / 大户 / 散户）只作描述，不许叫支撑 / 压力 / 信号。
  L3 层结论 = 价格位置 + 预警（`宏观规则.l3_verdict`），宏观页 L3 段 `出网站.l3_tab`，卡片指标读 `R.attach_l3`。参数在 `l3_daily.py` 顶部，改参数前先改研究文档。
- `l4/`：L4 情绪衍生品（《L4网页数据维度规格》，2026-10-22）。`l4-daily.yml` 每天 UTC 03:17 跑 `l4/l4_daily.py` → `data/l4/l4_latest.json` / `l4_history.json`。
  层结论读 `conclusion.level`（过热 / 偏热 / 中性 / 偏冷）+ 信号；`data_status` 非 ok 或 funding stale 时「今天不判断」。资金费率要 repo secret `COINALYZE_KEY`（BitMEX 在 Actions 里 403）。
  fng / hl_funding / hl_oi 已 retired；altseason、btc_dom 降为 L4 观察。宏观页 `l4_tab`。
- `cal/`：事件日历。`cal-daily.yml` 每天 UTC 00:37 跑 `cal/cal_daily.py` → `data/cal/cal_latest.json`；页面 /calendar/、首页卡片、宏观页综合研判下「下一个：…」。CoinMarketCal / Coindar 没 key 就「未接入」。
  监管 / 立法二元表决（type=REG，`origin` = auto:sec / manual）。只收有官方日期、结果二元的表决 / 最终决定日，每条必须有官方来源，没钟点就不写 time_utc。
  ① SEC 对加密产品的最终批准 / 否决期限：`cal/reg_sec.py` 每天自动扫 Federal Register 官方接口（全文走 govinfo，federalregister.gov 全文链接会转人机验证），
  只认「designates … approve or disapprove」且没有「or institute proceedings」的；之后出了批准 / 否决令或撤回（FR 文件头 File No. 对上，或 SEC 页 WITHDRAWN）就不出。失败用上次结果并标 stale。
  ② 国会委员会表决会 + 总统签署期限：`cal/reg_congress.py` 每天自动扫 api.congress.gov（repo secret `CONGRESS_API_KEY`；云端环境 uncleonchain 存了同一个 key，代理注入 X-Api-Key，本地跑设 `CONGRESS_API_KEY=proxy-injected`）。
  只收参院 Business Meeting / 众院 Markup、Meeting（不收听证），会议标题或关联法案标题含加密关键词；签署期限 = 呈送总统后 10 天（星期日除外）。
  ③ 院会表决 / 外国议会表决：手工维护 `cal/reg_events.json`（每周一个定时云端会话核对一次），核对后改 `checked_utc`，不收的写进 excluded。超过 14 天没核对 data_status 提示。
  `btc.reg_status` = 各来源最后成功核对日（manual / sec_auto / congress_auto）。大叔的交易系统读 btc.events 里的 REG（48 小时叠加、事件窗口），别改 type 值。
- `leg/`：涨跌腿追踪 + 山寨轮动窗口（站长交付 `leg_data.py` + 设计稿；11-09 升 v3 / schema 3：BTC 永远在涨腿或跌腿之一，`direction` = up / down）。`leg-daily.yml` 每天 UTC 00:53 跑 `leg/leg_data.py`
  （2017-08-17 起币安现货 BTCUSDT 已收盘日线，data-api.binance.vision 优先，云端环境 uncleonchain 已放行币安三个域名；之前读仓库里的 `leg/leg_early_cache.csv` = Coin Metrics PriceUSD）
  → `data/leg/leg_latest.json`（schema 3）+ `leg_history.json`（全部腿逐条 + 分布 + 牛熊周期口径，详情页「全部行情」）→ 出网站复制到 `/data/`。历史核对：截至 09-27 共 5,916 天、305 条腿、牛涨 103 / 牛跌 99 / 熊涨 49 / 熊跌 54。
  11-09 升 schema 4：`alt_leg` = 山寨整体涨跌腿（币安成交额前 50～75 山寨币等权指数，每月 1 日重排，ALT_THR=15%；大叔定「简单逻辑」，按校准结果只加一条：
  B 结尾且 2026-06-11 起上市的代币化股票不入篮 `ALT_STOCK_FROM`，其余参数用脚本默认）。700 来个币的日线缓存 `leg/leg_alt_cache.csv`（~30MB，gitignore，走 actions/cache）。
  卡片里的「山寨整体」模块是站点自写（`leg.js` 的 `altLegModuleHTML` / 文案 `LT`），只用百分比，不展示指数点位。校准用 `--alt-calib --alt-scan`（结果 `leg/leg_alt_report.txt`，不进仓库）。
  宏观页顶部（大叔 11-10 定）：「周期里的涨跌腿」图 `leg_cycle_chart`（价格按涨 / 跌腿分色，背景 = L2 状态，价格线用 l2_series 的 Coin Metrics 收盘）→「短期 · 波段」读数卡（只放 BTC 涨跌腿 + 山寨整体，
  山寨轮动窗口 11-13 起连详情页的读数卡也去掉，11-14 规律说明一节也撤掉；转换脚本 gen_leg.py 里有对应规则，设计稿换版不会带回来）→「长期 · 周期」四层综合研判 → 紧接「结合短期」`leg_short_context`（11-11 大叔定 A 方案：只摆历史位置和剩余空间，**不写买入 / 止盈等动作**；位置对比用 2010 起全部同类腿，剩余空间只用 2017-08 起的；长短期方向相反时多一句「不矛盾」）。卡片配色 11-10 起全用站点变量，不再用设计稿海报色。
  读数卡放宏观页最上面、四层综合研判之上（`leg_macro_card`，大叔 11-08 定：这是用户最直观的结论）+ 首页卡片（`leg_home_card`）；详情页 /leg-tracker/（`出网站.build_leg_tracker`，挂在宏观下，不单独占导航），都由 `leg/web/leg.js` 取数渲染（样式 `leg/web/leg.css`，全收在 `.lg` 下，变量 `--g-*`）。
  **数据字段、文案（T.zh / T.en）、STATS / ALT 统计数字、状态规则照设计稿，不许改**；统计只在研究文档升版时改并同步 `STATS_ASOF` + 更新日志。停更 = asof 比今天早 3 天以上（浏览器里判断）。
  卡片刻度（大叔 11-14 定）：`出网站.leg_scale` 按 L2 当前状态（L2_BULLISH 偏多 → 牛市阶段，否则熊市阶段，和「结合短期」同口径）取同阶段已走完的腿——BTC 2017-08 起、山寨整体指数 2018-08 起——写进站点版 `site/data/leg_latest.json` 的 `site_scale`（分位 + 全部天数 / 幅度，原始 data/leg 不动），`leg.js` 的 `dnScaleHTML` / `upScaleHTML` / `altScaleHTML` 画：幅度 = 四条分位线（只标「一半」「九成」，英文 Half / 9 in 10，不写 P90 这类行话）+ 一句「比 N 条里的 M 条走得久 / 跌得深」；天数 = 提示线（BTC 涨腿 89 天照设计稿；BTC 跌腿 45 天 `DN45`，假设级，证据是 2017 起 9 条，作废条件在详情页 #d45；山寨不画线）。配色照原回撤条（冷色渐深，超 P90 跌腿红 / 涨腿琥珀）。45 天线不进交易计划，要进先让 project 写进《操作规格》。
  设计稿换版时照原样拆：pure 函数 + STATS/T + 渲染片段原样搬进 leg.js，只改取数 / 预览删除 / 颜色变量。三个口径常量（THR_EQ / D0_INCLUDE_IGNITION / IGN_GAP）用脚本默认值，上线前 ACCEPTANCE 四个回放（--asof 2026-09-25～28）已全部对上；改规则先跑 `--selftest` 和回放。红线：不出现挂单 / 仓位 / 止损，不给个币名单。
- `core/`：核心选币观测台（大叔 2026-11-14 交付：Notion《核心标的基本面与叙事追踪》+ 原型 obs.html + volume_rank.py）。`core-daily.yml` 每天 UTC 04:13 跑 `core/core_daily.py`
  → `data/core/core_latest.json`（当前读数）、`series/<币>.json`（详情页走势）、`core_history.json`（评分 / 成交额排名每天一行，不回填）→ 出网站复制到 `/data/core/` 并注入 `gates`（`出网站.core_gates`：L2 状态熊底区 / 熊末→牛初才过、L1 净流动性闸门）。
  页面 /core/（`出网站.build_core`，hash 路由 #home / #rank / #coin/UNI / #volume / #market / #alerts / #findings / #method），由 `core/web/core.js` + `core.css` 渲染；首页卡片 `core_home_card`。
  来源：DefiLlama（手续费 / 收入 / 持有人收入 / DEX 成交额 / TVL）、币安现货日线（data-api）、U 本位永续 = data.binance.vision 公开归档（fapi 在美国 451；缓存 `core/cache/` 走 actions/cache，首次回填约 5 分钟）、CoinGecko 供给（云端环境已放行 api.coingecko.com）。
  人工登记全在 `core/core_config.json`（12 个观测池 T1–T3 + 18 个观察标的 W、叙事阶段、解锁、事件、证伪条件、风险记录、重大发现），Notion 有新核对就改这里。
  **评分研究立项（11-14 大叔定：没验证的不能用，但要立项研究、公开进度，不能静默撤掉）**：立项书 `core/research/评分研究立项.md`（页签 #research 原样渲染，`出网站.core_md`），阶段 M0–M5、判定标准写死在里面；研究出结论前页面不打分、不按分数排名，只摆读数 + 检验结论，分数只在后台记（`core_history.json`）。
  六问卡 = 《核心选币方法论》第 4 层 §5：一句话价值 / 商业竞争（反向逻辑）/ 价值捕获 / 筹码 / 驱动类型与阶段（1a/1b/1c、T0/T1/T2）/ 注意力与认知差；卡片十栏。核对过的答案写 `core_config.json` 的 `cards`，自动带入的只算草稿。
  建仓条件判定只用已验证 / 流程规则（`core.js` 的 `GRADE` / `HARD`：闸门 1/2/3、R1、R4）；R2 / R3 / R6 只作提示。页面只说「条件齐备 / 条件未齐 / 有硬条件未过」和风险提示，**不写买入 / 卖出**。
  数据请求的缓存版本号用 `generated`（不是数据日，同日重跑会被 CDN 缓存一小时，11-14 出过「篮子读不到」误报）。
  大叔 11-14 定：美股和黄金直接去掉——现货剔除 B 结尾且 2026-06-11 起上市的代币化股票 / ETF，合约只算币安现货有交易对的币（归档没有标的类型，SNDK、XAU 这类分不出来）。
  11-14 第二轮（大叔反馈）：成交额 = 币安全口径（`core/binance_vol.py`：全部现货交易对按当天收盘折美元，无 USDT 对的法币走 BTC 交叉；U 本位 USDT/USDC 保证金永续 + 交割；币本位 × 收盘），
  缓存 `core/cache/spot_pairs.json`、`fut_all.json`；榜单一张表，标签 regular / entrant / exit / new。等权篮子 = `leg_latest.json` 的 `alt_leg.basket.members`（和宏观页同一个）。
  评分回测 `core/score_backtest.py`（每周一在 core-daily 里跑，判定标准写在文件头，**跑完不许改标准**）→ `data/core/score_backtest.json`；第一轮 38 个币全部「未通过」（R、V 方向对不显著，C、D 无区分力）。
  外部复核包 `core/review/README.md`（给 Codex / Gemini / Grok 的分工和提示词）。拉盘复盘 = 大叔的龙头与轮动研究，原件 `core/research/`，`core/rotation_import.py` → `data/core/rotation.json`（静态快照，不日更）。
  待补维度：供给侧收入 / 日活（DefiLlama active-users，同接口带 GitHub 组织名和国库适配器）/ 国库（每周，`weekly.json` 缓存）/ 核心开发者（GitHub，Actions 的 GITHUB_TOKEN，沙盒 403）已接；代币激励只有付费源，待接入。
  「六问卡」原文在大叔的《核心选币方法论》里，网站还没有，等大叔给。
- `alpha/`：Alpha 雷达（2026-11-14，替换「叙事埋伏」，/narrative/ 跳 /alpha/）。和核心选币互补：核心 = 币安上有连续读数的成熟代币；Alpha = 没成熟的机会（无币协议、新协议 / 产品 / 机制、升级、上所）。
  **大叔 11-14 定：只研究正规项目，不做部署后 0–6 小时 / 纯 MEME 打狗**（要做另起一套，不上网站）；Codex 的分钟级 alpha-worker 搁置。
  `alpha-daily.yml` 每天 UTC 04:43 跑 `alpha/alpha_daily.py`（DefiLlama 协议列表 + dailyRevenue）→ `data/alpha/alpha_latest.json`（无币协议收入榜：本协议和母协议都没登记代币、30 天收入 ≥ 10 万美元、按母协议合并；新上架：listedAt 近 14 天）、
  `alpha_leads.json`（线索台账，只追加不删，首日 11-14 = 基线；每天回查发币）、`alpha_history.json`（每天一行）。参数和剔除名单 `alpha/alpha_config.json`。
  页面 `出网站.build_alpha`：/alpha/ 雷达、/alpha/cases/ 案例库、/alpha/method/ 方法论、/alpha/progress/ 研究进度，文档在 `alpha/research/*.md`（`core_md` 渲染）；首页卡片 `alpha_home_card`。
  方法论 = Codex 交付《Alpha标的筛选研究体系》全面版，网站版去掉执行纪律（执行卡 / 固定止损止盈参数）。红线：不打分排名、不公开「执行评估」档、不点名没有协议级读数的小市值币、不写买卖 / 仓位 / 止损。
  分工（大叔 11-14 定）：代码和推送网站 Claude 做，查证和出数据交 Codex，任务包 `alpha/review/README.md`（T1 发现源验收、T2 10-16 冻结评分 D30 复查、T3 无币协议前 30 补证），结果回到 `alpha/review/*.json` 再由 Claude 并入。
  11-14 三个任务已交回并入：候选池 /alpha/pool/（`出网站.alpha_pool`，读 `alpha/review/*_checks.json`；`alpha_daily.py` 把 verdict 写进台账 `status` / `status_history`，只追加）；研究观察 12、待核验 18。
  A4 判定标准已写死在 `研究进度.md`（研究观察组 vs 对照组 90 天收入保持率，各 ≥ 20 个才判），`alpha_history.json` 每天的 `rev30` 就是它的数据，**别删这个字段**。T2 九个全部待判（原卡没冻结合约 / 发现价）。
  T1 可接源（ethresear.ch、Snapshot、Binance、Bybit、Upbit）还没接：云端环境没放行这些域名，本地验证不了。
- 发射台活动温度（`pipeline/周期观察.py` 数据与热潮识别、`周期仪表盘.py` 展示）：每日更新。序列 = 研究快照 `content/cycle/snapshot.json`（截至 2026-10-17，sha256 在 manifest）+ 之后接 `发射台矩阵.json`「历史」的类目合计；热潮规则重算快照区间 27 轮逐字段对上（对不上会打 ⚠️）。
  仪表盘 `周期仪表盘.hero` 放在矩阵页最上面（先看温度再看细节），周期页 /launchpad/cycle/ 看这一轮、各阶段时长、历史；全站统一叫「发射台活动温度」，颜色用 `--cyc-*` 变量，文案要大白话。「钱在哪」= `出网站.money_where`。
- 发射台长周期（2026-10-29）：`周期观察.long_view` / `coverage`。全部历史 2021-09-18 起只作背景，比高低只用可比段（`COMPARABLE_FROM` = 2024-03-01，pump.fun 开始报数；之前只有 1–6 家融资型平台报数）；
  长周期读数只作描述（距最高、常态下沿 Q05 的倍数、可比段最低），不合成分数、不贴季节。近期温度仍是 730 天 Q05–Q95（≥365 天）。覆盖 < 95% 时第一屏提示。
- AI Agent 页 /ai-agent/（`出网站.build_ai_agent`）：读 `public/ai-agent/monitor/core_series.json`（交接包 `tools/agent-id` 导出，原样页面也发布在 /ai-agent/monitor/）。
  旧的 self-hosted 模板 `tools/agent-id/handoff/` 作废不用；U = 没取到完整数据，不当 0。
  云端版（2026-11-06 交接包）：`tools/agent-id-cloud` + `.github/workflows/agent-id-daily.yml`（GitHub-hosted，2026-11-09 起每天 UTC 00:20 唯一定时 + 手动，单独 concurrency 组 `agent-id-daily`）。
  节点 = 公共免费池优先（workflow 里 `AGENT_ID_RPC_PUBLIC`，开跑先探测 2026-10-20 的注册日志，查不到的剔除），`ALCHEMY_KEY` 只兜底；逐请求失败才换下一个，跑完日志里 `rpc_served` 报各节点承担了多少。
  大叔 2026-11-06 定：先用公共免费的，key 兜底；云端直连不走代理（`AGENT_ID_PROXY` 不配 = direct）。`AGENT_ID_STATE_KEY`（Fernet，Codex 已生成存好，加密 checkpoint artifact，丢了旧状态解不开）；
  2026-11-06 首轮实测：4 个公共节点都过不了历史探测（publicnode 对 10-20 返回空、drpc 400、1rpc 只给 50 块、llamarpc 域名失效），全部 4283 次请求走 Alchemy 兜底；回填 10-19～11-05 约 10 分钟，独立重算与旧数据 10 天逐项一致。
  加密 checkpoint 约 440MB / 份，保留两份（仓库公开，artifact 不占付费额度）。dispatch 的 daily.yml 若被 daily-pipeline 里后排进来的任务挤掉没关系：组里每条都从最新 main 重出网站。
  2026-11-09 接入 Gang（`collector/gang.py`，配置 `gang_adapter`：官方公开仓库 gangfun/gang-launchpad@8b12b30 的事件 topic 表 + pad 名单 + GangPadRegistry.pads()，E3）：成交额 = 含费毛额、只算 BNB 计价；
  未见创建记录的币当日 U；未完成的日子每次自动补。运行时 config 来自 checkpoint，`run_cloud.REFRESH_KEYS` 里的段每次以仓库为准、仓库新增段自动并入。
  2026-11-09 同日接入 `collector/agentpads.py`（配置 `agentpads`）：Flap = Portal 0xe2cE…9De0 上 FlapNFTGated(token, Binance Agent ID) 的门禁币（docs.flap.sh/en/flap/drafts/nft-gated，E2；
  买入 eth 已含费，链上实测），门禁移除后不算；Four.meme = TokenManager2 `_tokenInfos(token)` 第 3 个字的第 85 位 = Agent 钱包创建（官方仓库 four-meme-ai，买卖不限 ID，单列标注；
  买 = cost+fee，卖 = cost）。两家全量日志大，不缓存原始响应，只存命中事件。Four.meme 另有未公开合约 0xebe7…27f3（实现 0x02d7…，交易事件 topic 0x8728ba77：w0 1=买 0=卖、买毛额 w6、卖毛额 w5），
  抽查 6 个交易者 3 个没有 Agent ID、无文档说明属 Agent 生态，未计入。导出每行带 `by_platform`，页面「分平台（最近 7 天）」表。`agent-id-probe.yml` 手动摸底任意区块段事件 / eth_call / 公开网址（#grep= 关键词摘录）/ Four.meme 普查。
  发布 = 只提交 public/ai-agent/monitor → dispatch `daily.yml`（变量 `AGENT_ID_DEPLOY_WORKFLOW` 不设就默认它）。旧 Codex 任务（大叔电脑）已不推数据，但仍应停掉，避免旧数据盖回来。
- 时间口径（2026-11-06 定）：后端统计一律 UTC+0，数据按 UTC 完整日（UTC 0 点收盘）对齐，价格用收盘价（L2 / L3 只取 < 今天的日子）；
  前端显示按语言区域换算：中文站新加坡时间（UTC+8，`SG_TZ`），英文站美东时间。钟点用 `出网站.TT`，收盘 `TCLOSE`，UTC 日截止 `TDAY`，日历列表 `TLOC`。别写裸「UTC hh:mm」或「北京时间」。
- 交易所 + ETF 持币：`拉宏观.fetch_etf_hold`（TFTC data.json，`totalNetAssetsUsd / btcCloseUsd`）→ `etf_btc`；注册表 `etf_hold` / `exetf_sum` 在 L3「交易所与现货 ETF 持币」组，只作描述。
- **所有 workflow 共用 concurrency 组 `daily-pipeline`**：排队中的会被新排进来的取消，手动触发一次只排一个。
  提交步骤在 `pull --rebase -X theirs` 之后会比对：运行期间 main 上 pipeline / leg / config / content / assets 有改动，就用最新代码重出一次网站再推（2026-11-10 出过旧代码出的页面盖掉新版的事）。本地出网站会删掉 `site/data/launchpad/*`，提交前 `git checkout -- site/data/launchpad`。别用 git stash（出过丢改动的事）。
- **指标注册表**（M12）= `宏观规则.REGISTRY`：每条带 层 / 组 / 序 / 状态（live · pending · retired；自录的满 90 天前自动「记录中」）/ cuts（tone 即 bias：up 顺风 · neutral · dn 逆风 · warn 留意）/
  fmt / 出处 / 界（边界文字）/ 解读。宏观页各 Tab 的卡片分组、待接入占位卡、详情页、上一个 / 下一个、口径页指标表、停用说明页全部从它生成——改层的数据维度只改注册表 + 数据。
  L2 六个「估值与持有者」指标读 `data/l2/l2_series.json`（`R.attach_l2` 挂到 S 上）。
- `config/`：`composite.json` 综合研判短句表（附录 D，四层合成，`pipeline/综合研判.py` 拼接）、`site.json`（定时任务说明；时间从 workflow cron 读）、
  `glossary.json` 术语表与标签定义（G7）、`l1_rules.json`（宏观总文档 §10.2 逐条照抄）。改措辞只改配置。
- `content/changelog.json`：更新日志（附录 B）。**每次上线新功能 / 改口径都在最前面加一条**（`notify: true` 才弹窗；`data` 类带 `corrections_anchor` 并在 `RULE_CHANGES` 里加原因）。
- 全历史数据：`site/data/series/<id>.json`（归档，截至上月末，每月 1 日重写；数据源回改时重写）+ `<id>.recent.json`（本月）。
  构建时和上一版比较，7 天以前的数据变动 > 0.5% 记进 `data/data_revisions.json`（更正记录页展示）。`site/data/latest.json` = 全站当前读数唯一来源。
- 页面上的「当前读数」一律读本次构建的最新值（`G["RS"]`），日志只在日志页和标「日志 · 冻结」的位置出现；统计窗口规则在 `宏观规则.stats_window`（D3）。
- `pipeline/出网站.py` + `pipeline/网站样式.py`：中英双语（英文挂 /en/，`T(中, 英)` 包所有文案）、深 / 浅主题（CSS 变量，
  别写死颜色）、面包屑、交互走势图（`chart_div` + /data/*.json）。指标详情页 /macro/<key>/。
- `data/解读日志/{日,周,月}/`：写入即冻结。同日重跑且核心缺失变少才覆盖并标「补录」。
- `content/posts/<macro|rotation|narrative>/`：手写文章（.md 或整篇 .html）；`content/journal/<日期|周|月>.md`：人工点评。
- `content/reports/`：分析报告（新报告放进来后跑 `python3 pipeline/出报告PDF.py` 生成浅色 PDF，报告页「下载 PDF」按语言给）。大叔给排好的浅色 HTML（中文 `<slug>.html`，英文 `<slug>.en.html`），iframe 原样嵌入、不加摘要框；
  深色版出网站时自动生成（颜色明度翻转），不用手调。元信息写 `<!--meta-->`（含 `分类:` BTC / MEME / RWA / AI Agent，报告页按它筛选），流程见目录 README。
- `assets/`：头像、favicon、og 卡（`pipeline/做图标.py` 生成），`assets/vendor/html2canvas.min.js` 由 Actions 自托管。
- 呈现原则（2026-10-22 减法）：方法论放使用指南或 ⓘ 悬浮说明（页头 `p.lede` 自动变 ⓘ，要平铺的写 `lede keep`；图表 `note` 也变 ⓘ）。
  各层卡片按注册表 level 分层：核心 = 大卡 + 青柠左边线；辅助 = 虚线小卡无走势；没有核心的组折进「辅助与观察（不进本层判定）」。
- 视觉：底 #05070c、卡片 #0b0e17、1px rgba(255,255,255,.06) 细线、涨 #00ffcc、跌 #ff3366、品牌青柠 #a3e635（只用于导航和按钮）。
  浅色主题（太阳 / 月亮按钮切换）的配色在 `网站样式.py`。左侧常驻导航，每个板块独立 URL（方便推特直链）；子页面顶部有面包屑。

## 待办（按优先级）

1. 核对 2026-10-02 L1 改版后的 Actions 首跑：FRED 新序列（NASDAQ100 / VIXCLS / T10YIE / BAA10Y / NFCI / BAMLH0A0HYM2 / WTREGEN）、
   DefiLlama 稳定币分组（附注里有实际匹配到的币）、ETF（haturatu 镜像）、CME 升水（Yahoo 合约代码能否取到）是否都通；
   乐观度 z 在 2026-09-25 应约为 +0.49、净流动性约 $5.77T（研究报告 §7.1），对不上就查口径。
2. 宏观 v2：Coinglass（多空比 / 爆仓，需 key）、Deribit 期权 P/C 与 IV。2026 年底复核净流动性闸门（规格 D1）。
3. Alpha 雷达 A2：接 T1 验收可接的发现源（ethresear.ch、Snapshot、Binance / Bybit / Upbit 上新公告），先放行域名再本地验证；待核验 18 个的下一轮补证。
