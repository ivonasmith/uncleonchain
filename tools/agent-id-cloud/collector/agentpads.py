"""Four.meme（Agent 创建币）与 Flap（Agent ID 门禁币）只读适配器。

口径与证据：
- Flap：官方文档 docs.flap.sh「Agent ID-Gated Internal Market」：发币时可选 Agent ID 门禁，门禁币在内盘的每一笔买卖
  都要求 tx.origin 持有该 ERC-721；Portal（BSC 0xe2cE6ab80874Fa9Fa2aAE65D277Dd6B8e65C9De0）发币时发 FlapNFTGated(token, nft)。
  这里只算 nft == Binance Agent ID 注册表（config.registry.address）的币；管理员移除门禁（FlapNFTGateUpdated → 0）之后的买卖不算。
  事件定义照文档「Trade Tokens」：TokenBought/TokenSold(ts, token, trader, amount, eth, fee, postPrice)、LaunchedToDEX = 毕业。
- Four.meme：官方仓库 four-meme-community/four-meme-ai：TokenManager2._tokenInfos(token).template 第 85 位 = 由 Agent 钱包创建；
  这只标记创建者，买卖不限 Agent ID。所以 Four.meme 一行 = 「Agent 创建的币」的发币 / 买卖 / 毕业，和 Gang、Flap 的「只有 Agent ID 能买卖」口径不同，单独成行标注。
  事件：TokenCreate / TokenPurchase / TokenSale（全部字段不 indexed）/ LiquidityAdded = 毕业。
- 成交额都按含费毛额：买 = 付出（Four: cost + fee；Flap 见 FLAP_BUY_INCLUDES_FEE），卖 = 到手 + 费用（Four: cost，费用已含；Flap: eth + fee）。
  只计 BNB 计价（报价币为 0 地址或 WBNB），其他报价币计笔数和地址、不计 BNB。
- 两家每天日志量大（Flap 全平台每天约 5 万条买卖），只把命中的 Agent 币事件存进 data/agentpads_<id>.json，不缓存全量原始响应。
"""
import concurrent.futures
import json
import os
import time
import urllib.request
from decimal import Decimal
from pathlib import Path

from core import day, platform_day, timestamp
from transport import Unavailable

WBNB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'
ZERO = '0x' + '0' * 40


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


def W(data):
    d = data[2:]
    return [d[i:i + 64] for i in range(0, len(d), 64)]


def A(word):
    return '0x' + word[-40:].lower()


def U(word):
    return int(word, 16)


class Rpc:
    """Uncached JSON-RPC over the configured pool (public first, keyed fallback last)."""

    def __init__(self, config):
        url = config['rpc']
        self.members = url[5:].split('|') if url.startswith('pool:') else [url]
        proxy = config.get('proxy')
        handler = urllib.request.ProxyHandler({}) if proxy in (None, '', 'direct') else urllib.request.ProxyHandler({'https': proxy, 'http': proxy})
        self.opener = urllib.request.build_opener(handler)
        self.bad = {}
        self.calls = 0

    def call(self, method, params):
        last = None
        for i, m in enumerate(self.members):
            if i < len(self.members) - 1 and self.bad.get(m, 0) >= 5:
                continue
            for attempt in range(4):
                try:
                    self.calls += 1
                    req = urllib.request.Request(m, json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
                                                 {'Content-Type': 'application/json', 'User-Agent': 'agent-id-read-only-monitor/1.0'})
                    with self.opener.open(req, timeout=60) as r:
                        out = json.loads(r.read())
                    if 'error' in out:
                        msg = str(out['error'])
                        if any(s in msg.lower() for s in ('rate', 'limit exceeded', '429')) and attempt < 3:
                            time.sleep(2 ** attempt)
                            continue
                        raise Unavailable(msg[:300])
                    self.bad[m] = 0
                    return out['result']
                except Unavailable as e:
                    last = e
                    break
                except Exception as e:  # noqa: BLE001
                    last = Unavailable(str(e)[:300])
                    if attempt < 3:
                        time.sleep(2 ** attempt)
            self.bad[m] = self.bad.get(m, 0) + 1
        raise last or Unavailable('rpc pool empty')

    def logs(self, address, topics, a, b, chunk=2000):
        spans = [(x, min(b, x + chunk - 1)) for x in range(a, b + 1, chunk)]
        out = []

        def one(span, depth=3):
            try:
                return self.call('eth_getLogs', [{'address': address, 'topics': topics, 'fromBlock': hex(span[0]), 'toBlock': hex(span[1])}])
            except Unavailable as e:
                text = str(e).lower()
                if depth and span[1] > span[0] and any(s in text for s in ('range', 'too many', 'response size', 'query returned more', 'limit')):
                    mid = (span[0] + span[1]) // 2
                    return one((span[0], mid), depth - 1) + one((mid + 1, span[1]), depth - 1)
                raise
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for res in pool.map(one, spans):
                out += res
        seen, uniq = set(), []
        for r in out:
            if r.get('removed'):
                continue
            k = (r['transactionHash'].lower(), int(r['logIndex'], 16))
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        return sorted(uniq, key=lambda r: (int(r['blockNumber'], 16), int(r['logIndex'], 16)))


