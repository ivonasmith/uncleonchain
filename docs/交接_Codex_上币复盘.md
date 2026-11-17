# 交接给 Codex：交易所上币复盘（大叔 2026-11-17 定：这条线整条交给 Codex）

## 一、要回答的问题

各交易所上线一个新币后，历史上价格怎么走：从开盘第 15 分钟价算起，7 / 30 / 90 天回报、跑赢或跑输 BTC 多少、90 天内最高点和第几天；按 BTC 牛熊 × 涨跌腿（宏观仪表盘的涨跌腿数据）分组。
另有币安「不同开空位置」的历史读数。**只给历史统计，不写买卖 / 仓位 / 止盈止损建议**（`docs/表达规范.md`）。

口径写死在 `alpha/research/交易所上币回报研究.md`（v3），改口径先升版、写更新日志。

## 二、现状（2026-11-17）

| 部分 | 状态 | 文件 |
|---|---|---|
| 币安全历史（2017 起，含已下架） | 完成，659 个币进统计 | `alpha/listing_history.py` → `data/alpha/listing_history_binance.json`、`listing_regime_stats.json` |
| 币安开空位置读数 | 完成 | `alpha/listing_short.py` → `data/alpha/listing_short_stats.json`、`listing_paths_binance.json` |
| OKX、KuCoin、Coinbase、Crypto.com、Bitstamp、Bitvavo | 完成 | `alpha/listing_history_x.py`（CCXT）→ `data/alpha/listing_history_<id>.json` |
| Bitget | **不完整**：4.5 小时只跑了 484 / 3578 个币 | 要分片重跑，见第四节 |
| Gate、BingX | **不完整**：K 线历史只回溯约一年，起点只能用 1 小时价 | 先保留，标「不完整」 |
| Upbit | 在跑（11-17 08:54 那轮），结果会自动提交 | 跑完核对 |
| Bybit | 在跑（09:09 之后那轮）。API 在美国被拦，走官方逐笔成交归档 public.bybit.com（2022-11 起） | `alpha/listing_history_bybit.py` |
| 各所对比表 | 中期结果已出 | `alpha/listing_compare.py` → `data/alpha/listing_compare.json` |
| Notion | 已建页，第六节是对比表 | https://app.notion.com/p/41bb72fc8cae81f386a8fc600c179214 |

交易所名单（大叔 11-17 定）：CoinGecko 交易所排名在 LBank（第 12 位）之前的，另加 Upbit、Bybit。Kraken 接口只给最近数据，做不了。MEXC、LBank 及之后的不要。

## 三、你怎么跑复盘（你的环境发不出网络请求，复盘必须在 GitHub Actions 上跑）

1. 改 `alpha/review/listing_run.json` 的 `runs`，写这次要跑的任务，推到 `codex/review`：
   - `"okx"` = 整所；`"bitget:2/4"` = 分片第 2 份 / 共 4 份；`"bybit"` 走归档。
   - `"limit": "20"` = 每份只试跑前 20 个币（先试跑看数字对不对，再清空跑全量）。
2. 推送后 GitHub Actions「各交易所全历史上币复盘」自动开跑；跑的脚本永远是 main 上的版本（你在 codex/review 上改脚本不会生效，要改脚本照常写进 `alpha/review/` 的复核文件或开 PR，Claude / 大叔合并后才生效）。
3. 跑完结果自动提交到 main 的 `data/alpha/listing_history_*.json` 和 `listing_compare.json`。`git pull` 后核对。
4. 汇总表的结果在工作流运行页的 Summary 里也能看到。

## 四、待办（按顺序）

1. **收 Upbit、Bybit 结果**：核对 n、起点类型（`ref_type`）、有没有「不能回溯」报错、异常起点价（比如起点价比首日均价低 10 倍以上）、批量上线日。
2. **Bitget 分片重跑**：`runs` 写 `["bitget:1/8","bitget:2/8",…,"bitget:8/8"]`，8 台机器并行。
3. **币安改名 / 迁移名单**（`alpha/review/x10_binance_renames.json`，之前派过的任务）：旧代码、新代码、生效日、官方公告链接。交上来后，复盘要剔除这些「假新币」（脚本改动请写清楚，Claude / 大叔合并）。
4. **核对每家所的数据质量**：抽查 10 个知名币的上线日和官方公告是否一致（之前发现 OKX 有 2020-01-01 的数据起点堆积，已用「同日 ≥ 8 个」规则剔除；OKX X 开头、Gate G 结尾是代币化股票）。发现新的异常写进 `alpha/review/listing_qc_<日期>.md`。
5. **更新 Notion 页**第六节两张表（如果你连得上 Notion；连不上就把更新后的表写进 `alpha/review/listing_notion_<日期>.md`，大叔贴过去）。

## 五、已知的坑

- 其它所（除 Binance、Bybit）只能查到现在还在交易的币，已下架的查不到，回报偏高。比较时用「Binance 只看现在还在交易的」那一行。
- 起点用开盘第 15 分钟价（大叔 11-17 定）；第一笔开盘价常有尖峰，只作上限读数。
- 「牛熊 × 涨跌腿」是事后划分；交易时能知道的是「当时已确认的腿」。
- Bybit 归档里有正式开盘前的零星成交（如 3P 首笔 0.00000001），脚本把开盘定义为第一个成交 ≥ 10 笔的分钟。
- 取消的工作流不会再提交结果（11-17 出过取消后仍提交半成品）。
- 规矩不变：拿不到写 U，不估不编；推 `codex/review`，不推 main；在 `docs/协作记录.md` 记一行。
