"""
Tests for the live -> snapshot -> sample/empty fallback order in app.py's
/rainfall, /sowing-advisory, /mandi and /data-status endpoints, and the
live -> unavailable fallback of /weather. No network: the live fetch functions
(or requests.get) are patched, and snapshots go to a temp dir.

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


# Real Open-Meteo response for Ranchi, captured 2026-10-22 with the same
# query parameters _fetch_open_meteo_days sends.
OPEN_METEO_RESPONSE = {
    "latitude": 23.30404, "longitude": 85.27807, "generationtime_ms": 5.735039710998535,
    "utc_offset_seconds": 19800, "timezone": "Asia/Kolkata", "timezone_abbreviation": "GMT+5:30",
    "elevation": 650.0,
    "daily_units": {"time": "iso8601", "temperature_2m_max": "°C", "temperature_2m_min": "°C",
                    "precipitation_sum": "mm", "weathercode": "wmo code"},
    "daily": {
        "time": ["2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25",
                 "2026-10-26", "2026-10-27", "2026-10-28"],
        "temperature_2m_max": [26.8, 26.6, 26.2, 26.5, 26.9, 26.7, 22.6],
        "temperature_2m_min": [17.1, 16.9, 17.0, 16.4, 17.2, 16.5, 19.7],
        "precipitation_sum": [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 27.00],
        "weathercode": [3, 2, 0, 0, 1, 3, 80],
    },
}


def _open_meteo_get(payload):
    """A requests.get stand-in that returns `payload` as the JSON body."""
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return mock.Mock(return_value=resp)


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
            mock.patch.dict(app._weather_cache, {"days": None, "fetched_at": 0.0}),
            # Never touch the network: live is unreachable unless a test says otherwise.
            mock.patch.object(app, "_fetch_rainfall_records", _fail),
            mock.patch.object(app, "_fetch_agmarknet_records", _fail),
            mock.patch.object(app.requests, "get", _fail),
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


class WeatherTests(FallbackTestCase):
    DAY_KEYS = {"day", "tmax", "tmin", "rain_mm", "cond"}

    def live_weather(self, payload):
        get = _open_meteo_get(payload)
        p = mock.patch.object(app.requests, "get", get)
        p.start()
        self.addCleanup(p.stop)
        return get

    def assert_weather_shape(self, resp):
        self.assertEqual(set(resp), {"location", "updated", "days", "source"})
        self.assertEqual(set(resp["location"]), {"en", "hi"})
        self.assertEqual(len(resp["days"]), 7)
        for d in resp["days"]:
            self.assertEqual(set(d), self.DAY_KEYS)
            self.assertEqual(set(d["day"]), {"en", "hi"})
            self.assertEqual(set(d["cond"]), {"en", "hi"})
            for k in ("tmax", "tmin", "rain_mm"):
                self.assertIsInstance(d[k], (int, float))

    def test_live_maps_open_meteo_response(self):
        get = self.live_weather(OPEN_METEO_RESPONSE)
        resp = app.weather()
        self.assertEqual(resp["source"], "live")
        self.assertEqual(resp["updated"], date.today().isoformat())
        self.assertEqual(get.call_args.kwargs["timeout"], 10)
        # 2026-10-22 is a Thursday.
        self.assertEqual(resp["days"][0], {
            "day": {"en": "Thu", "hi": "गुरु"}, "tmax": 27, "tmin": 17, "rain_mm": 0.0,
            "cond": {"en": "Cloudy", "hi": "बादल"},
        })
        self.assertEqual(resp["days"][6], {
            "day": {"en": "Wed", "hi": "बुध"}, "tmax": 23, "tmin": 20, "rain_mm": 27.0,
            "cond": {"en": "Showers", "hi": "बौछारें"},
        })
        self.assertEqual(
            [d["cond"]["en"] for d in resp["days"]],
            ["Cloudy", "Partly cloudy", "Sunny", "Sunny", "Sunny", "Cloudy", "Showers"],
        )
        self.assertEqual(app.data_status()["weather"],
                         {"source": "live", "as_of": date.today().isoformat()})

    def test_live_is_cached(self):
        get = self.live_weather(OPEN_METEO_RESPONSE)
        app.weather()
        app.weather()
        app.data_status()
        self.assertEqual(get.call_count, 1)

    def test_failed_fetch_is_unavailable(self):
        resp = app.weather()  # requests.get raises (see setUp)
        self.assertEqual(resp, {
            "location": app.WEATHER_LOCATION, "updated": None, "days": [], "source": "unavailable",
        })
        self.assertEqual(app.data_status()["weather"], {"source": "unavailable", "as_of": None})

    def test_malformed_response_is_unavailable(self):
        self.live_weather({"error": True, "reason": "bad request"})
        self.assertEqual(app.weather()["source"], "unavailable")
        self.assertEqual(app.weather()["days"], [])

    def test_null_values_are_unavailable(self):
        payload = json.loads(json.dumps(OPEN_METEO_RESPONSE))
        payload["daily"]["temperature_2m_max"][3] = None
        self.live_weather(payload)
        self.assertEqual(app.weather()["source"], "unavailable")
        self.assertEqual(app.weather()["days"], [])

    def test_failure_is_not_cached(self):
        self.assertEqual(app.weather()["source"], "unavailable")
        self.live_weather(OPEN_METEO_RESPONSE)
        self.assertEqual(app.weather()["source"], "live")

    def test_keys_unchanged_across_sources(self):
        """Live and unavailable responses have identical top-level keys."""
        unavailable = app.weather()
        self.live_weather(OPEN_METEO_RESPONSE)
        live = app.weather()
        self.assert_weather_shape(live)
        self.assertEqual(set(unavailable), set(live))
        self.assertEqual(live["location"], unavailable["location"])

    def test_wmo_mapping_uses_only_existing_texts(self):
        known_conds = {json.dumps(c, sort_keys=True) for c in app._COND.values()}
        for code in list(range(0, 100)):
            cond = app._condition_for_wmo(code)
            self.assertIn(json.dumps(cond, sort_keys=True), known_conds, code)


class DataStatusTests(FallbackTestCase):
    def test_reports_all_sources(self):
        self.live_rainfall(_fail)
        self.live_mandi(_fail)
        self.write_rain_snapshot({"Ranchi": _rain_records()}, fetched_at="2026-10-02")
        self.assertEqual(app.data_status(), {
            "rainfall": {"source": "snapshot", "as_of": "2026-10-02"},
            "mandi": {"source": "sample", "as_of": None},
            "weather": {"source": "unavailable", "as_of": None},
        })


if __name__ == "__main__":
    unittest.main()
