"""
Tests for the live -> snapshot -> sample/empty fallback order in app.py's
/rainfall, /sowing-advisory, /mandi and /data-status endpoints. No network:
the live fetch functions are patched, and snapshots go to a temp dir.

Run: python -m unittest test_data_fallback -v
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

import app


def _rain_records(years=(2023, 2024, 2025), daily_mm=5.0):
    """Raw data.gov.in-shaped rainfall records covering Jun 20-30 of `years`."""
    return [
        {"Date": date(y, 6, d).isoformat(), "Avg_rainfall": daily_mm}
        for y in years
        for d in range(20, 31)
    ]


AGMARKNET_RECORDS = [
    {"commodity": "Maize", "market": "Ranchi", "district": "Ranchi",
     "modal_price": "2100", "min_price": "2000", "max_price": "2150"},
]
SNAPSHOT_AGMARKNET_RECORDS = [
    {"commodity": "Maize", "market": "Ranchi", "district": "Ranchi",
     "modal_price": "1900", "min_price": "1800", "max_price": "2000"},
]


def _fail(*args, **kwargs):
    raise ConnectionError("unreachable")


class FallbackTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rain_snap = self.tmp / "rainfall_snapshot.json"
        self.mandi_snap = self.tmp / "mandi_snapshot.json"
        for patcher in (
            mock.patch.object(app, "DATAGOV_API_KEY", "test-key"),
            mock.patch.object(app, "RAINFALL_SNAPSHOT", self.rain_snap),
            mock.patch.object(app, "MANDI_SNAPSHOT", self.mandi_snap),
            mock.patch.dict(app._rainfall_cache, clear=True),
            mock.patch.dict(app._mandi_cache, {"records": None, "fetched_at": 0.0}),
            # Never touch the network: live is unreachable unless a test says otherwise.
            mock.patch.object(app, "_fetch_rainfall_records", _fail),
            mock.patch.object(app, "_fetch_agmarknet_records", _fail),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def live_rainfall(self, fn):
        p = mock.patch.object(app, "_fetch_rainfall_records", fn)
        p.start()
        self.addCleanup(p.stop)

    def live_mandi(self, fn):
        p = mock.patch.object(app, "_fetch_agmarknet_records", fn)
        p.start()
        self.addCleanup(p.stop)

    def write_rain_snapshot(self, districts, fetched_at="2026-10-01"):
        self.rain_snap.write_text(json.dumps({"fetched_at": fetched_at, "districts": districts}))

    def write_mandi_snapshot(self, records, fetched_at="2026-10-01"):
        self.mandi_snap.write_text(json.dumps({"fetched_at": fetched_at, "records": records}))


class RainfallFallbackTests(FallbackTestCase):
    def test_live_wins_over_snapshot(self):
        self.live_rainfall(lambda d: _rain_records(daily_mm=9.0))
        self.write_rain_snapshot({"Ranchi": _rain_records(daily_mm=1.0)})
        resp = app.rainfall("Ranchi", days=1)
        self.assertEqual(resp["source"], "live")
        self.assertEqual(resp["as_of"], date.today().isoformat())
        self.assertEqual(resp["days"][0]["rain_mm"], 9.0)

    def test_live_failure_serves_snapshot(self):
        self.live_rainfall(_fail)
        self.write_rain_snapshot({"Ranchi": _rain_records(daily_mm=1.0)})
        resp = app.rainfall("Ranchi", days=2)
        self.assertEqual(resp["source"], "snapshot")
        self.assertEqual(resp["as_of"], "2026-10-01")
        self.assertEqual(len(resp["days"]), 2)
        self.assertEqual(resp["days"][-1], {"date": "2025-06-30", "rain_mm": 1.0})

    def test_no_key_serves_snapshot_without_trying_live(self):
        live = mock.Mock(side_effect=_fail)
        self.live_rainfall(live)
        self.write_rain_snapshot({"Ranchi": _rain_records()})
        with mock.patch.object(app, "DATAGOV_API_KEY", None):
            resp = app.rainfall("Ranchi", days=30)
        live.assert_not_called()
        self.assertEqual(resp["source"], "snapshot")

    def test_live_failure_without_snapshot_is_empty(self):
        self.live_rainfall(_fail)
        resp = app.rainfall("Ranchi", days=30)
        self.assertEqual(resp, {"district": "Ranchi", "days": [], "source": None, "as_of": None})

    def test_snapshot_missing_district_is_empty(self):
        self.live_rainfall(_fail)
        self.write_rain_snapshot({"Ranchi": _rain_records()})
        resp = app.rainfall("Gumla", days=30)
        self.assertEqual(resp["days"], [])
        self.assertIsNone(resp["source"])

    def test_corrupt_snapshot_is_treated_as_missing(self):
        self.live_rainfall(_fail)
        self.rain_snap.write_text("{not json")
        resp = app.rainfall("Ranchi", days=30)
        self.assertEqual(resp["days"], [])
        self.assertIsNone(resp["source"])


class SowingAdvisoryFallbackTests(FallbackTestCase):
    def test_live_failure_serves_snapshot(self):
        self.live_rainfall(_fail)
        self.write_rain_snapshot({"Ranchi": _rain_records()})
        resp = app.sowing_advisory("Ranchi")
        self.assertEqual(resp["source"], "snapshot")
        self.assertEqual(resp["data_as_of"], "2026-10-01")
        # The advisor's own as_of (last rainfall date assessed) is untouched.
        self.assertEqual(resp["as_of"], "2025-06-30")
        self.assertIn(resp["status"], {"sow", "wait", "switch"})

    def test_live_source_reported(self):
        self.live_rainfall(lambda d: _rain_records())
        resp = app.sowing_advisory("Ranchi")
        self.assertEqual(resp["source"], "live")
        self.assertEqual(resp["data_as_of"], date.today().isoformat())

    def test_live_failure_without_snapshot_is_503(self):
        self.live_rainfall(_fail)
        with self.assertRaises(HTTPException) as ctx:
            app.sowing_advisory("Ranchi")
        self.assertEqual(ctx.exception.status_code, 503)


class MandiFallbackTests(FallbackTestCase):
    def setUp(self):
        super().setUp()
        self.sample = app._load_json("mandi.json")

    def test_live_wins_over_snapshot(self):
        self.live_mandi(lambda: AGMARKNET_RECORDS)
        self.write_mandi_snapshot(SNAPSHOT_AGMARKNET_RECORDS)
        data = app.mandi()
        self.assertEqual(data["maize"][0]["price"], 2100.0)
        self.assertEqual(app.data_status()["mandi"]["source"], "live")

    def test_live_failure_serves_snapshot(self):
        self.live_mandi(_fail)
        self.write_mandi_snapshot(SNAPSHOT_AGMARKNET_RECORDS)
        data = app.mandi()
        self.assertEqual(data["maize"][0]["price"], 1900.0)
        self.assertEqual(app.data_status()["mandi"], {"source": "snapshot", "as_of": "2026-10-01"})

    def test_live_empty_serves_snapshot(self):
        self.live_mandi(lambda: [])
        self.write_mandi_snapshot(SNAPSHOT_AGMARKNET_RECORDS)
        self.assertEqual(app.mandi()["maize"][0]["price"], 1900.0)

    def test_live_failure_without_snapshot_serves_sample(self):
        self.live_mandi(_fail)
        self.assertEqual(app.mandi(), self.sample)
        self.assertEqual(app.data_status()["mandi"], {"source": "sample", "as_of": None})

    def test_response_shape_unchanged_across_sources(self):
        """Same crop keys and per-entry fields whatever the source, and no
        source/as_of fields leak into /mandi itself."""
        self.live_mandi(_fail)
        sample = app.mandi()
        self.write_mandi_snapshot(SNAPSHOT_AGMARKNET_RECORDS)
        snapshot = app.mandi()
        self.assertEqual(set(snapshot), set(sample))
        self.assertNotIn("source", snapshot)
        for crop, entries in snapshot.items():
            for entry in entries:
                self.assertEqual(set(entry), {"mandi", "price", "unit", "trend"})
        self.assertEqual(
            app.mandi(crop="maize"),
            {"crop": "maize", "prices": snapshot["maize"]},
        )


class DataStatusTests(FallbackTestCase):
    def test_reports_both_sources(self):
        self.live_rainfall(_fail)
        self.live_mandi(_fail)
        self.write_rain_snapshot({"Ranchi": _rain_records()}, fetched_at="2026-10-02")
        self.assertEqual(app.data_status(), {
            "rainfall": {"source": "snapshot", "as_of": "2026-10-02"},
            "mandi": {"source": "sample", "as_of": None},
        })


if __name__ == "__main__":
    unittest.main()
