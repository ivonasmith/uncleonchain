# unclechain.com · AI Agent 交接包

本包交付客户版核心指标页、采集代码、历史种子和每日更新工作流模板。尚未修改 unclechain.com 的 GitHub 仓库，也未部署或新增在线定时任务。完整ZIP已含private-seed.tar.gz；轻量代码ZIP不含该大文件，须搭配同目录的历史种子。把完整ZIP或交付目录路径交给Claude Code即可。

## 页面目标

左侧现有列表新增「AI Agent」，目标路由 /ai-agent/。保留网站现有侧栏和布局。页面只展示六项：累计 Agent ID、每日新增 Agent ID、每日交易地址数、每日曲线成交额（BNB）、每日新发币数、每日毕业数。每项都有趋势，可切换近7天、30天、全部。未知保留U、断点；不发布当天未结束的数据。

注册为全注册表。交易、成交额及发币目前只覆盖 AgentPad，已在卡片、趋势图和范围说明中标明，不冒充全生态。交易地址是买入/卖出事件去重，不能把仅铸造或领取的地址算进来。合约参数、RPC、税率、原始响应、证据表和缺口报告继续在运行目录保存，不塞进普通客户首页。

## 包内结构

- public/ai-agent/monitor/：可立即托管的客户页、精简日序列、健康状态。六张客户趋势内嵌页面，原8张研究PNG在私有后台保留。首页内嵌数据，CSS/JS使用同目录静态文件，无CDN依赖；本包版本的数据截止日期见页面。
- integration/：侧栏条目、React路由嵌入示例、需合并的Cloudflare缓存头。没有站点仓库，故示例不假定真实路由文件路径。
- tools/agent-id/collector/：完整A–G采集、证据与后台报告代码；保留原25个合成测试。
- tools/agent-id/export_site.py：只读本地输出，额外核对事件笔数和BNB金额后导出客户数据，同时在私有运行目录保存customer_metrics_audit.json/tsv逐项证据。
- tools/agent-id/test_export.py：8个客户指标导出场景测试。
- tools/agent-id/update_daily.py：复制代码到持久运行目录、运行测试和昨日采集、离线报告、客户导出；文件锁防重入。
- workflow-templates/agent-id-daily.yml：GitHub每日UTC00:20和手动更新模板。尚未安装到.github/workflows。
- private-seed.tar.gz：另附的后台运行种子，含state、raw、data和完整研究报告；不放进public，不提交普通Git，不上传Cloudflare静态资产。

## 给 Claude Code 的落地步骤

1. 在用户已有 unclechain.com GitHub 仓库内阅读自身AGENTS/README，确认框架、现有侧栏配置、构建输出和Cloudflare Git绑定。不要另造站点，不覆盖现有侧栏和_headers。
2. 合并tools/agent-id及public/ai-agent/monitor；按实际框架把 /ai-agent/ 放进网站共享布局。React可参考integration/AI-Agent.tsx；Vue/Astro等使用相同iframe路由或原生适配。侧栏显示「AI Agent」。不要给该入口加钱包连接。
3. 本地构建检查桌面/手机、6项数字、六张图、日期、范围标签和按钮。公开目录不得包含state.json、raw、私有报告、凭证或钱包会话。同源CSS/JS无需放宽全站CSP；若现有站点框架有额外资源策略，按现有策略适配。
4. 配置一个长期在线的self-hosted GitHub Runner，标签agent-id。Python3.10+，安装requirements.txt；Linux安装fonts-noto-cjk以使后台PNG中文可读。用venv时须把其Python放在Runner PATH中。首次安装依赖在Runner外完成，定时任务不会每次下载依赖。
5. 在checkout外创建私有持久目录，例如 /srv/agent-id/runtime，将种子解压到该目录（归档顶层直接为state.json等）。不要用Runner checkout保存历史，避免checkout clean删除缓存。若先手动接通而尚未切换时钟，只跑--report-only，不能并行启动第二个每日采集。
6. Repo Variable AGENT_ID_RUNTIME 设置为该目录的绝对路径；Repo Secret AGENT_ID_PROXY 设置为此Runner实际可达的完整HTTP代理URL。用户电脑7980或本机旧7890都不是另一台Runner必然可达的地址。没有代理禁止联网，不改成直连；即便在云上也保留此规则。代理若含凭证，后台配置/raw按私有运行数据管理。
7. 首先手动离线演练命令：python3 tools/agent-id/update_daily.py --runtime /srv/agent-id/runtime --output public/ai-agent/monitor --report-only。校验原25项和额外8项测试通过，再构建网站。该命令不会把页面日期伪更新成今天。
8. 正式单时钟切换：确认Runner、代理、数据基线和Cloudflare构建都就绪后，先在Codex把已有 monitor-agent-id 定时任务暂停/停用，再把唯一模板安装到.github/workflows/agent-id-daily.yml。启用后手动触发一次，观察Git数据提交、Cloudflare部署和线上核心数据日期一致。不要另外加CF Cron或系统cron。未切换前本地任务继续，模板不算已启用。迁移完成后告知用户只剩哪一份定时器在运行。
9. 定时执行前一完整UTC日，提交public/ai-agent/monitor的生成产物；由用户既有Cloudflare Git集成部署。GitHub定时触发可能排队，页面展示真实数据截止日，不承诺00:20整点可见。仓库需允许工作流写入生成文件；分支保护有冲突时按现有发布流程调整，不自动关闭保护。
10. 若过去漏日，自动日更不要偷偷扩大为回填；先在gaps记录。恢复旧日需单独按既有--backfill口径重算，不能跳日造累计。采集成功但来源不足可以发布U；脚本/测试/文件校验失败则保持现有公开产物，先修复。

## 常用命令（在网站仓库根目录）

```sh
python3 -m pip install -r tools/agent-id/requirements.txt
python3 -m unittest discover -s tools/agent-id -p 'test_export.py' -v
python3 tools/agent-id/export_site.py --runtime /srv/agent-id/runtime --output public/ai-agent/monitor
python3 tools/agent-id/update_daily.py --runtime /srv/agent-id/runtime --output public/ai-agent/monitor
```

最后一条需要AGENT_ID_PROXY环境变量。只处理前一完整UTC日。全量raw用于重算，不应被公开页面加载。浏览器端不会连接RPC，不会连钱包，不会签名或交易。

## 当前采集边界

B/D至少两个不同平台系列的完整数据仍未达标；目前不能把交易和发币叫全生态总量。HashDroids、Ptah等铸造活动保留在后台E/G模块，未混入交易地址。AgentPad创建者有ID豁免，所以创建数不表述成「每个创建者都持Agent ID」。所有原始未知和价格冲突规则保留。

## 核验依据

Cloudflare Pages单文件上限25MiB，导出器自动检查。大型运行种子不作为Pages资产。
https://developers.cloudflare.com/pages/platform/limits/
GitHub schedule在默认分支运行并可能延迟；workflow_dispatch支持手动演练。
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow

说明编写日期2026-10-29；不等于研究数据更新日。文件浏览器预览因本次工具的file协议策略未执行；不绕过，使用静态检查及本地脚本测试，最终真实站点视觉验收由仓库接入方完成。
