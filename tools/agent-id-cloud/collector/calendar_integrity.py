"""Expose uncollected calendar days without inventing reads, blocks or zeroes."""
import datetime as dt

from core import mean_complete, platform_day


def fill_calendar(state, config, through):
    gaps = []
    date = dt.date.fromisoformat(config['backfill_observed_start'])
    end = dt.date.fromisoformat(through)
    reason = '该UTC日无采集记录；仅登记U占位，未请求历史区块；本轮daily不回填历史日'
    while date <= end:
        key = date.isoformat()
        if key not in state['days']:
            a = dict(date=key, daily_new_ids=None, cumulative_ids=None,
                     agent_id_holders=None, busiest_hour_share=None,
                     sequence_name_share_e4=None, start_block=None, end_block=None,
                     rpc=config['rpc'], complete=False, read_utc=None, raw=[])
            platforms = []
            for p in config.get('platforms', []):
                row = platform_day([], [], key, False)
                row.update(platform=p['id'], date=key, complete=False,
                           start_block=None, end_block=None, rpc=config['rpc'],
                           raw=[], reason=reason)
                platforms.append(row)
            state['days'][key] = dict(A=a, B=platforms, E=[], C={},
                                      bnb_price={}, calendar_missing=True)
        if state['days'][key].get('calendar_missing'):
            if state['days'][key].get('bnb_price') is None:
                state['days'][key]['bnb_price'] = {}
            gaps.append(dict(module='A–G/缺日', date=key, reason=reason,
                             url=None, blocks=None, rpc=config['rpc']))
        date += dt.timedelta(days=1)
    # Seven calendar days, never the last seven observed rows across a gap.
    for key, record in state['days'].items():
        date = dt.date.fromisoformat(key)
        values = [state['days'].get((date-dt.timedelta(days=n)).isoformat(), {})
                  .get('A', {}).get('daily_new_ids') for n in range(6, -1, -1)]
        record['A']['ma7_new_ids'] = mean_complete(values)
    return gaps