def collect(root, config, client, scope, span, state, key):
    """key = 'four' | 'flap'. Returns rows / trades / errors like gang.collect."""
    root = Path(root)
    cfg = config['agentpads'][key]
    platform = cfg['platform']
    rpc = Rpc(config)
    prior_path = root / 'data' / f'agentpads_{key}.json'
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    if prior.get('schema') != cfg['schema']:
        prior = {}
    tokens = prior.get('tokens', {})        # agent tokens only: {addr: {created_ts?, creator?, quote, graduated_date?, gate_removed_ts?}}
    lookups = prior.get('lookups', {})      # four: every traded token's (is_agent, quote)
    trades = prior.get('trades', [])
    launches = prior.get('launches', {})    # date -> count of agent launches
    grads = prior.get('grads', {})          # date -> count of agent graduations
    done = dict(prior.get('done', {}))
    errors = []
    registry = config['registry']['address'].lower()
    T = cfg['topics']

    def four_info(tok):
        if tok not in lookups:
            raw = rpc.call('eth_call', [{'to': cfg['address'], 'data': cfg['tokeninfo_selector'] + tok[2:].zfill(64)}, 'latest'])
            w = W(raw)
            if len(w) < 3:
                raise Unavailable('_tokenInfos 返回异常 ' + tok)
            template = U(w[2])
            lookups[tok] = dict(agent=bool((template >> cfg['agent_bit']) & 1), quote=A(w[1]))
        return lookups[tok]

    days_sorted = sorted(d for d, r in state['days'].items() if r.get('A', {}).get('start_block') is not None)
    todo = [d for d in days_sorted if d < scope and d >= cfg.get('first_date', '0000') and (d in span or not done.get(d))]
    for d in todo:
        a = state['days'][d]['A']
        try:
            logs = rpc.logs(cfg['address'], [list(T.values())], a['start_block'], a['end_block'])
            day_trades, n_launch, n_grad = [], 0, 0
            if key == 'four':
                need = sorted({A(W(l['data'])[1]) if l['topics'][0] == T['create'] else A(W(l['data'])[0]) for l in logs})
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                    list(pool.map(four_info, need))
                for l in logs:
                    t0, w = l['topics'][0], W(l['data'])
                    if t0 == T['create']:
                        tok = A(w[1])
                        if lookups[tok]['agent']:
                            tokens.setdefault(tok, dict(created_date=d, creator=A(w[0]), quote=lookups[tok]['quote']))
                            n_launch += 1
                    elif t0 == T['graduate']:
                        tok = A(w[0])
                        if lookups[tok]['agent']:
                            tokens.setdefault(tok, dict(quote=lookups[tok]['quote']))['graduated_date'] = d
                            n_grad += 1
                    else:
                        tok = A(w[0])
                        if not lookups[tok]['agent']:
                            continue
                        side = 'buy' if t0 == T['buy'] else 'sell'
                        gross = U(w[4]) + U(w[5]) if side == 'buy' else U(w[4])
                        day_trades.append(dict(token=tok, actor=A(w[1]), side=side, gross=str(gross), quote=lookups[tok]['quote'],
                                               tx=l['transactionHash'], log_index=int(l['logIndex'], 16), block=int(l['blockNumber'], 16)))
            else:
                # Flap: gate events first (same tx as TokenCreated), then trades on gated tokens only.
                for l in logs:
                    t0 = l['topics'][0]
                    fields = [x[2:].zfill(64) for x in l['topics'][1:]] + W(l['data'])
                    if t0 == T['gated'] and A(fields[1]) == registry:
                        tokens.setdefault(A(fields[0]), dict(created_date=d, gated_block=int(l['blockNumber'], 16), quote=WBNB))
                    elif t0 == T['gate_updated'] and A(fields[0]) in tokens and A(fields[2]) == ZERO:
                        tokens[A(fields[0])]['gate_removed_block'] = int(l['blockNumber'], 16)
                    elif t0 == T['quote'] and A(fields[0]) in tokens:
                        tokens[A(fields[0])]['quote'] = A(fields[1])
                for l in logs:
                    t0 = l['topics'][0]
                    fields = [x[2:].zfill(64) for x in l['topics'][1:]] + W(l['data'])
                    block = int(l['blockNumber'], 16)
                    if t0 == T['create']:
                        tok = A(fields[3])
                        if tok in tokens and tokens[tok].get('created_date') == d:
                            tokens[tok]['creator'] = A(fields[1])
                            n_launch += 1
                    elif t0 == T['graduate']:
                        tok = A(fields[0])
                        if tok in tokens:
                            tokens[tok]['graduated_date'] = d
                            n_grad += 1
                    elif t0 in (T['buy'], T['sell']):
                        tok = A(fields[1])
                        t = tokens.get(tok)
                        if t is None or block < t.get('gated_block', 0) or block >= t.get('gate_removed_block', 10**12):
                            continue
                        side = 'buy' if t0 == T['buy'] else 'sell'
                        eth, fee = U(fields[4]), U(fields[5])
                        gross = (eth if cfg['buy_includes_fee'] else eth + fee) if side == 'buy' else eth + fee
                        day_trades.append(dict(token=tok, actor=A(fields[2]), side=side, gross=str(gross), quote=t.get('quote', WBNB),
                                               tx=l['transactionHash'], log_index=int(l['logIndex'], 16), block=block))
            trades = [t for t in trades if t['date'] != d] + [dict(t, date=d) for t in day_trades]
            launches[d], grads[d] = n_launch, n_grad
            done[d] = True
        except Exception as e:  # noqa: BLE001
            done[d] = False
            errors.append(dict(module='B/' + platform, date=d, reason=str(e)[:300], rpc='pool', url=None, blocks=[a['start_block'], a['end_block']]))

    rows, out_trades = [], []
    for d in days_sorted:
        a = state['days'][d]['A']
        complete = bool(done.get(d)) and d >= cfg.get('first_date', '0000')
        daily = []
        for t in trades:
            if t['date'] != d:
                continue
            bnb = t['quote'] in (WBNB, ZERO)
            daily.append(dict(platform=platform, address=t['token'], timestamp=timestamp(d) + 1, block=t['block'], tx=t['tx'], log_index=t['log_index'],
                              actor=t['actor'], side=t['side'], curve_bnb_wei=int(t['gross']) if bnb else 0, bnb=float(Decimal(int(t['gross']) if bnb else 0) / 10**18),
                              quote=t['quote'], quote_is_bnb=bnb, quote_amount_wei=t['gross'], date=d))
        row = platform_day([], daily, d, complete)
        row.update(platform=platform, date=d, start_block=a.get('start_block'), end_block=a.get('end_block'), rpc='pool', complete=complete,
                   launch_events_complete=complete, source_grade=cfg['grade'], raw=[], reason=None if complete else ('不在统计期内' if d < cfg.get('first_date', '0000') else '链上日志读取不完整'))
        if complete:
            row['curve_trade_count'] = len(daily)
            row['curve_volume_bnb'] = str(Decimal(sum(t['curve_bnb_wei'] for t in daily)) / 10**18)
            row['new_launches'] = launches.get(d, 0)
            row['graduated_today'] = grads.get(d, 0)
            row['unique_buyers'] = len({t['actor'] for t in daily if t['side'] == 'buy'})
            row['non_bnb_quote_trades'] = sum(not t['quote_is_bnb'] for t in daily)
            row['scope_note'] = cfg['scope_note']
        rows.append(row)
        out_trades += daily
    result = dict(schema=cfg['schema'], tokens=tokens, lookups=lookups if key == 'four' else {}, trades=trades, launches=launches, grads=grads, done=done)
    dump(prior_path, result)
    return dict(rows=rows, trades=out_trades, errors=errors, rpc_calls=rpc.calls)
