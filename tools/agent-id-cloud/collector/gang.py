"""Gang（gang.fun）发射台只读适配器。

为什么能算 Agent 生态：Gang 所有内盘（曲线买卖、打新、发币）在合约里强制 SPACE ID Agent ID 门禁
（README「Only wallets with a SPACE ID Agent ID (.ai) can create, buy or sell on a curve, or mint」，合约事件 AgentGateUpdated）。
事件定义取自公开仓库 github.com/gangfun/gang-launchpad（commit 见 config.gang_adapter.source_commit），按 topic0 解码，
不是 Sourcify/BscScan 已验证源码（源码在两处都查不到），证据等级记 E3（官方公开源码 + 链上事件），和 AgentPad 的 E1 分开标。

口径：
- 交易 = 曲线 Buy / Sell（含 V2 / U / S / GangLaunchpad / 2.0 / Vault / 3.0 等所有 Gang 曲线 pad）；打新 Minted/Withdrawn 不算买卖。
- 成交额 = Buy.(净额 + 费用) + Sell.(到手额 + 费用)，两侧都按含费毛额（源码里 Buy 记的是扣费后净额）；只计 WBNB / 原生 BNB 计价的币，稳定币计价的计笔数和地址、不计入 BNB 成交额（另记 non_bnb_quote_trades）。
- 新发币 = 各 pad 的 Created（曲线 + 打新 + Flywheel）；毕业 = Graduated（曲线进池）+ Launched（打新 / Flywheel 满额开池）。
- 交易对应的币必须在 Gang pad 的 Created 里出现过（从各 pad 部署区块起完整扫描），否则当天 U，不猜。
"""
import concurrent.futures
import json
from decimal import Decimal
from pathlib import Path

from core import day, dedup_logs, platform_day, timestamp
from eth import Chain
from transport import Unavailable

WBNB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'
ZERO = '0x' + '0' * 40


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def words(log):
    data = log['data'][2:]
    return [int(data[i:i + 64], 16) for i in range(0, len(data), 64)]


def topic_addr(log, i):
    return '0x' + log['topics'][i][-40:].lower()


def word_addr(w):
    return '0x' + hex(w)[2:].zfill(40)[-40:]


def deployment_block(chain, address, head):
    """Smallest block where the address has code (binary search on archive getCode)."""
    lo, hi = 0, head
    if chain.rpc('eth_getCode', [address, hex(head)], True) in ('0x', '0x0'):
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if chain.rpc('eth_getCode', [address, hex(mid)]) in ('0x', '0x0'):
            lo = mid + 1
        else:
            hi = mid
    return lo


