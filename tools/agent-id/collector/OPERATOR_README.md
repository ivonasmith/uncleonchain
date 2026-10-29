# Agent ID 只读监控运行说明

研究数据日期以 dashboard.html 的 UTC 标记为准。HTML 生成时间不是数据更新日。身份层已完成全序列回填和对账：2026-10-19 至 2026-10-28，132,038 条注册，132,038 个独立持有地址，10/10 ownerOf 抽样一致。B/D 至少两个不同平台系列的真实日数据仍未达标，详见 validation.json。文件校验通过不代表数据齐全。

## 一键运行

在本目录运行：

    python3 monitor_agent_id.py --backfill
    python3 monitor_agent_id.py --daily
    python3 monitor_agent_id.py --report
    python3 monitor_agent_id.py --backfill --reprocess
    python3 -m unittest discover -s tests -v

--backfill 从已观察起点到前一完整 UTC 日逐日处理，已有行默认保留。--daily 仅处理前一完整 UTC 日。--report 完全离线。--reprocess 按已缓存原始响应重算已有行，不清缓存、不改变链上口径。JSON 的 null 在审阅输出显示 U。Python 依赖 matplotlib、numpy；当前执行环境已验证可用。不要把本地日历的“昨日”直接当作 UTC 昨日。

## 证据和重算

raw/http 的请求信封保存实际 URL、JSON-RPC 方法及参数、代理、读取时间、完整响应、重试过程和缓存键。成功与失败均缓存；相同精确请求和 scope 重跑命中缓存。每日变化状态使用 UTC 日 scope，历史区块请求使用 immutable scope。历史失败不会被替换成零；原始失败保留。raw/ 另有本次人工核验的来源原文，不使用旧 C28 响应冒充本次请求。

facts.txt 是每行以 | 分隔的事实表；facts.tsv 是五列事实表；facts.json 增加 raw 路径、区块和 RPC。读取时间来自原始请求信封，不能用报告生成时间替换。E1 为可复算链上记录；E2 官方资料；E3 第三方数据或媒体；E4 社区、第三方 README、目录候选及明确标记的启发式代理。Sourcify exact_match 证明源码与字节码精确匹配；match 为含允许差异的匹配，单列匹配类型。默认只接受 runtime 和 creation 均 exact_match；Ptah POA 明示单独采用双 match 核验政策。代理壳验证不代替实现源码验证。验证源码不自动证明产品门禁或事件全集，也不等同于 BscScan 页面核验通过。

## 范围和口径

A 只称 Agent ID 持有地址，Agentic Wallet 总量另列 U。注册表实际事件是 Registered、AdminRegistered 和 mint Transfer；未发现 NameRegistered。已从部署区块完整读取首条注册之前的空前缀，确认首条注册在 UTC 2026-10-19（区块128506365），与用户提供待核的2026-10-20上线说法并列标注冲突；后者原文链接仍U。命名序列比例为 E4 启发式。

B 按版本与工厂分轨；先核验源码、事件、过滤条件和全集完整性才启用。AgentPad 创建者有身份豁免，其工厂创建数不等于“纯 Agent ID 买家发币数”。源不完整不算毕业率，队列未满窗口 U，空分母 U。

C 全生态指标必须覆盖配置产品且活动身份可核实；当前全生态数值为U。另列已核产品 observed_active_id_wallets 和 observed_activation_lower_bound，附覆盖产品范围与身份未核地址数；覆盖范围变化时不直接计算跨期方向。成交集中度按 BNB 计价；非 BNB 不拼入。

AgentPad 使用已验证工厂创建的子合约源码与完整 Buy/Sell/Graduated 事件。买卖成交 BNB 均扣除平台费；转账税率与曲线手续费分别记录。毕业价依 Solidity 整数运算，不能四舍五入替代。工厂旧版当前零项目不充作第二个平台。

D D0 暂定毕业所在 UTC 日收盘；首个 DEX 价单列，不能拿日 K 开盘替代首笔成交价。GeckoTerminal 同池同资产同来源，按日保存跨运行的价格观察值，两价冲突 U，不跨池拼接；USD 转换另用币安 BNBUSDT 闭合日 K。当前项目 API 快照为“未完”，独立列出，不回写成历史日末状态。未毕业样本也保留，样本不足 5 不报中位数。

E 非曲线铸造和领取分项。HashDroids 只有完整最近 24h 计数及剩余量已知才线性外推，标 E4 代理。外推不是承诺时间。

F 当日抓取时保存哈希，首次成功只建立基线。变更日期为实际检测 UTC 日，不能回填成昨日的已知变更。差异片段最多 200 字。缺页或历史基线未知为 U。

G 候选目录与 GitHub 搜索分别记录。只核实的 Agent ID 门禁项目进入确认分母；未核候选不冒充免费或已确认项目。逐日保留源码验证、价格、管理员改价/暂停、授权/typedData、首个挂牌、D0/D1/D3/D7 地板和成交笔数。合约 mint 路径无需 typedData 不证明前端永远不会请求额外签名，前端未知另记 U。地板必须是实际挂牌地板，不拿最后成交、DEX 价或 Transfer 替代。免费转付费和跌幅 >90% 只有同源可比较时点才标记；缺地板仍保留。地板 D0 起点尚待确认，不代填。全部期初/期末缺失时均 U。当前已核4项是核实子集；生态项目总分母和全生态地板可用占比仍U，不能把子集0/4称作生态比例。

## 网络和定时

本执行环境实测代理为 config.json 的地址；它不是用户电脑 VPN 的 7980 端口。没有代理直连后备。当前主序列统一使用 https://rpc-bsc.blockmachine.io，旧48.club序列单独保存在data/source_series，不拼接；两源重叠4日的新增数一致。该RPC最多10000区块/日志查询，60CU/分钟；采集串行间隔至少1.2秒，HTTP200的RPC限流错误也按服务端retry_after_ms退避，最多3次重试。403/429 在原地址退避重试 3 次，仍失败记缺口；验证码/Cloudflare 挑战立即记“被拦”，不点击、不绕过。只使用只读 RPC 方法，不含钱包连接、签名、下单或广播。

已创建一个聊天定时任务 monitor-agent-id，每日 UTC 00:20（Asia/Singapore 08:20）运行。任务仅处理昨日完整日，定时器由 Codex 桌面应用管理；需应用运行并具备执行环境。脚本不安装其他定时器、不触发交易或外部消息。未变化安静，实质采集/校验故障在本聊天报告。

## 文件

dashboard.html 是内嵌全部图的离线单文件；charts/ 保存 8 张 PNG。daily_summary.html 为每日值和前 7 日均值方向；gaps.html 是逐日原因；validation.json 区分通过与未达标；test_log.txt 是25个真实合成测试日志；artifact_verification.html 校验raw哈希、实际请求URL/UTC时间、文件引用、8张图和缓存零请求复跑。data/ 保存日表、队列表、候选快照、铸造登记与规则差异。完整读到的零计数才为 0，图上缺失画断点，不填零、不连线。

## U的计数口径

U_count 为五列事实表中整项值为U的行数，不把结构化字段内部的每个U再重复计数；分子、分母、价格等已尽量各自单列。未发布当天数据不进入趋势。源码/门禁未核验的候选逐项列出原因，不据缺失数据补零。
