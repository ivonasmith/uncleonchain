# 交易所上币复盘 QC（2026-11-18）

核对时间为 UTC，口径遵循《交易所上币回报研究》v3。

| 交易所 | 结果 | 样本与起点 | 异常 |
|---|---|---|---|
| Upbit | 文件返回 error | n=0，ref_type=U | 该所 K 线接口不按 since 回溯，无法复盘。 |
| Bybit | 已生成 | symbols=848，coins=18，used=10，ref_15m=10，ref_1h=0 | complete=false，7 个币在归档开始前已上线。 |
| Bitget | 不完整 | bases=3578，coins=484，used=472，ref_15m=472 | complete=false，本轮未覆盖全部基础币。 |

## 官方公告抽查

Bybit 和 Bitget 各抽查 BTC、ETH、SOL、XRP、DOGE。上线日、官方公告链接、是否一致均为 U。当前 Actions 结果没有保存公告 URL 字段，环境也不能直接请求交易所网络，待下一轮补证。
