"""
Tests for the live -> snapshot -> sample/empty fallback order in app.py's
/rainfall, /sowing-advisory, /mandi and /data-status endpoints, and the
Open-Meteo -> MET Norway -> unavailable order of /weather. No network: the live fetch functions
(or requests.get) are patched, and snapshots go to a temp dir.

Run: python -m unittest test_data_fallback -v
"""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import requests
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


# Real MET Norway Locationforecast compact response for Ranchi
# (lat=23.34&lon=85.31), captured 2026-10-31 16:00:16 UTC (21:30 IST), and
# the caching headers it came with.
TESTDATA = Path(__file__).parent / "testdata"
MET_NO_RESPONSE = json.loads((TESTDATA / "met_no_compact_ranchi.json").read_text(encoding="utf-8"))
MET_NO_HEADERS = {"Last-Modified": "Sat, 31 Oct 2026 16:00:16 GMT",
                  "Expires": "Sat, 31 Oct 2026 16:30:33 GMT"}
MET_NO_FETCHED = datetime(2026, 10, 31, 16, 0, 16, tzinfo=timezone.utc).timestamp()
MET_NO_EXPIRES = datetime(2026, 10, 31, 16, 30, 33, tzinfo=timezone.utc).timestamp()


def _http_response(status, payload=None, headers=None):
    resp = mock.Mock(status_code=status, headers=headers or {})
    resp.json.return_value = payload
    resp.text = "" if payload is None else json.dumps(payload)
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(str(status), response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


def _weather_get(open_meteo=None, met_no=None):
    """A requests.get stand-in routed by URL. Each provider gets a response,
    or a list of responses (one per call); None means unreachable."""
    routes = {app.OPEN_METEO_URL: open_meteo, app.MET_NO_URL: met_no}

    def get(url, **kwargs):
        r = routes[url]
        if isinstance(r, list):
            r = r.pop(0)
        if r is None:
            raise ConnectionError("unreachable")
        return r
    return mock.Mock(side_effect=get)


def _calls_to(get, url):
    return [c for c in get.call_args_list if c.args[0] == url]


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
            mock.patch.dict(app._met_no_cache, {"timeseries": None, "fetched_at": 0.0,
                                                "last_modified": None, "next_request_at": 0.0}),
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

    def live_weather(self, open_meteo_payload=None, met_no=None):
        """Open-Meteo answers 200 with `open_meteo_payload` (None: unreachable);
        MET Norway answers with `met_no` (see _weather_get)."""
        open_meteo = None if open_meteo_payload is None else _http_response(200, open_meteo_payload)
        get = _weather_get(open_meteo, met_no)
        p = mock.patch.object(app.requests, "get", get)
        p.start()
        self.addCleanup(p.stop)
        return get

    def assert_weather_shape(self, resp):
        self.assertEqual(set(resp), {"location", "updated", "provider", "days", "source"})
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
        self.assertEqual(resp["provider"], "open-meteo")
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
            "location": app.WEATHER_LOCATION, "updated": None, "provider": None, "days": [],
            "source": "unavailable",
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


class MetNoWeatherTests(FallbackTestCase):
    """MET Norway failover, using the captured 2026-10-31 response."""

    DAY_KEYS = WeatherTests.DAY_KEYS
    assert_weather_shape = WeatherTests.assert_weather_shape

    # Cross-checked by bucketing every forecast hour independently.
    EXPECTED_DAYS = [  # Sat 31 Oct is dropped: fetched at 21:30 IST, a part-day.
        ("Sun", 27, 20, 0.5, "Showers"),
        ("Mon", 28, 20, 0.2, "Showers"),
        ("Tue", 27, 19, 0.0, "Cloudy"),
        ("Wed", 23, 21, 0.1, "Cloudy"),
        ("Thu", 23, 18, 0.4, "Cloudy"),
        ("Fri", 26, 18, 0.0, "Sunny"),
        ("Sat", 25, 17, 0.0, "Sunny"),
    ]

    def setUp(self):
        super().setUp()
        self.now = MET_NO_FETCHED
        for patcher in (
            mock.patch.object(app, "time", mock.Mock(time=lambda: self.now)),
            mock.patch.object(app, "_today_ist", lambda: date(2026, 10, 31)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def live_met_no(self, *responses, open_meteo_payload=None):
        get = _weather_get(
            None if open_meteo_payload is None else _http_response(200, open_meteo_payload),
            list(responses),
        )
        p = mock.patch.object(app.requests, "get", get)
        p.start()
        self.addCleanup(p.stop)
        return get

    @staticmethod
    def ok():
        return _http_response(200, MET_NO_RESPONSE, MET_NO_HEADERS)

    def summary(self, resp):
        return [(d["day"]["en"], d["tmax"], d["tmin"], d["rain_mm"], d["cond"]["en"]) for d in resp["days"]]

    def test_used_when_open_meteo_fails(self):
        get = self.live_met_no(self.ok())
        resp = app.weather()
        self.assertEqual(resp["source"], "live")
        self.assertEqual(resp["provider"], "met-no")
        self.assertEqual(resp["location"], app.WEATHER_LOCATION)
        self.assertEqual(self.summary(resp), self.EXPECTED_DAYS)
        self.assertEqual(resp["days"][0]["day"], {"en": "Sun", "hi": "रवि"})
        self.assertEqual(resp["days"][0]["cond"], {"en": "Showers", "hi": "बौछारें"})
        self.assertEqual(app.data_status()["weather"]["source"], "live")

        (call,) = _calls_to(get, app.MET_NO_URL)
        self.assertEqual(call.kwargs["params"], {"lat": 23.34, "lon": 85.31})
        self.assertEqual(call.kwargs["headers"],
                         {"User-Agent": "KisanDashboard/1.0 github.com/aquibazam8-afk/kisan-dashboard"})
        self.assertEqual(call.kwargs["timeout"], 10)

    def test_same_shape_as_open_meteo(self):
        self.live_met_no(self.ok())
        self.assert_weather_shape(app.weather())

    def test_not_asked_when_open_meteo_works(self):
        get = self.live_met_no(self.ok(), open_meteo_payload=OPEN_METEO_RESPONSE)
        self.assertEqual(app.weather()["provider"], "open-meteo")
        self.assertEqual(_calls_to(get, app.MET_NO_URL), [])

    def test_both_failing_is_unavailable(self):
        self.live_met_no(_http_response(503, {"error": "down"}))
        resp = app.weather()
        self.assertEqual((resp["source"], resp["provider"], resp["days"]), ("unavailable", None, []))

    def test_no_request_before_expires_then_if_modified_since(self):
        get = self.live_met_no(
            self.ok(),
            _http_response(304, headers={"Expires": "Sat, 31 Oct 2026 17:01:00 GMT"}),
        )
        first = app.weather()

        # 30 min TTL has passed but Expires (16:30:33) hasn't: still cached.
        self.now = MET_NO_FETCHED + 30 * 60 + 5
        self.assertEqual(app.weather(), first)
        self.assertEqual(len(_calls_to(get, app.MET_NO_URL)), 1)

        # Past Expires: conditional request; 304 keeps the stored forecast.
        self.now = MET_NO_EXPIRES + 1
        self.assertEqual(self.summary(app.weather()), self.EXPECTED_DAYS)
        calls = _calls_to(get, app.MET_NO_URL)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].kwargs["headers"]["If-Modified-Since"], "Sat, 31 Oct 2026 16:00:16 GMT")
        self.assertEqual(calls[1].kwargs["headers"]["User-Agent"], app.MET_NO_USER_AGENT)

        # The 304's new Expires (17:01) is respected too.
        self.now = MET_NO_EXPIRES + 30 * 60 + 5  # 17:00:38
        app.weather()
        self.assertEqual(len(_calls_to(get, app.MET_NO_URL)), 2)

    def test_failure_backs_off_before_retrying(self):
        get = self.live_met_no(_http_response(429, {"error": "throttled"}), self.ok())
        self.assertEqual(app.weather()["source"], "unavailable")
        self.now += 60
        self.assertEqual(app.weather()["source"], "unavailable")
        self.assertEqual(len(_calls_to(get, app.MET_NO_URL)), 1)  # no retry yet
        self.now += 30 * 60
        self.assertEqual(app.weather()["provider"], "met-no")
        self.assertEqual(len(_calls_to(get, app.MET_NO_URL)), 2)

    def test_days_roll_over_at_midnight(self):
        self.live_met_no(self.ok())
        app.weather()
        with mock.patch.object(app, "_today_ist", lambda: date(2026, 11, 2)):
            days = self.summary(app.weather())  # cached data, re-derived
        self.assertEqual([d[0] for d in days], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])

    def test_too_short_forecast_is_unavailable(self):
        short = json.loads(json.dumps(MET_NO_RESPONSE))
        short["properties"]["timeseries"] = short["properties"]["timeseries"][:60]
        self.live_met_no(_http_response(200, short, MET_NO_HEADERS))
        self.assertEqual(app.weather()["source"], "unavailable")

    def test_missing_precipitation_is_unavailable(self):
        broken = json.loads(json.dumps(MET_NO_RESPONSE))
        del broken["properties"]["timeseries"][5]["data"]["next_1_hours"]["details"]["precipitation_amount"]
        self.live_met_no(_http_response(200, broken, MET_NO_HEADERS))
        self.assertEqual(app.weather()["source"], "unavailable")

    def test_precipitation_not_double_counted(self):
        """Steady 1 mm/h rain, laid out like the real response: hourly entries
        that also carry next_6_hours, then 6-hourly entries. Every whole IST
        day — including the one where the step changes — must total 24 mm."""
        def entry(t, one=True, six=True):
            data = {"instant": {"details": {"air_temperature": 20.0}}}
            if one:
                data["next_1_hours"] = {"summary": {"symbol_code": "rain"},
                                        "details": {"precipitation_amount": 1.0}}
            if six:
                data["next_6_hours"] = {"summary": {"symbol_code": "rain"},
                                        "details": {"precipitation_amount": 6.0}}
            return {"time": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "data": data}

        start = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)   # 23:30 IST
        switch = datetime(2026, 11, 3, 6, tzinfo=timezone.utc)    # hourly -> 6-hourly
        end = switch + timedelta(days=8)
        ts = []
        t = start
        while t < switch:
            ts.append(entry(t))
            t += timedelta(hours=1)
        while t < end:
            ts.append(entry(t, one=False))
            t += timedelta(hours=6)
        ts.append(entry(end, one=False, six=False))  # last entry: instant only

        days = app._met_no_days(ts, date(2026, 11, 1))
        self.assertEqual([d["rain_mm"] for d in days], [24.0] * 7)
        self.assertEqual(days[0]["day"]["en"], "Sun")  # 1 Nov; 31 Oct is a part-day

    def test_met_symbols_map_to_existing_texts(self):
        cases = {
            "clearsky_day": "Sunny", "fair_night": "Sunny", "partlycloudy_polartwilight": "Partly cloudy",
            "cloudy": "Cloudy", "fog": "Cloudy", "lightrain": "Light rain", "lightsleet": "Light rain",
            "rain": "Rain", "heavyrain": "Rain", "sleet": "Rain", "lightsnow": "Rain",
            "lightrainshowers_day": "Showers", "heavyrainshowers_night": "Showers",
            "rainshowersandthunder_day": "Rain", "heavysnowshowers_day": "Rain", "unknownsymbol": "Cloudy",
        }
        for symbol, text in cases.items():
            self.assertEqual(app._COND[app._condition_key_for_met_symbol(symbol)]["en"], text, symbol)


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
