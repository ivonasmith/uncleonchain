# SEO 规范（2026-11-15 起）

所有会话（不管负责哪个板块）新建或改页面时都按这份来。基建（公共函数、sitemap、检查脚本）统一在 `pipeline/出网站.py` 里做，
各板块只按「板块约定」用它，**不要在自己的板块里另写一套 head / sitemap / 结构化数据**。

## 0. 现状（2026-11-15 核对）

已有：
- 全站静态生成（Python 出 HTML → Cloudflare Pages），不需要换 Next.js / Astro。
- `出网站.page()` 统一出 `<head>`：title、description、og / twitter 卡片、中英 hreflang 互指（`/` ↔ `/en/`）。
- `robots.txt`、`sitemap.xml`（出网站末尾的 `urls` 列表，中英各一条）。

缺口（按优先级，基建窗口逐条做，做完在这里打勾并写日期）：

| # | 缺口 | 影响 | 状态 |
|---|---|---|---|
| S1 | sitemap 是手写清单，漏了 `/core/`、`/rwa/` 及其子页、`/launchpad/cycle/` 等新板块；没有 `lastmod` | 新板块搜索引擎不知道 | ✅ 11-15：`page()` 登记自动生成，带 lastmod（正文指纹变了才更新日期，状态 `site/seo_lastmod.json`） |
| S2 | 普通页面没有 `rel=canonical`，hreflang 没有 `x-default` | 可能被当重复页 | ✅ 11-15：每页 canonical + x-default；英文 noindex 的页，中文页自动去掉指向它的 hreflang |
| S3 | 首屏关键内容靠 JS 取数：首页 / 宏观页「涨跌腿」卡片源码里只有「读取中…」，/core/、/alpha/ 由 JS 渲染 | 爬虫看到空壳 | 涨跌腿卡 ✅ 11-15（`出网站.leg_static`）；/core/、/alpha/ 交各自板块窗口 |
| S4 | /core/ 用 hash 路由（`#coin/UNI`），单币没有独立 URL | 单币页无法被收录 | 待做：交核心选币窗口出 `/core/<币>/` 静态页（传 `kind="dataset"`），hash 路由可保留做页内切换 |
| S5 | 没有 JSON-LD 结构化数据 | 拿不到富结果 | ✅ 11-15：首页 WebSite、日志 / 复盘 / 报告 / 文章 Article、指标详情 Dataset、其余 WebPage（按路径自动推） |
| S6 | 首页 / 宏观页 description 用当天结论句（含「不追高、风险预算打七折」） | 搜索摘要像操作建议，且天天变 | ✅ 11-15：首页 / 宏观 / 日志 / 周月复盘改成描述页面内容 |
| S7 | 没有主动推送收录（IndexNow） | 新页收录慢 | ✅ 11-15：`pipeline/indexnow.py`，daily.yml 定时运行推送当天变化的页面 |
| S8 | 正文提到指标 / 币名没有自动站内链接 | 权重传不到数据页 | 待做 |

## 1. 基建（统一由一个会话做，其它会话不要动这些函数的结构）

1. **`page()` 增加参数**（向后兼容，旧调用不改也能跑）：
   - 已上线（11-15），全部可不传：`kind`（不传按路径推：`/` home、`/journal/…` `/reports/…` 文章 article、`/macro/<key>/` dataset、其余 page）、
     `updated`（不传 = 正文指纹最后变化日）、`published`（不传 = 路径里的日期）、`noindex`（meta refresh 跳转页、404、英文页含 `ZH_ONLY` 自动 True）、
     `canonical`（镜像页指向正本，如 /launchpad/report/ → 当天存档页；镜像不进 sitemap）。
   - 新板块要出单实体页（单币 / 单协议）时传 `kind="dataset"`；文章类传 `kind="article"`。
   - description 超长自动在句号处截断（中文 150 字、英文 220 字符）。
2. **sitemap 自动收集**（✅ 11-15）：`page()` 每出一个页面就登记 URL + `updated`，不再维护手写清单；`noindex` 的不进。
3. **静态兜底**（涨跌腿卡 ✅ 11-15）：JS 渲染的卡片，出网站时先把关键读数（方向、天数、幅度、asof、层结论）写成纯 HTML 放在容器里，JS 加载后覆盖。
   不能只放「读取中…」。
4. **构建检查** `pipeline/seo_check.py`（✅ 11-15，出网站末尾自动跑，只警告不拦）：每页必须有唯一 title、description（中文 20～150 字 / 英文 40～220 字符）、canonical；
   正文可见文字不能只有「读取中…」；sitemap 里每个 URL 都存在文件；报告缺什么、在哪页。
5. **IndexNow**（✅ 11-15）：日更出网站后，把 `lastmod` 是今天的 URL 推一次（Bing / Yandex / Naver 等；Google 靠 sitemap + Search Console）。
6. **自动内链**（待做）：渲染 md（日志、报告、研究文档）时，按注册表指标名和 core / alpha 观测名单匹配，第一次出现加站内链接，每篇每个词只链一次。

## 2. 板块约定（每个会话都要遵守）

1. **新页面一律走 `page()`**，传有信息量的 `title` 和 `desc`，填 `kind` / `updated`。不要手写 `<head>`。
2. **title 格式**：`<页面主题> · 链上大叔研究台`，英文 `… · Uncle Onchain`。单币 / 单协议页可以带一个关键读数，**必须同时带日期**，
   例如「Polymarket 协议收入（30 天 $18.7M，截至 11-14）· 链上大叔研究台」。
3. **description 写这页是什么、有哪些数据**，不写当天结论，**不写任何操作性措辞**（追高 / 抄底 / 仓位 / 止损 / 买卖）。
4. **实体级内容要有真实路径**：单币 `/core/<币小写>/`、单协议 `/alpha/<slug>/`、发射台 `/launchpad/platforms/<slug>/`。
   不要只用 `#…` 或 `?tab=`；hash 可以保留做页内切换，但每个实体至少有一个静态页。
5. **首屏关键数字在出网站阶段写进 HTML**（见基建 3），JS 只负责交互和刷新。
6. **少而实**：只有有实质读数的实体才单独出页；只有一行数字的不出页（薄页会拉低全站质量）。
7. **中英文都要出**，英文页 `T(中, 英)` 文案齐全；英文没翻译的页在正文放 `ZH_ONLY` 提示，`page()` 会自动 noindex（11-15 实测 63 页：Alpha / RWA / 部分 AI Agent / 往期发射台日报）。
   翻译补齐后去掉 `ZH_ONLY`，就自动回到索引里。
8. **改 URL 要留跳转**：旧路径在 `_redirects` 或跳转页里 301 / meta refresh 到新路径，并在新页 canonical 指向自己。
9. 出网站末尾会打印「SEO 检查：N 页，M 条警告」，推送前看一眼，新增的警告自己修掉（11-15 基线 = 0 条）。

## 3. 不做的

- 不为 SEO 写软文、不堆关键词、不出没数据的落地页。
- 不改 YMYL 红线：不给买卖建议，免责声明和数据来源保留在页面上。
- 不追标题里的实时价格（数字天天变，搜索结果里会对不上）。
