# 链上大叔研究台（uncleonchain.com）

个人 web3 链上数据情报终端：宏观四层仪表盘（流动性 → 周期 → 筹码 → 情绪）→ 发射台矩阵 → 板块轮动 → 叙事埋伏，
每天一篇规则化解读日志（写入即冻结），每周 / 每月自动复盘，全部公开。

## 目录结构

```
pipeline/    数据抓取与看板/网站生成脚本（中文文件名，逐脚本单一职责）
             拉宏观.py 宏观四层数据 · 宏观规则.py 指标注册表与区间规则 · 写日志.py 每日解读 + 周/月复盘
data/        逐日累加的台账（估值序列、PONS 销毁、宏观台账、发射台矩阵、板块快照、解读日志），每天由 GitHub Actions 提交
content/posts/    手写文章（macro / rotation / narrative 三个板块）
content/journal/  解读日志的人工点评（可选）
assets/      头像、favicon、分享卡片（pipeline/做图标.py 生成）
site/        生成的静态网站，Cloudflare Pages 直接从这个目录发布
.github/workflows/daily.yml   每天定时跑 pipeline，提交 data/ 和 site/
```

## 本地跑一遍

```bash
export LP_DATA=$PWD/data LP_OUT=$PWD/build
python3 pipeline/跑日更.py --site      # 拉数 → 出看板 → 出网站，写入 data/ 与 site/
```

## 发布新文章（宏观 / 板块轮动 / 叙事币埋伏）

看 `content/posts/README.md`；给某天的解读日志加人工点评看 `content/journal/README.md`。其余全自动。

## 运维手册

`pipeline/RUNBOOK.md` 是 Claude 会话侧（看板发 Artifact + Notion + 聊天推送）的操作手册；本仓库到网站这条线
是全自动的，见上面的 workflow，不需要按那份手册操作。

本站只给数据和复盘记录，不构成任何投资建议。
