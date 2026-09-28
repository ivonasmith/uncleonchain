# 链上大叔研究台（uncleonchain.com）

个人 web3 链上数据研究站：宏观流动性 → BTC/ETH → 板块轮动 → 发射台 / 低位叙事。

## 目录结构

```
pipeline/    数据抓取与看板/网站生成脚本（中文文件名，逐脚本单一职责）
data/        逐日累加的台账（估值序列、PONS 销毁记录等），每天由 GitHub Actions 提交
content/posts/  手写文章的 Markdown 源（macro / rotation / narrative 三个板块）
site/        生成的静态网站，Cloudflare Pages 直接从这个目录发布
.github/workflows/daily.yml   每天定时跑 pipeline，提交 data/ 和 site/
```

## 本地跑一遍

```bash
export LP_DATA=$PWD/data LP_OUT=$PWD/build
python3 pipeline/跑日更.py --site      # 拉数 → 出看板 → 出网站，写入 data/ 与 site/
```

## 发布新文章（宏观 / 板块轮动 / 叙事币埋伏）

看 `content/posts/README.md`。发射台日更是全自动的，不用管。

## 运维手册

`pipeline/RUNBOOK.md` 是 Claude 会话侧（看板发 Artifact + Notion + 聊天推送）的操作手册；本仓库到网站这条线
是全自动的，见上面的 workflow，不需要按那份手册操作。

本站只给数据和复盘记录，不构成任何投资建议。
