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
- `pipeline/宏观规则.py`：四层框架（流动性 / 周期 / 筹码 / 情绪）的指标注册表、区间规则、层结论、预警、日志与周月复盘生成。
  规则改动要在「更正记录」留痕，已写入的历史日志不改。
- `data/解读日志/{日,周,月}/`：写入即冻结。同日重跑且核心缺失变少才覆盖并标「补录」。
- `content/posts/<macro|rotation|narrative>/`：手写文章（.md 或整篇 .html）；`content/journal/<日期|周|月>.md`：人工点评。
- `assets/`：头像、favicon、og 卡（`pipeline/做图标.py` 生成），`assets/vendor/html2canvas.min.js` 由 Actions 自托管。
- 视觉：底 #05070c、卡片 #0b0e17、1px rgba(255,255,255,.06) 细线、涨 #00ffcc、跌 #ff3366、品牌青柠 #a3e635（只用于导航和按钮）。
  左侧常驻导航，每个板块独立 URL（方便推特直链）。

## 待办（按优先级）

1. 核对 Actions 首跑：宏观各数据源（DefiLlama 稳定币、FRED CSV、Deribit、CoinMetrics Community、alternative.me、Hyperliquid、CoinGecko）
   在 GitHub runner 上是否都通；看 `data/宏观台账.json` 的「源状态」和线上 /macro/ 页。第一篇日志应是 2026-09-29。
2. 宏观 v2：BTC 现货 ETF 净流入、Coinglass（多空比 / 爆仓，需 key）、Deribit 期权 P/C 与 IV。
3. 叙事雷达：DefiLlama 无代币协议 × 收入增速筛选；Robinhood Chain / Arc 发射台大户地址追踪。
