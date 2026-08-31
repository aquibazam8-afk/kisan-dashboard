"""
Tests for sowing_advisor.py — the Jun 20-30 sowing-window advisor grounded
in the ATMA Ranchi SREP (Ch. 9) sowing dates and IMD's departure-from-normal
rainfall classification.

Run: python -m unittest test_sowing_advisor -v
"""
import unittest
from datetime import date

from sowing_advisor import (
    assess_kharif_sowing,
    NoRainfallDataError,
    _classify_departure,
    _departure_pct,
    _window_for_year,
)


def _window_records(year, daily_mm, start_day=20, end_day=30):
    """Build {"date", "rain_mm"} records for Jun `start_day`-`end_day` of `year`,
    one record per day at `daily_mm` mm/day (or a list of per-day values)."""
    if isinstance(daily_mm, (int, float)):
        daily_mm = [daily_mm] * (end_day - start_day + 1)
    return [
        {"date": date(year, 6, day).isoformat(), "rain_mm": daily_mm[day - start_day]}
        for day in range(start_day, end_day + 1)
    ]


class DepartureClassificationTests(unittest.TestCase):
    """IMD's departure-from-normal bands, pure function level."""

    def test_departure_pct_basic(self):
        self.assertEqual(_departure_pct(200, 100), 100.0)
        self.assertEqual(_departure_pct(50, 100), -50.0)
        self.assertEqual(_departure_pct(100, 100), 0.0)
        self.assertEqual(_departure_pct(0, 100), -100.0)

    def test_departure_pct_zero_normal_guard(self):
        self.assertEqual(_departure_pct(0, 0), 0.0)
        self.assertGreater(_departure_pct(10, 0), 0)

    def test_classify_large_excess(self):
        self.assertEqual(_classify_departure(60), "Large Excess")
        self.assertEqual(_classify_departure(150), "Large Excess")

    def test_classify_excess(self):
        self.assertEqual(_classify_departure(20), "Excess")
        self.assertEqual(_classify_departure(59), "Excess")

    def test_classify_normal(self):
        self.assertEqual(_classify_departure(19), "Normal")
        self.assertEqual(_classify_departure(-19), "Normal")
        self.assertEqual(_classify_departure(0), "Normal")

    def test_classify_deficient(self):
        self.assertEqual(_classify_departure(-20), "Deficient")
        self.assertEqual(_classify_departure(-59), "Deficient")

    def test_classify_large_deficient(self):
        self.assertEqual(_classify_departure(-60), "Large Deficient")
        self.assertEqual(_classify_departure(-99), "Large Deficient")

    def test_classify_no_rain(self):
        self.assertEqual(_classify_departure(-100), "No Rain")


class SowingWindowTests(unittest.TestCase):
    """The Jun 20-30 window itself (SREP Ch. 9)."""

    def test_window_bounds(self):
        start, end = _window_for_year(2025)
        self.assertEqual(start, date(2025, 6, 20))
        self.assertEqual(end, date(2025, 6, 30))

    def test_ignores_rain_outside_window(self):
        # Heavy rain in early June (before the window) and July (after it)
        # must not count toward the assessed total.
        records = _window_records(2025, 20)  # normal-ish window: 220mm total
        records += _window_records(2024, 20)  # a prior year, so leave-one-out has a normal to compute
        records.append({"date": "2025-06-01", "rain_mm": 500})
        records.append({"date": "2025-07-05", "rain_mm": 500})
        result = assess_kharif_sowing(records, today=date(2025, 7, 10))
        self.assertEqual(result["cumulative_rain_mm"], 220.0)


