import unittest

from calendar_integrity import fill_calendar


class CalendarIntegrityTests(unittest.TestCase):
    def test_absent_day_is_unknown_with_no_invented_request(self):
        state = {'days': {'2026-11-01': {'A': {'daily_new_ids': 2}}}}
        config = {'backfill_observed_start': '2026-11-01', 'rpc': 'https://example.invalid',
                  'platforms': [{'id': 'test'}]}
        gaps = fill_calendar(state, config, '2026-11-03')
        self.assertEqual([g['date'] for g in gaps], ['2026-11-02', '2026-11-03'])
        row = state['days']['2026-11-02']
        self.assertIsNone(row['A']['daily_new_ids'])
        self.assertIsNone(row['A']['start_block'])
        self.assertIsNone(row['A']['read_utc'])
        self.assertIsNone(row['B'][0]['new_launches'])
        self.assertIsNone(gaps[0]['url'])

    def test_complete_zero_day_is_preserved(self):
        state = {'days': {'2026-11-01': {'A': {'daily_new_ids': 0, 'complete': True}}}}
        config = {'backfill_observed_start': '2026-11-01', 'rpc': 'x'}
        self.assertEqual(fill_calendar(state, config, '2026-11-01'), [])
        self.assertEqual(state['days']['2026-11-01']['A']['daily_new_ids'], 0)

    def test_gap_invalidates_calendar_average(self):
        state = {'days': {f'2026-11-{n:02}': {'A': {'daily_new_ids': 1}}
                          for n in [1, 2, 3, 4, 5, 6, 8]}}
        config = {'backfill_observed_start': '2026-11-01', 'rpc': 'x'}
        fill_calendar(state, config, '2026-11-08')
        self.assertIsNone(state['days']['2026-11-08']['A']['ma7_new_ids'])
        self.assertEqual(len(fill_calendar(state, config, '2026-11-08')), 1)