def collect(root, config, client, scope, span, state):
    root = Path(root)
    cfg = config['gang_adapter']
    rpc = config['rpc']
    chain = Chain(client, rpc, scope, config['confirmations'])
    errors = []
    prior_path = root / 'data' / 'gang_adapter.json'
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    if prior.get('schema') != cfg['schema']:
        prior = {}
    kinds = {t.lower(): spec for t, spec in cfg['events'].items()}
    head = int(chain.rpc('eth_blockNumber', [], True), 16)

    # 1) Pads: published list + on-chain GangPadRegistry.pads(); keep only addresses with mainnet code.
    pads = {a.lower() for a in cfg['pads']}
    try:
        raw = chain.rpc('eth_call', [{'to': cfg['registry'], 'data': '0x' + cfg['registry_pads_selector']}, 'latest'], True)
        w = [int(raw[2:][i:i + 64], 16) for i in range(0, len(raw) - 2, 64)]
        n = w[1] if len(w) > 1 else 0
        pads |= {word_addr(x).lower() for x in w[2:2 + n]}
    except Exception as e:  # noqa: BLE001
        errors.append(dict(module='B/Gang', date=scope, reason='GangPadRegistry.pads() 读取失败: ' + str(e), rpc=rpc, url=None, blocks=None))
    known_deploy = prior.get('deploy', {})
    deploy = {}
    for a in sorted(pads):
        if a in known_deploy:
            if known_deploy[a] is not None:
                deploy[a] = known_deploy[a]
            continue
        b = deployment_block(chain, a, head)
        known_deploy[a] = b
        if b is not None:
            deploy[a] = b
    addresses = sorted(deploy)
    if not addresses:
        raise Unavailable('Gang pad 列表为空')
    topics = [sorted(kinds)]

    tokens = prior.get('tokens', {})
    trades = prior.get('trades', [])
    done = dict(prior.get('done', {}))
    prefix_to = prior.get('prefix_to')

    def scan(a, b):
        rows, ok, errs = chain.logs(addresses, a, b, topics, config['rpc_log_chunk'], 2)
        if not ok:
            raise Unavailable('Gang getLogs 不完整: ' + str(errs[:2]))
        return dedup_logs(rows)

    def absorb(logs, date_of):
        out_trades, created, graduated = [], [], []
        for log in sorted(logs, key=lambda r: (int(r['blockNumber'], 16), int(r['logIndex'], 16))):
            spec = kinds.get(log['topics'][0].lower())
            if spec is None:
                continue
            pad = log['address'].lower()
            block = int(log['blockNumber'], 16)
            ts = int(log['blockTimestamp'], 16) if log.get('blockTimestamp') else chain.time(block)
            token = topic_addr(log, 1)
            kind = spec['kind']
            w = words(log)
            if kind == 'create':
                quote = WBNB if spec['quote'] == 'native' else (topic_addr(log, 3) if spec['quote'] == 'topic3' else word_addr(w[spec['quote_word']]).lower())
                tokens.setdefault(token, dict(pad=pad, quote=quote, created_ts=ts, created_tx=log['transactionHash'],
                                              creator=topic_addr(log, 2), mode=spec['mode'], graduated_ts=None))
                created.append(token)
            elif kind == 'graduate':
                t = tokens.get(token)
                if t is not None and t.get('graduated_ts') is None:
                    t['graduated_ts'] = ts
                graduated.append(token)
            elif kind in ('buy', 'sell'):
                # 源码核对：Buy 第一个金额是扣费后的净额（v.net / bnbIn），Sell 是付给用户的净额；两侧都加回费用 = 含费毛额
                gross = w[spec['amount_word']] + sum(w[i] for i in spec['fee_words'])
                out_trades.append(dict(platform='Gang', pad=pad, address=token, timestamp=ts, block=block, tx=log['transactionHash'],
                                       log_index=int(log['logIndex'], 16), actor=topic_addr(log, 2), side=kind, quote_amount_wei=str(gross),
                                       date=date_of(ts)))
        return out_trades, created, graduated

    # 2) One-time prefix: every Created / Graduated from the earliest pad deployment up to the first tracked day.
    days_sorted = sorted(d for d, r in state['days'].items() if r.get('A', {}).get('start_block') is not None)
    if not days_sorted:
        raise Unavailable('没有可用的日区块边界')
    first_start = state['days'][days_sorted[0]]['A']['start_block']
    if prefix_to != first_start - 1:
        start = min(deploy.values())
        if start <= first_start - 1:
            absorb(scan(start, first_start - 1), day)  # 只要创建/毕业记录；起点前的买卖不进日表
        prefix_to = first_start - 1

    # 3) Every tracked UTC day not yet complete (catches up history even when the main run is daily-only).
    todo = [d for d in days_sorted if d < scope and (d in span or not done.get(d))]
    for d in todo:
        a = state['days'][d]['A']
        try:
            logs = scan(a['start_block'], a['end_block'])
        except Exception as e:  # noqa: BLE001
            done[d] = False
            errors.append(dict(module='B/Gang', date=d, reason=str(e), rpc=rpc, url=rpc, blocks=[a['start_block'], a['end_block']]))
            continue
        trades = [t for t in trades if t['date'] != d]
        new_trades, _, _ = absorb(logs, lambda ts: d)
        trades += new_trades
        done[d] = True

    # 4) Price each trade in BNB; a trade on a token we never saw created makes that day U.
    rows = []
    for d in days_sorted:
        a = state['days'][d]['A']
        end_ts = timestamp(d) + 86400
        daily = [t for t in trades if t['date'] == d]
        unknown = [t for t in daily if t['address'] not in tokens]
        complete = bool(done.get(d)) and not unknown
        for t in daily:
            q = tokens.get(t['address'], {}).get('quote')
            bnb_quoted = q in (WBNB, ZERO)
            t['curve_bnb_wei'] = int(t['quote_amount_wei']) if bnb_quoted else 0
            t['bnb'] = float(Decimal(t['curve_bnb_wei']) / 10**18)
            t['quote'] = q
            t['quote_is_bnb'] = bnb_quoted
        known = [dict(t, address=addr, platform='Gang', taxed=None, dev_prebuy=None, raised_eod_bnb=None)
                 for addr, t in tokens.items() if t.get('created_ts') is not None and t['created_ts'] < end_ts]
        row = platform_day(known, daily, d, complete)
        row.update(platform='Gang', date=d, start_block=a.get('start_block'), end_block=a.get('end_block'), rpc=rpc,
                   complete=complete, launch_events_complete=bool(done.get(d)), source_grade='E3',
                   raw=[], reason=None if complete else ('当日有未见创建记录的币：' + ','.join(sorted({t['address'] for t in unknown}))[:300] if unknown else '链上日志读取不完整'))
        if complete:
            row['curve_trade_count'] = len(daily)
            row['curve_volume_bnb'] = str(Decimal(sum(t['curve_bnb_wei'] for t in daily)) / 10**18)
            row['new_launches'] = sum(day(t['created_ts']) == d for t in tokens.values())
            row['graduated_today'] = sum(t.get('graduated_ts') is not None and day(t['graduated_ts']) == d for t in tokens.values())
            row['non_bnb_quote_trades'] = sum(not t['quote_is_bnb'] for t in daily)
            row['pads_active'] = sorted({t['pad'] for t in daily})
        rows.append(row)
        if unknown:
            errors.append(dict(module='B/Gang', date=d, reason=row['reason'], rpc=rpc, url=None, blocks=[a.get('start_block'), a.get('end_block')]))

    result = dict(schema=cfg['schema'], rows=rows, tokens=tokens, trades=trades, done=done, deploy=known_deploy, prefix_to=prefix_to,
                  pads=addresses, source=cfg['source_repo'] + '@' + cfg['source_commit'], errors=errors)
    dump(root / 'data' / 'gang_adapter.json', result)
    return result
