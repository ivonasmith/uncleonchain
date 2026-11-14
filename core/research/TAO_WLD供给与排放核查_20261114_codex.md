# TAO 与 WLD 供给及排放机制核查

**核查截至 2026 年 11 月 14 日，并非截至 11 月底。** 下表区分官方规则、第三方链上统计及计算值；“未查到”不代表数量为零。

两个关键区别：**TAO 排放与 alpha 奖励不是同一种代币；WLD 解锁与新增流通不是同一件事。** 未来解锁量也不能直接当作卖出量。

## 一、TAO（Bittensor）

| 项目 | 数值／核查结果 | 截至日 | 来源链接 | 备注 |
|---|---|---|---|---|
| 最大供给 | **2,100 万 TAO** | 核查日现行文档 | [官方·Money](https://www.bittensor.com/docs/concepts/money) | 每个子网的 alpha 另有自己的供给上限，不能与 TAO 相加 |
| 当前总发行量 | **11,724,278.0916 TAO** | 2026-11-13 UTC 日末，区块 9,500,887 | [第三方·Bittensor.ai 链上统计](https://bittensor.ai/explorer/stats) | `TotalIssuance`，包含质押及池内资产；是扣除 recycling 后的发行计数，不是历史累计毛铸造量 |
| 发行量的其他数字 | 官方排放页面示例显示 **11,222,524.60 TAO**；CoinGecko 显示约 **1,172.5 万** | 官方示例时间未标明；CoinGecko 为核查日读取 | [官方·排放](https://www.bittensor.com/docs/concepts/emissions)、[第三方·CoinGecko](https://www.coingecko.com/en/coins/bittensor) | 官方示例缺少快照时间，不能将其当成 11 月实时数据；CoinGecko 数字经过四舍五入 |
| 当前流通量 | CoinGecko：约 **1,172.5 万 TAO**；按官方“排除质押和池储备”的定义，当前精确值**未查到** | 2026-11-14 | [第三方·CoinGecko](https://www.coingecko.com/en/coins/bittensor)、[官方·供给定义](https://www.bittensor.com/docs/concepts/money) | CoinGecko 把大量已质押 TAO 也计入流通。不能将“未质押余额”直接改称官方流通量 |
| 减半规则 | 发行计数达到 **1,050 万、1,575 万、1,837.5 万……**时减半 | 核查日 | [官方·排放](https://www.bittensor.com/docs/concepts/emissions) | **按供给阈值，不是固定每四年或固定区块数**；回收可再次发行的 TAO 会推迟阈值到达 |
| 已发生减半日期及冲突 | 官方确认 **2025 年 12 月**首次减半；Taostats 记为 **2025-12-15，区块 7,103,976**；Grayscale 文件写 **2025-12-13** | 历史事件 | [官方·排放](https://www.bittensor.com/docs/concepts/emissions)、[第三方·Taostats](https://taostats.io/tokenomics)、[第三方·Grayscale 提交 SEC 的年报](https://www.sec.gov/Archives/edgar/data/2029297/000119312526104209/tao-20251231.htm) | 日期不一致，均列出。SEC 收录的基金文件不是 Bittensor 官方公告，也不是 SEC 对其中日期的认证 |
| 当前每日新增 | **0.5 TAO／区块；约 3,600 TAO／日毛排放** | 核查日 | [官方·排放](https://www.bittensor.com/docs/concepts/emissions) | 按约 12 秒一块、每日 7,200 块计算 |
| 实际每日净增 | **3,245.6835 TAO** | 2026-11-13 UTC 全天 | [第三方·发行量变化](https://bittensor.ai/explorer/stats) | 这是当日 `TotalIssuance` 净变化；不同于 3,600 的理论毛排放 |
| dTAO 上线日期 | **2025-02-13**；本次未查到可直接回溯的项目官方上线公告 | 历史事件 | [第三方·DeSpread](https://research.despread.io/dtao/)、[生态工具方·TAO.app 文档](https://www.tao.app/developer/subnet-data)、[官方·dTAO 白皮书](https://www.bittensor.com/dtao-whitepaper) | 日期有第三方及工具方依据；官方白皮书用于核实机制，不将其冒充上线日期出处 |
| 新增 TAO 怎么分 | dTAO 后，新增 TAO 进入子网经济／池机制；参与者主要取得该子网的 **alpha 奖励** | 核查日 | [官方·dTAO 白皮书](https://www.bittensor.com/dtao-whitepaper)、[官方·排放](https://www.bittensor.com/docs/concepts/emissions) | **不能直接写成每天 3,600 TAO × 18%／41%／41%** |
| 子网所有者／矿工／验证者与质押者 | 默认 alpha 分配：**所有者 18%、矿工 41%、验证者及其质押者合计 41%** | 核查日 | [官方·Emission weights](https://www.bittensor.com/docs/concepts/emission-weights) | 当前已可按子网调整：所有者最高 33%、矿工最低 33%、验证者最高 50%；另有 burn、recycle、gamma 等分配项。18／41／41 是默认值，不是所有子网永久统一值 |
| 质押者独立占比 | **没有全网固定的第四个百分比** | 核查日 | [官方·Emission weights](https://www.bittensor.com/docs/concepts/emission-weights) | 质押者从验证者奖励中分配，扣除验证者 take；root 与 alpha 质押权重也影响结果，不能再加一个“质押者 41%” |
| Root 质押奖励 | 有子网 alpha 排放形成的收益；Root Reborn 将其纳入验证者管理的篮子，按规则领取 | 2026 年 7 月官方升级说明 | [官方·Root Reborn](https://www.bittensor.com/releases/v441-upgrade) | **属于代币排放收益，不等于外部客户收入分红**；该文约 936 TAO／日等数字是当时快照，不作为当前值 |
| 当前质押数量及比例 | 约 **747.54 万 TAO 等值、63.76%** | 2026-11-13 UTC 日末 | [第三方·Bittensor.ai](https://bittensor.ai/explorer/stats) | 数量为本文计算：11,724,278.0916 × 63.76%；因比例被四舍五入，数量也是近似值 |
| 质押比例的其他数字 | Taostats：**63.73%，基数约 1,173 万**；tao.eco：**63.70%** | 核查日不同快照 | [第三方·Taostats](https://taostats.io/tokenomics)、[第三方·tao.eco](https://tao.eco/network) | 快照时间及统计细节不同，不强行统一成同一精确值 |
| Root 与子网池 TAO | Root 约 **551 万 TAO**；子网池约 **196 万 TAO** | 2026-11-14 09:04 UTC，区块 9,503,608 | [第三方·tao.eco](https://tao.eco/network) | 这是上述广义质押统计的组成，**不能再把池内 196 万加在总质押之上**。池储备也不等于固定期限锁仓 |
| 协议收入是否回流 TAO | **有交易费／注册成本回收影响当期供给；未查到外部业务收入统一回购 TAO 或向全体持有人分红的机制** | 核查日 | [官方·Money](https://www.bittensor.com/docs/concepts/money) | Recycling 会降低发行计数、以后可重新发行；永久 burn 不可重新发行。池 swap fee 则付给区块作者，不能统称全体持有人分红 |
| 子网 alpha 回购 | 存在；但回购对象通常是**子网 alpha，不是 TAO** | 2026-11-14 | [第三方·回购看板](https://tao.eco/revenue) | 看板记录约 23 天、7 个子网使用 **6,292.99 TAO** 买入并销毁 alpha。链上买入可验证，但资金是否全部来自外部客户收入仍需额外证明 |
| 子网对外收费：Chutes SN64 | 官方确认有按量付费；可选 Plus **10 美元／月**、Pro **20 美元／月**。当前完整月收入：**未查到** | 官方价格页核查日读取 | [子网官方·价格](https://www.chutes.ai/pricing)、[子网官方·经营更新](https://chutes.ai/news/from-volume-to-value-building-a-sustainable-ai-inference-platform-2) | 定价证明有收费业务，不能据此推算总收入 |
| Chutes 历史收入补充 | 第三方记录 2026 Q2 收入约 **137 万美元**，折合月均约 **45.7 万美元** | 2026 Q2 | [第三方·DefiLlama](https://defillama.com/protocol/chutes?events=false&fees=true&tvl=false) | 月均为本文计算，**不是某个自然月实收，也不是 11 月收入**；其页面“成本为零”字段不能当作真实经营成本为零 |
| 其他子网月收入 | Targon SN4、Lium SN51、Almanac SN41：本次**未查到可直接核实的当前官方自然月收入** | 核查日 | [第三方·SubnetAtlas](https://www.subnetatlas.com/)、[第三方·tao.eco](https://tao.eco/revenue) | 第三方有年化值，例如 Targon 约 810 万美元／年、Almanac 约 40 万／年；另一个看板列 Lium 530 万／年。均不能替代官方月度收入报表 |
| 前十大地址／冷钱包占比 | 前十合计 **2,355,235.6806 TAO 等值，占发行量约 20.09%** | 2026-11-13 UTC 日末 | [第三方·前十大榜单](https://bittensor.ai/explorer/accounts)、[第三方·同日发行量](https://bittensor.ai/explorer/stats) | 本文加总及计算；排名按自由余额＋保留余额＋质押按池价估值。包括普通地址，不主动剔除交易所；**交易所身份完整核验未查到**。不是十大最终受益人占比 |
| 基金会／团队预分配 | 官方称 **无预挖、无 ICO、公平启动** | 2023-09-20 官方历史说明 | [官方·TAO Token Economy Explained](https://blog.bittensor.com/tao-token-economy-explained-17a3a90cd44e) | 无预分配不等于创始人／基金会后来没有挖矿、验证或买入所得 |
| 基金会／团队当前持有及锁仓 | 合并持有量、全部关联地址、统一锁仓表：**未查到** | 核查日 | [官方历史说明](https://blog.bittensor.com/tao-token-economy-explained-17a3a90cd44e)、[第三方·透明度汇总](https://blockworks.com/token-transparency/filing/bittensor) | 不将“没有团队预分配”推导为“团队持仓为零” |

前十榜单使用的地址缩写依次为：`5HDzD…5VGr`、`5Hd2z…pg4N`、`5HMtF…8CCx`、`5Gs1z…kUNA`、`5HeWF…r7qc`、`5HbUB…J329`、`5GaTC…y3iJ`、`5FEA1…goCL`、`5ChHT…VDCi`、`5Hive…FLCv`。完整地址和各自余额可从[同日榜单](https://bittensor.ai/explorer/accounts)进入；alpha 按现价折算的余额不保证能按该价格全部退出。

## 二、WLD（Worldcoin／World）

未来 12 个月采用 **2026-11-15 至 2027-11-14**。日历中的数量为官方公布的**约 160 万／日社区解锁＋约 130 万／日团队和投资人解锁**乘以天数，属于近似计算；**不是新增流通预测，也不是完整的所有私募合同解锁清单**。

| 项目 | 数值／核查结果 | 截至日 | 来源链接 | 备注 |
|---|---|---|---|---|
| 最大供给 | 初始／前 15 年供给上限 **100 亿 WLD**；**不是永久固定上限** | 核查日 | [官方·白皮书](https://whitepaper.world.org/designing-for-scale/2026-03-24) | 最早 2038-07-24 04:00 UTC 后可由治理启用年增发，最高 1.5%，默认 0% |
| 当前流通量 | 约 **37.85 亿 WLD**，约占初始供给 **37.85%** | 2026-11-14 读取 | [第三方·CoinGecko](https://www.coingecko.com/en/coins/worldcoin) | 本次未从官方 Dune 动态页面取得同一时点可复核数值，不将第三方数据冒充官方实时数 |
| 最近查到的官方供给快照 | **49 亿已解锁，其中 33 亿流通** | **2026-04-10** | [官方·解锁速率公告](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 是历史官方数值，不是 11 月数据 |
| 当前未解锁量 | 第三方模型：已释放约 **58.1 亿**；对应未解锁约 **41.9 亿** | 2026-11-14 | [第三方·Token Radar](https://tokenradar.ai/tokens/worldcoin/tokenomics) | 41.9 亿为本文以 100 亿减 58.1 亿计算；官方同日精确值**未查到** |
| 未流通与未解锁的区别 | 未流通约 **62.15 亿**，不等于上述未解锁约 41.9 亿 | 核查日 | [第三方·CoinGecko](https://www.coingecko.com/en/coins/worldcoin)、[官方·定义](https://whitepaper.world.org/designing-for-scale) | 已解锁、但仍受基金会分配决策约束的代币，可以尚未流通 |
| 分配比例：现行披露 | **社区 75%／75 亿；团队及其他开发贡献者 11.1%／11.1 亿；TFH 投资人 13.6%／13.6 亿；TFH 储备 0.3%／3,000 万** | 白皮书注明该比例截至 2025-04-28 | [官方·现行分配表](https://whitepaper.world.org/designing-for-scale) | 社区 75% 不代表 75% 已经发给用户 |
| 分配比例：历史版本 | **社区 75%；初始开发团队 9.8%；投资人 13.5%；储备 1.7%** | 2023-12-11 版 | [官方·历史白皮书](https://whitepaper.world.org/designing-for-scale/2023-12-11) | 与现行版本不同。官方说明变化发生在团队＋投资人＋储备合计 25% 内 |
| 团队／投资人解锁规则 | 约 80% 在一年完全锁定后，分 **48 个月**线性解锁；约 20% 分 **24 个月**线性解锁；绝大部分至 2028 年 7 月结束 | 2024 年调整后的规则 | [官方·延长锁定公告](https://world.org/blog/announcements/extended-lock-up-for-tfh-team-and-investors)、[官方·白皮书](https://whitepaper.world.org/designing-for-scale) | 个别团队成员还有与任职期限相关的 vesting；不能把全部团队代币视作同一天可卖 |
| 当前常规解锁速度 | 官方约 **290 万／日**：社区约 160 万，团队＋投资人约 130 万 | 2026-07-24 起 | [官方·速率公告](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 此前约 510 万／日；降速约 43%。团队与投资人分别的官方精确日速率**未查到** |
| 解锁速度的其他数字 | 第三方模型约 **295 万／日**，其中约 135 万为模型估计的团队／投资人部分 | 2026-11-14 | [第三方·Token Radar](https://tokenradar.ai/tokens/worldcoin/tokenomics) | 与官方 290 万的约数不同，保留两种数字；不能将两个口径混用 |
| 日历：2026-11-15—11-30 | **4,640 万**＝社区 2,560 万＋团队／投资人 2,080 万 | 未来，16 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性；以下均为相同基准 |
| 日历：2026-12 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-01 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-02 | **8,120 万**＝4,480 万＋3,640 万 | 未来，28 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-03 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-04 | **8,700 万**＝4,800 万＋3,900 万 | 未来，30 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-05 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-06 | **8,700 万**＝4,800 万＋3,900 万 | 未来，30 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-07 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性；不含下述另售代币解禁 |
| 日历：2027-08 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-09 | **8,700 万**＝4,800 万＋3,900 万 | 未来，30 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-10 | **8,990 万**＝4,960 万＋4,030 万 | 未来，31 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 日历：2027-11-01—11-14 | **4,060 万**＝2,240 万＋1,820 万 | 未来，14 天 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 每日线性 |
| 未来 365 天常规解锁合计 | 约 **10.585 亿**＝社区 5.84 亿＋团队／投资人 4.745 亿 | 上述窗口 | [官方规则／本文计算](https://world.org/blog/announcements/tokenomics-milestone-wld-unlock-rate-to-decrease-by-43-in-july) | 采用官方四舍五入日速率；不能视为精确合约解锁量 |
| 储备及额外私募日历缺口 | 储备具体日期**未查到**。第三方报道 2026 年 7 月有 **5,250 万美元**代币销售、锁一年，但代币枚数和逐笔到期日**未查到** | 核查日 | [官方·储备规则](https://whitepaper.world.org/designing-for-scale)、[第三方·销售报道](https://thepaypers.com/fraud-and-fincrime/news/world-raises-usd-525-million-via-crypto-sale-to-strategic-investors) | 储备从实际分配起至少锁一年，再线性两年；不能按美元募资额猜代币数量，也不能认定全部在 2027-07-24 一次解禁 |
| 用户发放规则的重要变化 | **2026-06-01 起停止新建和续期空投周期**；已有合资格周期继续按月领取，至其 12 个月周期结束 | 官方帮助中心核查日版本 | [官方·空投计划更新](https://support.world.org/hc/en-us/articles/30969185598739-Updates-to-the-Airdrop-Program) | 新验证用户不再自动符合该空投计划。不能沿用旧白皮书“持续领取”的叙述估算当前发放 |
| 每日／每月实际新增流通 | **当前完整合计未查到** | 核查日 | [官方·空投更新](https://support.world.org/hc/en-us/articles/30969185598739-Updates-to-the-Airdrop-Program)、[官方·流通看板入口](https://dune.com/world/world) | 需合并实际领取、团队／投资人释放、运营支付、销售、借币及归还等，避免重复。**290 万／日是解锁，不是流通净增；用户领取也不能简单叠加在社区解锁上** |
| 历史用户发放 | 累计向用户发放 **超过 9 亿 WLD**，包括用户奖励和推荐奖励 | 2026-06-09 | [官方·The Simple Plan](https://world.org/thesimpleplan) | 是累计量，不是当前每月发放量 |
| 收入回流 WLD 持有人 | **未查到已执行的统一分红或固定回购机制** | 核查日 | [官方·2026 年费用说明](https://world.org/blog/announcements/world-id-fees-the-revenue-potential-from-world-id) | 官方描述协议费可用于运营或销毁，但本次未查到实际执行比例、持续销毁流水和持有人分配报表 |
| World ID／Orb 是否收费、归谁 | 官方设计：向使用证明的**应用收费，终端用户免费**；凭证费归发行方，协议费按协议配置分配；Orb 凭证发行方为基金会 | 2025 年设计及 2026 年更新 | [官方·原费用设计](https://world.org/blog/announcements/introducing-world-id-fees)、[官方·2026 年更新](https://world.org/blog/announcements/world-id-fees-the-revenue-potential-from-world-id) | 不应把全部收入归为 TFH，亦不应归为代币持有人。2025 年称费用以 WLD 支付；2026 年更新采用“结算费用所用资产”的表述。实际全面启用程度和已实现收入**未查到** |
| World App 是否收费、归谁 | TFH 运营；条款允许适用的交易／兑换费用，交易前展示；第三方及链上网络费用另算 | TFH 条款 4.6，2026-07-22 生效 | [官方·TFH 条款](https://www.toolsforhumanity.com/legal/user-terms-and-conditions/4.6)、[官方·World App FAQ](https://world.org/blog/world/world-app-faqs) | 不能因 App 免费下载就说所有交易免费，也不能把第三方费、gas 全算作 TFH 收入；TFH 当前净收入及分成表**未查到** |
| 做市商借币：早期 | 启动时向五家非美国做市商借出 **1 亿 WLD**；2023 年续约规模降为 **7,500 万** | 2023 年披露 | [官方·早期续约说明](https://world.org/fil-ph/blog/announcements/update-circulating-supply-evolution-renewal-market-maker-loan-agreements) | 早期不同阶段的余额，不能相加 |
| 做市商借币：2024 年披露 | 2023-12-16 新合同合计 **1,000 万 WLD**；后延期至 **2025-06-14**，约定到期全额归还 | 2024-05-30 公告 | [官方·借币延期](https://world.org/blog/announcements/circulating-supply-update-trading-firm-loan-agreements) | **截至 2026-11 的归还、再次续约及剩余余额未查到**；不能自动写成目前仍借出 1,000 万 |
| World Chain 流动性借币 | 2024-10-09 借出 **200 万 WLD**，初始期限两个月 | 2024-10-17 公告 | [官方·World Chain 上线公告](https://world.org/blog/announcements/world-chain-now-open-every-human?forceLocale=true) | 核查日的偿还／续约现状**未查到** |
| 向交易商销售，区别于借币 | 官方 2024-10 更新称此前半年平均销售 **180 万 WLD／周**；2025 年另披露销售 **1.35 亿美元**WLD | 各公告日期 | [官方·交易商销售](https://world.org/blog/announcements/circulating-supply-update-sales-trading-firms)、[官方·2025 年融资](https://world.org/th-th/blog/announcements/world-raises-135m) | 均为历史数据，不能把 180 万／周当作 2026 年当前速率；销售不要求像借币一样归还 |
| Ethereum 合约 | `0x163f8C2467924be0ae7B5347228CABF260318753` | 官方披露，核查日核对 | [官方·合约表](https://whitepaper.world.org/designing-for-scale/2026-03-24) | 主网原生 ERC-20；不是下列桥接代币之外另加一份供给 |
| Optimism 合约 | `0xdC6fF44d5d932Cbd77B52E5612Ba0529DC6226F1` | 同上 | [官方·合约表](https://whitepaper.world.org/designing-for-scale/2026-03-24) | 仍存在；主要使用场景已迁往 World Chain |
| World Chain 合约（补充） | `0x2cFc85d8E48F8EAB294be644d9E25C3030863003` | 同上 | [官方·合约表](https://whitepaper.world.org/designing-for-scale/2026-03-24) | 用户发放及当前链上使用不能只查 Optimism |
| 基金会主要冷钱包 | `0xc534a745bFfaF9466Ed7B47fA23B0177b99A3e77` | 核查日白皮书 | [官方·Main Wallets](https://whitepaper.world.org/designing-for-scale#main-wallets) | 官方列 Ethereum、Optimism、World Chain；同地址在不同链余额不同 |
| World Assets 主要冷钱包 | `0x59a0f98345f54bAB245A043488ECE7FCecD7B596` | 核查日白皮书 | [官方·Main Wallets](https://whitepaper.world.org/designing-for-scale#main-wallets) | 基金会子公司钱包，不应直接标为 TFH 公司私有资产 |
| TFH 团队／投资人／储备历史解锁钱包 | ① `0x0D4CA2FF883D429cE4372Eeb056EFAFab181CcE7`；② `0xFB7F100ED6793FCD63E6E9F201bE9Aa567B2C9cC` | **2023-12-11 版披露** | [官方·历史钱包表](https://whitepaper.world.org/designing-for-scale/2023-12-11) | 历史托管／解锁用途，**不能把钱包全余额归为 TFH 团队个人持仓**；当前完整替代地址表和余额未查到 |
| 社区解锁合约 | Ethereum 上四个地址：`0x1770bd8186AAd27Df9B050D65f86CF2cdC92C296`；`0xaEE0360b73B5D01dad134f234d3a93adc1680e57`；`0x938ceD2D1eE4AFB220929F96c2eB754C053C77F7`；`0x5B5442C5fcEaE3b40C230C32a3Ffe924BcBe7D93` | 官方现行披露 | [官方·合约表](https://whitepaper.world.org/designing-for-scale/2026-03-24) | 属于解锁合约；持币排行榜中的大余额不能一律解释为可立即卖出的巨鲸钱包 |
| 做市商主要持有地址 | 官方披露的完整实体—地址对应表及当前余额：**未查到** | 核查日 | [官方·借币披露](https://world.org/blog/announcements/circulating-supply-update-trading-firm-loan-agreements) | 不采用仅凭转账路径推定的做市商归属作为官方确认 |

## 发现的疑点

1. **TAO 的发行量、流通量和可卖余额口径不同。** 官方文档中的发行示例也与实时看板不同。前十约 20.09% 是地址及质押估值口径，不能解释为十个人可立即卖出的原生 TAO。

2. **TAO 的质押收益主要来自排放。** 子网有收入、alpha 有回购，并不自动意味着 TAO 持有人取得外部现金分红。回收 TAO 与永久销毁也有不同后果。

3. **子网收入缺乏统一可核对口径。** 第三方既有约 2,020 万美元年化、只覆盖三个披露子网的数字，也有 SubConnect 约 7,000 万美元的生态年化估计；覆盖范围、估算方法不同。不能据此给出可信的全网“排放／真实收入”精确倍数。[第三方·tao.eco](https://tao.eco/revenue)、[第三方·SubConnect 数据报道](https://cryptobriefing.com/bittensor-revenue-run-rate-70m/)

4. **WLD 当前约 37.85% 的初始供给在流通，仍有较大的潜在供给释放。** 但约 62.15%“未流通”中有部分已经解锁；把它全部称为“未解锁”会夸大锁仓规模。

5. **WLD 旧版用户增长与排放模型已经失效。** 2026 年 6 月起停止新建／续期空投周期，与旧白皮书持续领取叙述存在实质差异，当前用户日发放量需查实际领取记录。

6. **WLD 常规解锁日历不能覆盖所有额外销售合同。** 未来一年约 10.585 亿只是按官方约数得到的常规解锁基准；额外私募的枚数、结算日、禁售到期日及储备分配日有缺口，不能把这份日历包装成完整精确清单。

7. **做市商借币现状透明度不足。** 历史披露有数量及到期义务，但本次未查到 2026 年 11 月完整的剩余借币余额和对账证明；到期不等于已经归还，未找到归还公告也不等于违约。

8. **World 的商业收入与 WLD 持有人收益尚不能画等号。** 官方确有费用设计及可能销毁的表述，但已实现收入、实际销毁比例和持有人回流记录未查到；TFH、基金会、凭证发行方及第三方服务商也必须分别核算。