class AssessKharifSowingTests(unittest.TestCase):
    """End-to-end classification + advisory mapping."""

    def _multi_year_records(self, per_year_daily_mm, assess_year, assess_daily_mm):
        """Build a dataset of several past years (each at a flat daily mm) plus
        the season being assessed, matching the shape /rainfall returns."""
        records = []
        for year, daily in per_year_daily_mm.items():
            records += _window_records(year, daily)
        records += _window_records(assess_year, assess_daily_mm)
        return records

    def test_normal_rainfall_recommends_sow(self):
        # 5 history years all at 20mm/day (220mm total) -> normal = 220mm.
        # Assessed year also at 20mm/day -> 0% departure -> Normal -> sow.
        records = self._multi_year_records(
            {2018: 20, 2019: 20, 2020: 20, 2021: 20, 2022: 20},
            assess_year=2023, assess_daily_mm=20,
        )
        result = assess_kharif_sowing(records, today=date(2023, 6, 30))
        self.assertEqual(result["status"], "sow")
        self.assertEqual(result["category"], "Normal")
        self.assertEqual(result["departure_pct"], 0.0)
        self.assertIsNone(result["alternative_crop"])

    def test_excess_rainfall_recommends_sow(self):
        # Normal = 220mm; assessed year at 30mm/day = 330mm -> +50% -> Excess -> sow.
        records = self._multi_year_records(
            {2018: 20, 2019: 20, 2020: 20, 2021: 20},
            assess_year=2022, assess_daily_mm=30,
        )
        result = assess_kharif_sowing(records, today=date(2022, 6, 30))
        self.assertEqual(result["status"], "sow")
        self.assertEqual(result["category"], "Excess")

    def test_large_excess_recommends_sow(self):
        # 8 history years at 220mm + assessed year at 440mm -> normal ~244.4mm,
        # actual 440mm -> +80% -> Large Excess -> sow.
        records = self._multi_year_records(
            {y: 20 for y in range(2013, 2021)},
            assess_year=2021, assess_daily_mm=40,
        )
        result = assess_kharif_sowing(records, today=date(2021, 6, 30))
        self.assertEqual(result["status"], "sow")
        self.assertEqual(result["category"], "Large Excess")

    def test_deficient_rainfall_recommends_wait(self):
        # Normal = 220mm; assessed year at 15mm/day = 165mm -> -25% -> Deficient -> wait.
        records = self._multi_year_records(
            {2018: 20, 2019: 20, 2020: 20},
            assess_year=2021, assess_daily_mm=15,
        )
        result = assess_kharif_sowing(records, today=date(2021, 6, 30))
        self.assertEqual(result["status"], "wait")
        self.assertEqual(result["category"], "Deficient")
        self.assertIsNotNone(result["wait_window_days"])
        self.assertIsNone(result["alternative_crop"])

    def test_large_deficient_recommends_switch(self):
        # Normal = 220mm; assessed year at 5mm/day = 55mm -> -75% -> Large Deficient -> switch.
        records = self._multi_year_records(
            {2018: 20, 2019: 20},
            assess_year=2020, assess_daily_mm=5,
        )
        result = assess_kharif_sowing(records, today=date(2020, 6, 30))
        self.assertEqual(result["status"], "switch")
        self.assertEqual(result["category"], "Large Deficient")
        self.assertEqual(result["alternative_crop"]["en"], "Maize")

    def test_no_rain_recommends_switch(self):
        # Normal = 220mm; assessed year 0mm -> -100% -> No Rain -> switch.
        records = self._multi_year_records(
            {2018: 20, 2019: 20},
            assess_year=2020, assess_daily_mm=0,
        )
        result = assess_kharif_sowing(records, today=date(2020, 6, 30))
        self.assertEqual(result["status"], "switch")
        self.assertEqual(result["category"], "No Rain")

    def test_reasoning_includes_departure_and_mm_figures(self):
        records = self._multi_year_records(
            {2018: 20, 2019: 20},
            assess_year=2020, assess_daily_mm=5,
        )
        result = assess_kharif_sowing(records, today=date(2020, 6, 30))
        en = result["reasoning"]["en"]
        hi = result["reasoning"]["hi"]
        departure_str = f"{result['departure_pct']:+.0f}%"
        self.assertIn("Large Deficient", en)
        self.assertIn(f"{result['cumulative_rain_mm']}mm", en)
        self.assertIn(f"{result['normal_rain_mm']}mm", en)
        self.assertIn(departure_str, en)
        self.assertIn("Large Deficient", hi)
        self.assertIn(departure_str, hi)

    def test_falls_back_to_most_recent_complete_window(self):
        # "today" is in a year with no window data yet -> falls back to the
        # latest year that does have data, and flags it via `note`.
        records = self._multi_year_records(
            {2018: 20, 2019: 20},
            assess_year=2023, assess_daily_mm=20,
        )
        result = assess_kharif_sowing(records, today=date(2025, 8, 31))
        self.assertFalse(result["current_season"])
        self.assertEqual(result["season"], "2023")
        self.assertIsNotNone(result["note"])

    def test_uses_current_season_when_available(self):
        records = self._multi_year_records(
            {2018: 20, 2019: 20},
            assess_year=2020, assess_daily_mm=20,
        )
        result = assess_kharif_sowing(records, today=date(2020, 6, 30))
        self.assertTrue(result["current_season"])
        self.assertIsNone(result["note"])

    def test_current_season_partial_window_capped_at_today(self):
        # Mid-window "today" (Jun 25): only Jun 20-25 data should count,
        # not the full Jun 20-30 window.
        records = _window_records(2020, 20, start_day=20, end_day=30)
        records += _window_records(2019, 20)  # a prior year, so leave-one-out has a normal to compute
        result = assess_kharif_sowing(records, today=date(2020, 6, 25))
        self.assertTrue(result["current_season"])
        self.assertEqual(result["as_of"], "2020-06-25")
        self.assertEqual(result["cumulative_rain_mm"], 20 * 6)  # Jun 20-25 inclusive

    def test_no_data_at_all_raises(self):
        with self.assertRaises(NoRainfallDataError):
            assess_kharif_sowing([], today=date(2025, 6, 30))

    def test_single_year_dataset_raises_no_normal_available(self):
        # Only the assessed year is on record, so a leave-one-out normal
        # has nothing to average — this must fail loudly, not silently
        # fall back to comparing the year against itself.
        records = _window_records(2020, 20)
        with self.assertRaises(NoRainfallDataError):
            assess_kharif_sowing(records, today=date(2020, 6, 30))

    def test_malformed_records_are_skipped_not_fatal(self):
        records = _window_records(2020, 20)
        records += _window_records(2019, 20)
        records.append({"date": "not-a-date", "rain_mm": 999})
        records.append({"rain_mm": 50})  # missing date
        result = assess_kharif_sowing(records, today=date(2020, 6, 30))
        self.assertEqual(result["cumulative_rain_mm"], 220.0)

    def test_normal_excludes_assessed_year_leave_one_out(self):
        # Proper climatological practice: a year's normal must be built
        # only from *other* years, never from its own data. Prove it by
        # varying the assessed year's own rainfall while holding the
        # history years fixed — the computed normal must not move.
        records_low = self._multi_year_records(
            {2018: 20, 2019: 20}, assess_year=2020, assess_daily_mm=5,
        )
        records_high = self._multi_year_records(
            {2018: 20, 2019: 20}, assess_year=2020, assess_daily_mm=80,
        )
        result_low = assess_kharif_sowing(records_low, today=date(2020, 6, 30))
        result_high = assess_kharif_sowing(records_high, today=date(2020, 6, 30))

        # Normal = average of 2018 + 2019 only (220mm each) = 220mm, in both
        # cases — the assessed year's own value (55mm vs. 880mm) never
        # entered the average.
        self.assertEqual(result_low["normal_rain_mm"], 220.0)
        self.assertEqual(result_high["normal_rain_mm"], 220.0)
        self.assertEqual(result_low["normal_years_count"], 2)
        self.assertEqual(result_high["normal_years_count"], 2)
        # Sanity check this isn't a trivial always-equal case: the actuals
        # (and resulting departures) genuinely differ between the two runs.
        self.assertNotEqual(result_low["cumulative_rain_mm"], result_high["cumulative_rain_mm"])
        self.assertNotEqual(result_low["departure_pct"], result_high["departure_pct"])

    def test_normal_years_count_reflects_dataset_span(self):
        records = self._multi_year_records(
            {2018: 20, 2019: 20, 2020: 20, 2021: 20, 2022: 20, 2023: 20},
            assess_year=2024, assess_daily_mm=20,
        )
        result = assess_kharif_sowing(records, today=date(2024, 6, 30))
        self.assertEqual(result["normal_years_count"], 6)  # 2018-2023, excluding assessed 2024


if __name__ == "__main__":
    unittest.main()
