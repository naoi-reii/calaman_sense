from datetime import datetime
from django.test import SimpleTestCase
from .shelf_life import get_season_key, get_shelf_life_estimates, SEASONS


class ShelfLifeTestCase(SimpleTestCase):
    def test_season_mapping_by_month(self):
        # Cool dry: Nov, Dec, Jan, Feb
        self.assertEqual(get_season_key(11), 'cool_dry')
        self.assertEqual(get_season_key(12), 'cool_dry')
        self.assertEqual(get_season_key(1), 'cool_dry')
        self.assertEqual(get_season_key(2), 'cool_dry')

        # Hot dry: Mar, Apr, May
        self.assertEqual(get_season_key(3), 'hot_dry')
        self.assertEqual(get_season_key(4), 'hot_dry')
        self.assertEqual(get_season_key(5), 'hot_dry')

        # Rainy: Jun to Oct
        for m in (6, 7, 8, 9, 10):
            self.assertEqual(get_season_key(m), 'rainy')

    def test_shelf_life_estimates_november(self):
        # Nov date (cool dry season)
        test_date = datetime(2026, 11, 8, 12, 0, 0)
        ripeness_rows = [
            {'key': 'unripe', 'count': 8, 'pct': 57.1},
            {'key': 'ripe', 'count': 4, 'pct': 28.6},
            {'key': 'overripe', 'count': 2, 'pct': 14.3},
        ]
        res = get_shelf_life_estimates(created_at=test_date, ripeness_rows=ripeness_rows)

        self.assertEqual(res['season']['badge'], 'Cool season (Nov–Feb)')
        estimates = {item['key']: item for item in res['estimates']}

        self.assertEqual(estimates['unripe']['shelf_life'], '5–7 days')
        self.assertEqual(estimates['unripe']['count'], 8)

        self.assertEqual(estimates['ripe']['shelf_life'], '2–3 days')
        self.assertEqual(estimates['ripe']['count'], 4)

        self.assertEqual(estimates['overripe']['shelf_life'], '1–2 days')
        self.assertEqual(estimates['overripe']['count'], 2)

    def test_shelf_life_estimates_summer(self):
        # April date (hot dry season)
        test_date = datetime(2026, 4, 15, 12, 0, 0)
        ripeness_rows = [
            {'key': 'unripe', 'count': 5, 'pct': 50.0},
            {'key': 'ripe', 'count': 3, 'pct': 30.0},
            {'key': 'overripe', 'count': 2, 'pct': 20.0},
        ]
        res = get_shelf_life_estimates(created_at=test_date, ripeness_rows=ripeness_rows)

        self.assertEqual(res['season']['badge'], 'Hot season (Mar–May)')
        estimates = {item['key']: item for item in res['estimates']}
        self.assertEqual(estimates['unripe']['shelf_life'], '3–5 days')
        self.assertEqual(estimates['ripe']['shelf_life'], '1–2 days')
        self.assertEqual(estimates['overripe']['shelf_life'], '0–1 day')

    def test_shelf_life_estimates_with_live_location_temp(self):
        # Scan in Quezon City with live ambient temp 31.8°C
        ripeness_rows = [
            {'key': 'unripe', 'count': 8, 'pct': 57.1},
            {'key': 'ripe', 'count': 4, 'pct': 28.6},
            {'key': 'overripe', 'count': 2, 'pct': 14.3},
        ]
        res = get_shelf_life_estimates(
            created_at=datetime(2026, 11, 8, 12, 0, 0),
            ripeness_rows=ripeness_rows,
            ambient_temp=31.8,
            location_name='Quezon City'
        )
        self.assertTrue(res['season']['is_live'])
        self.assertEqual(res['season']['badge'], 'Quezon City (31.8°C)')
        estimates = {item['key']: item for item in res['estimates']}
        # 31.8°C corresponds to high ambient temperature
        self.assertEqual(estimates['unripe']['shelf_life'], '3–5 days')
        self.assertEqual(estimates['ripe']['shelf_life'], '1–2 days')
        self.assertEqual(estimates['overripe']['shelf_life'], '0–1 day')

