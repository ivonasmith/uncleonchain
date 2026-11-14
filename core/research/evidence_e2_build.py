#!/usr/bin/env python3
"""证据库 E2 地址表：把 Codex 2026-11-14 核查（core/research/回购销毁地址核查_20261115_codex.md）整理成结构化数据 → core/research/evidence_e2.json。
等级：official = 官方文档 / 仓库直接列址；official_tx = 官方报告链接的交易反查；candidate = 只在 E1（第三方适配器）出现、官方逐址未查到；missing = 该用途地址没找到。
qty_12m 一律 None（Codex 没有一个地址闭合到可核实的 12 个月数量；不是 0）。e1 = 地址字符串是否出现在 E1（修正正则后）。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
U = {"hl": "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees",
     "pumpfee": "https://github.com/pump-fun/pump-public-docs/blob/main/docs/FEE_RECIPIENTS.md", "pumptok": "https://pump.fun/pump-token",
     "cakeblog": "https://blog.pancakeswap.finance/articles/pancake-swap-cake-burn-mechanics-a-comprehensive-guide", "caketok": "https://docs.pancakeswap.finance/protocol/cake-tokenomics",
     "unidep": "https://developers.uniswap.org/docs/protocols/protocol-fee/deployments",
     "aavegov": "https://www.aave.com/docs/ecosystem/governance", "aavebook": "https://github.com/aave-dao/aave-address-book/blob/main/src/AaveV3Ethereum.sol",
     "jupq2": "https://impressive-horses-5641a8b530.media.strapiapp.com/Jupiter_Token_Transparency_Framework_Q2_2025_07d97ce582.pdf", "jupburn": "https://discuss.jup.ag/t/jup-community-audit-feb-2025/34764",
     "pendle": "https://docs.pendle.finance/pendle-v2/ProtocolMechanics/Mechanisms/Fees",
     "ena": "https://docs.ethena.fi/technical-design/key-addresses", "enafee": "https://gov.ethenafoundation.com/t/ena-fee-switch-activation/830",
     "ethfi": "https://etherfi.gitbook.io/gov/ethfi-buyback-program",
     "ldorep": "https://research.lido.fi/t/utilizing-market-opportunities-steth-ldo-trade/11358?page=2", "ldodep": "https://docs.lido.fi/deployed-contracts/",
     "sky": "https://chainlog.skyeco.com/api/mainnet/active.json", "render": "https://know.rendernetwork.com/general-render-network/stay-safe-1",
     "aster": "https://docs.asterdex.com/usdaster-token/tokenomics", "virtual": "https://whitepaper.virtuals.io/about-virtuals/capital-formation-layer/virtuals-launch-mechanics",
     "gmxarb": "https://github.com/gmx-io/gmx-synthetics/blob/main/deployments/arbitrum/FeeHandler.json", "gmxavax": "https://github.com/gmx-io/gmx-synthetics/blob/main/deployments/avalanche/FeeHandler.json",
     "ray": "https://docs.raydium.io/ray/ray-buybacks", "aero": "https://github.com/aerodrome-finance/contracts/blob/main/README.md",
     "crv": "https://docs.curve.finance/developer/fees/fee-distributor/"}

# 用途类别：fee_in = 费用接收 / 归集；buyback = 回购执行或回购持仓；burn = 销毁；distribute = 分配给质押者 / 持有人；treasury = 国库
R = []
def add(sym, chain, addr, cat, role, lvl, src, e1, last=None):
    R.append({"sym": sym, "chain": chain, "addr": addr, "cat": cat, "role": role, "level": lvl, "src": U[src], "e1": e1, "qty_12m": None, "last": last})

add("HYPE", "HyperCore", "0xfefefefefefefefefefefefefefefefefefefefe", "burn", "Assistance Fund：费用自动买入 HYPE，官方认定其中 HYPE 为已销毁", "official", "hl", False)
for a, e in [("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV", True), ("7VtfL8fvgNfhz17qKRMjzQEXgbdpnHHHQRh54R9jP2RJ", False), ("7hTckgnGnLQR6sdH7YkqFTAA7VwTfYFaZ6EhEsU3saCX", False),
             ("9rPYyANsfQZw3DnDmKE3YCQF5E8oD89UXoHn9JFEhJUz", False), ("AVmoTthdrX6tKt4nDjco2D775W2YK3sDhxPcMmzUAmTY", False), ("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM", True),
             ("FWsW1xNtWscwNmKv6wVsU1iTzRN6wmmk3MjxRP5tT7hz", False), ("G5UZAVbAf46s7cKWoyKu8kYTip9DGTpbLZ2qa9Aq69dP", False)]:
    add("PUMP", "Solana", a, "fee_in", "普通币协议费用接收（不等于 PUMP 回购）", "official", "pumpfee", e)
for a, e in [("GesfTA3X2arioaHp8bbKdjG9vJtskViWACZoYvxp4twS", True), ("4budycTjhs9fD6xw62VBducVTNgMgJJ5BgtKq7mAZwn6", False), ("8SBKzEQU4nLSzcwF4a74F2iaUDQyTfjGndn6qUWBnrpR", False),
             ("4UQeTP1T39KZ9Sfxzo3WR5skgsaP6NZa87BAkuazLEKH", False), ("8sNeir4QsLsJdYpc9RZacohhK1Y5FLU3nC5LXgYB4aa6", False), ("Fh9HmeLNUMVCvejxCtCL2DbYaRyBFVJ5xrWkLnMH6fdk", False),
             ("463MEnMeGyJekNZFQSTUABBEbLnvMTALbT6ZmsxAbAdq", False), ("6AUH3WEHucYZyC61hqpqYUWVto5qA5hjHuNQ32GNnNxA", False)]:
    add("PUMP", "Solana", a, "fee_in", "Mayhem 协议费用接收（不等于 PUMP 回购）", "official", "pumpfee", e)
for a in ["5YxQFdt3Tr9zJLvkFccqXVUwhdTWJQc1fFg2YPbxvxeD", "9M4giFFMxmFGXtc3feFzRai56WbBqehoSeRE5GK7gf7", "GXPFM2caqTtQYC2cJ5yJRi9VDkpsYZXzYdwYpGnLmtDL", "3BpXnfJaUTiwXnJNe7Ej1rcbzqTTQUvLShZaWazebsVR",
          "5cjcW9wExnJJiqgLjq7DEG75Pm6JBgE1hNv4B2vHXUW6", "EHAAiTxcdDwQ3U4bU6YcMsQGaekdzLS3B5SmYo46kJtL", "5eHhjP8JaYkz83CWwvGU2uMUXefd3AazWGx4gpcuEEYD", "A7hAgCzFw14fejgCp387JUJRMNyz4j89JKnhtKU8piqW"]:
    add("PUMP", "Solana", a, "fee_in", "buybackFeeRecipient：回购费用接收，收款量不等于买入 PUMP 数量", "official", "pumpfee", False)
for a in ["3vkpy5YHqnqJTnA5doWTpcgKyZiYsaXYzYM9wm8s3WTi", "88uq8JNL6ANwmow1og7VQD4hte73Jpw8qsUP77BtF6iE", "3YNxfRAEqKrGNCmx5JUfCD9er5djZToqSomzR2Yi8rqx", "99mRw3EzdJZWEUjgp1nrU4WeHsukUBjbh7gYE7pm4F3c",
          "9jHrTCwpDANHLNQz5cem6XLUBM8KiTWKe766Br6KVCXM", "2ifjKjqtETDeHXKsrRxeKWUuwUtXxNS4HepT6eftj6Qz", "78hoB7emUo7zF5kdNf9TFxzpLRKCy8Jgft5cu69Byuax", "G8CcfRffqZWHSAQJXLDfwbAkGE95SddUqVXnTrL4kqjm"]:
    add("PUMP", "Solana", a, "buyback", "E1 回购 / 销毁执行或持仓候选；官方逐址归属未查到", "candidate", "pumptok", True)
add("CAKE", "BNB Chain", "0xceba60280fb0ecd9a5a26a1552b90944770a4a0e", "fee_in", "官方 Appendix 链接的费用归集多签，随后转向销毁地址", "official", "cakeblog", False)
add("CAKE", "BNB Chain", "0x000000000000000000000000000000000000dEaD", "burn", "CAKE 销毁接收候选；官方说明 burn address，精确地址的官方直接披露未查到", "candidate", "caketok", False)
for ch, jar, rel in [("Ethereum", "0xf38521f130fcCF29dB1961597bc5d2B60F995f85", "0x0D5Cd355e2aBEB8fb1552F56c965B867346d6721"),
                     ("Unichain", "0xD576BDF6b560079a4c204f7644e556DbB19140b5", "0xe0A780E9105aC10Ee304448224Eb4A2b11A77eeB"),
                     ("Optimism", "0xb13285DF724ea75f3f1E9912010B7e491dCd5EE3", "0x94460443Ca27FFC1baeCa61165fde18346C91AbD"),
                     ("BNB Chain", "0xc6Ae6373CEcc9e595A6C8b9fe581925a8c84f70A", "0xa59FfbB55D91Fc32b44A06F0b9cc6036a4afbcE2"),
                     ("Polygon", "0xc6Ae6373CEcc9e595A6C8b9fe581925a8c84f70A", "0xa59FfbB55D91Fc32b44A06F0b9cc6036a4afbcE2"),
                     ("X Layer", "0x8Dd8B6D56e4a4A158EDbBfE7f2f703B8FFC1a754", "0xe122E231cb52aea99690963Fd73E91e33E97468f"),
                     ("World Chain", "0xbDb82c2dE7D8748A3e499e771604ef8ef8544918", "0x455e844D286631566cF98D6cb2996149734618C6"),
                     ("Soneium", "0x85aeb792b94a9d79741002FC871423Ec5dAD29e9", "0xc9CC50A75cE2a5f88fa77B43e3b050480c731b6e"),
                     ("Robinhood Chain", "0x2aC03e14Cfe755426DaAEe0a4994184Ce81482F8", "0x7a8f74C2585F84c781F951B7f2FF21337D5b630b"),
                     ("Base", "0x9bD25e67bF390437C8fAF480AC735a27BcF6168c", "0xFf77c0ED0B6b13A20446969107E5867abc46f53a"),
                     ("Arbitrum", "0x95E337C5B155385945D407f5396387D0c2a3A263", "0xB8018422bcE25D82E70cB98FdA96a4f502D89427"),
                     ("Celo", "0x190c22c5085640D1cB60CeC88a4F736Acb59bb6B", "0x2758FbaA228D7d3c41dD139F47dab1a27bF9bc25"),
                     ("Zora", "0x4753C137002D802f45302b118E265c41140e73C2", "0x2f98eD4D04e633169FbC941BFCc54E785853b143")]:
    add("UNI", ch, jar, "fee_in", "TokenJar：协议费用接收，不直接等同于 UNI 买入 / 销毁", "official", "unidep", False)
    add("UNI", ch, rel, "burn", "Firepit / Releaser：释放费用资产，UNI 销毁或跨链处理路径需按该链合约核实", "official", "unidep", False)
add("AAVE", "Ethereum", "0x22740deBa78d5a0c24C58C740e3715ec29de1bFa", "buyback", "Aave Finance Committee 多签：回购和国库操作", "official", "aavegov", True)
add("AAVE", "Ethereum", "0xb7D402138Cb01BfE97d95181C849379d6AD14d19", "buyback", "Mainnet Swap Steward：执行 CoW 国库兑换，所得返回 Collector", "official", "aavegov", False)
add("AAVE", "Ethereum", "0x464C71f6c2F760DdA6093dCB91C24c39e5d6e18c", "treasury", "Aave Collector：费用 / 国库接收，AAVE 流入不全是回购", "official", "aavebook", True)
add("JUP", "Solana", "6tZT9AUcQn4iHMH79YZEXSy55kDLQ4VbA3PMtfLVNsFX", "buyback", "Litterbox：回购 JUP 持仓（持有，不是销毁）", "official", "jupq2", True)
add("JUP", "Solana", "8gMBNeKwXaoNi9bhbVUWFt4Uc5aobL9PeYMXfYDMePE2", "burn", "3B Burn Multisig：2025-01 历史供给销毁，不是费用回购", "official", "jupburn", True)
for ch, a in [("Ethereum", "0x8270400d528c34e1596EF367eeDEc99080A1b592"), ("Arbitrum", "0xCbcb48e22622a3778b6F14C2f5d258Ba026b05e6"),
              ("Mantle", "0x5C30d3578A4D07a340650a76B9Ae5dF20D5bdF55"), ("BNB Chain", "0xd77E9062c6DF3F2d1CB5Bf45855fa1E7712A059e")]:
    add("PENDLE", ch, a, "fee_in", "2024-10-08 之前池子的积分费用归集；不是独立回购执行证明", "official", "pendle", True)
add("PENDLE", "Ethereum / Arbitrum / Mantle / BNB Chain", "0xC328dFcD2C8450e2487a91daa9B75629075b7A43", "fee_in", "2024-10-08 之后池子的积分费用归集（官方称全部链）", "official", "pendle", False)
add("ENA", "Ethereum", "0x71E4f98e8f20C88112489de3DDEd4489802a3A87", "distribute", "sUSDe Payout Fund：发 USDe 收益，不是 ENA 回购", "official", "ena", True)
add("ENA", "Ethereum", "0xf2fa332bD83149c66b09B45670bCe64746C6b439", "distribute", "USDe→sUSDe 质押奖励分发器，不是 ENA 回购", "official", "ena", True)
add("ENA", "Ethereum", "0x2b5ab59163a6e93b4486f6055d33ca4a115dd4d5", "treasury", "Reserve Fund：USDe 风险储备，不是 ENA 回购", "official", "ena", True)
add("ENA", None, None, "buyback", "ENA 专用回购 / 销毁执行地址", "missing", "enafee", False)
add("ETHFI", "Ethereum", "0x2f5301a3D59388c509C65f8698f521377D41Fd0F", "buyback", "Foundation wallet：旧回购计划，所得用于 sETHFI 分配", "official", "ethfi", True,
    {"date": "2026-04-01", "what": "该钱包已核实的最后一笔 CoW 回购", "url": "https://eth.blockscout.com/tx/0xb236e4a5dd02755313e3bf02dcd1c2b30afe6954d203177648821902e46bbe19"})
add("ETHFI", "Ethereum", "0x43F4ca92F7F378bCdcF1508b866b5B6c47D6408C", "buyback", "E1 新 ETHFI 回购 Safe；官方逐址未查到", "candidate", "ethfi", True)
add("ETHFI", "Ethereum", "0xa7b1d3a045fe9566513f3ecc858469640c88be29", "buyback", "E1 EthfiBuyback 合约；官方逐址未查到", "candidate", "ethfi", True)
add("ETHFI", "Ethereum", "0xd1208cC82765aA4dc696117D26f37388B6Dcb6D5", "distribute", "E1 持有人收入接收候选；官方逐址未查到", "candidate", "ethfi", True)
add("ETHFI", "Ethereum", "0x8fb66F38cF86A3d5e8768f8F1754A24A6c661Fb8", "fee_in", "E1 fee recipient；官方逐址未查到", "candidate", "ethfi", True)
add("ETHFI", "Optimism", "0x38F2fBb259F042DE3A601E0f7135f768DE08F5A2", "distribute", "E1 CashbackDistributor：不能认作持有人分红或销毁", "candidate", "ethfi", True)
add("LDO", "Ethereum", "0xf6F0732c1e9971497342C295141566E6F1A31e96", "buyback", "旧 Accumulation Program Safe（由官方报告链接的交易反查）", "official_tx", "ldorep", True,
    {"date": "2026-09-25", "what": "最后一次 Safe→Agent LDO 归库（归库日不是成交日）", "url": "https://eth.blockscout.com/tx/0x60ccdd81c55a4e2dad9b5c6c6634f0f8a892f1e1f8dd7cf932216ccee75aeee3"})
add("LDO", "Ethereum", "0x3e40D73EB977Dc6a537aF587D48316feE66E9C8c", "treasury", "Aragon Agent 国库：接收回购所得；NEST 国库模式直接接收", "official", "ldodep", True)
add("SKY", "Ethereum", "0x374D9c3d5134052Bc558F432Afa1df6575f07407", "buyback", "MCD_FLAP：Smart Burn Engine 执行合约", "official", "sky", False)
add("SKY", "Ethereum", "0xBF7111F13386d23cb2Fba5A538107A73f6872bCF", "fee_in", "MCD_SPLIT：盈余分流", "official", "sky", False)
add("SKY", "Ethereum", "0xA950524441892A31ebddF91d3cEEFa04Bf454466", "fee_in", "MCD_VOW：系统盈余接收 / 记账", "official", "sky", False)
add("RENDER", "Solana", "rbrnm7nPhfhBxPSh8qhRFrhB5MLnJGMNoyNQPvSi7vq", "burn", "BME 销毁操作钱包（owner）；转入不等于已销毁", "official", "render", True)
add("RENDER", "Solana", "GqE7wcwRw86xxMz4pNq5cV3BkM64h3bvajQRQbigYqTX", "burn", "BME 销毁关联 ATA；要按 Burn / BurnChecked 指令计", "official", "render", False)
add("ASTER", "Aster Chain（未独立确认）", "0xa0edBaBcb48034e368de286b49F9603C7AfA1b60", "buyback", "公开 buyback wallet：TWAP 回购，所得作为 veASTER 奖励", "official", "aster", True)
add("ASTER", None, "0x39C473f4420e4ae9Ab3fe9e7ceDFc08F9684bB1a", "fee_in", "Listing fee wallet：上币费，随后用于回购（链未查到）", "official", "aster", False)
add("ASTER", "BNB Chain", "0x5E4969C41ca9F9831468B98328A370b7AbD5a397", "burn", "E1 历史 buybackWalletToBurn；官方逐址未查到", "candidate", "aster", True)
add("ASTER", "BNB Chain", "0xa6F7444D2b92Aa9F94a2165c77aAF2B671e63994", "buyback", "E1 历史 TWAP 执行合约；官方逐址未查到", "candidate", "aster", True)
for ch, a, nm in [("Base", "0xb51c52d9e5e41937b0100840b6c3cba6f7a57a0c", "EVM_TREASURY"), ("Solana", "933jV351WDG23QTcHPqLFJxyYRrEPWRTR3qoPWi3jwEL", "BONDING_COLLECTOR"),
                  ("Solana", "Bo2jk8vNANP3cEgsEWCszvzy9mPR8CPqQKenUkNbyBHm", "TAX_DISTRIBUTOR"), ("Solana", "9yEiY8zzVcV5ASmFub9X3Ti96AAwboYRVAKajwbpba5", "TREASURY")]:
    add("VIRTUAL", ch, a, "treasury", f"E1 {nm}；官方逐址未查到，不能认作 VIRTUAL 回购 / 销毁", "candidate", "virtual", True)
add("GMX", "Arbitrum", "0x7EB417637a3E6d1C19E6d69158c47610b7a5d9B3", "buyback", "FeeHandler：费用兑换 / 回购处理，买入代币由参数决定", "official", "gmxarb", False)
add("GMX", "Avalanche", "0x1A3A103F9F536a0456C9b205152A3ac2b3c54490", "buyback", "FeeHandler：费用兑换 / 回购处理，买入代币由参数决定", "official", "gmxavax", False)
add("RAY", "Solana", "DdHDoz94o2WJmD9myRobHCwtx1bESpHTd4SSPe6VEZaz", "buyback", "买回 RAY 持仓地址（持有，不是销毁）", "official", "ray", False)
add("RAY", "Solana", "projjosVCPQH49d5em7VYS7fJZzaqKixqKtus7yk416", "fee_in", "CLMM 费用归集", "official", "ray", False)
add("RAY", "Solana", "ProCXqRcXJjoUd1RNoo28bSizAA6EEqt9wURZYPDc5u", "fee_in", "CPMM 费用归集", "official", "ray", False)
add("RAY", "Solana", "PNLCQcVCD26aC7ZWgRyr5ptfaR7bBrWdTFgRWwu2tvF", "fee_in", "Standard AMM v4 费用归集", "official", "ray", False)
add("AERO", "Base", None, "fee_in", "PoolFees / FeesVotingReward 逐池部署，具体实例地址未查到", "missing", "aero", False)
add("CRV", "Ethereum", "0xD16d5eC345Dd86Fb63C6a9C43c517210F1027914", "distribute", "FeeDistributor：向 veCRV 分配 crvUSD，不是销毁 CRV", "official", "crv", False,
    {"date": "2026-11-14", "what": "费用领取 Claim", "url": "https://etherscan.io/tx/0xeb730ce81a80bda2dda7b2730cd01b19915cedc994e2dba17c51d0c47529bfdf"})
add("CRV", "Ethereum", "0xA464e6DCda8AC41e03616F95f4BC98a13b8922Dc", "distribute", "旧 FeeDistributor：向 veCRV 分配 3CRV，不是销毁 CRV", "official", "crv", False,
    {"date": "2026-11-14", "what": "费用领取 Claim", "url": "https://etherscan.io/tx/0x7c0f2d997d0e0a5a5ffb0d7987945e169467a3492d980c2db6b4de410575be1f"})

out = {"asof": "2026-11-14", "source": "core/research/回购销毁地址核查_20261115_codex.md（Codex，E1 基线 f6f01137）",
       "window_12m": ["2025-11-14", "2026-11-14"], "note": "12 个月数量全部未查到（不是 0）；地址核实不等于数量核实。",
       "levels": {"official": "官方直接列址", "official_tx": "官方报告链接的交易反查", "candidate": "只在第三方适配器出现，官方未确认", "missing": "该用途地址未找到"},
       "cats": {"fee_in": "费用接收 / 归集", "buyback": "回购执行 / 持仓", "burn": "销毁", "distribute": "分配给质押者 / 持有人", "treasury": "国库"},
       "not_covered": ["MORPHO", "NEAR", "LINK", "PYTH", "BNB", "TRX"], "rows": R}
json.dump(out, open(os.path.join(HERE, "evidence_e2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(R), "行；", dict(Counter(r["level"] for r in R)), "；币", len({r["sym"] for r in R}))
