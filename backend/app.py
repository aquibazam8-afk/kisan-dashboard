"""
Kisan Dashboard — backend API (Phase 0)
Wraps the AgriSens CNN disease model + serves Ranchi weather/mandi data.

Run:  uvicorn app:app --reload --port 8000
Model: copy trained_plant_disease_model.keras into this backend/ folder,
       OR set MODEL_PATH below to point at the file in the AgriSens repo.
"""
import io
import json
import logging
import os
import time
from datetime import date
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from ai_edge_litert.interpreter import Interpreter

from disease_info import DISEASE_INFO, CLASS_NAMES
from paddy_disease_info import PADDY_DISEASE_INFO, PADDY_CLASS_NAMES
from sowing_advisor import assess_kharif_sowing, NoRainfallDataError

# --- Config ----------------------------------------------------------------
BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

# Default: model sits next to this file. Change if you keep it in the repo.
MODEL_PATH = os.environ.get("MODEL_PATH", str(BASE / "trained_plant_disease_model.tflite"))
PADDY_MODEL_PATH = os.environ.get("PADDY_MODEL_PATH", str(BASE / "paddy_disease_model.tflite"))
DATA_DIR = BASE / "data"
IMG_SIZE = (128, 128)  # must match the PlantVillage model's training input
PADDY_IMG_SIZE = (224, 224)  # must match the paddy MobileNetV2 model's input

# Selected crop (frontend crop id) -> PlantVillage class-name prefix. Only
# these crops are diagnosed with the PlantVillage model, restricted to their
# own classes; paddy has its own model; every other crop is "unsupported".
PLANTVILLAGE_CROP_PREFIX = {"maize": "Corn_(maize)", "potato": "Potato", "tomato": "Tomato"}
PLANTVILLAGE_CROP_LABEL = {
    "maize": {"en": "maize", "hi": "मक्का"},
    "potato": {"en": "potato", "hi": "आलू"},
    "tomato": {"en": "tomato", "hi": "टमाटर"},
}
# Minimum share of the model's probability that must fall on the selected
# crop's classes before we diagnose — below it, the photo isn't that crop.
CROP_MASS_THRESHOLD = 0.5

# Live mandi + rainfall data (data.gov.in). Only read the key from the env —
# never hardcode it. Absent key means these endpoints stay on sample/empty
# data.
DATAGOV_API_KEY = os.environ.get("DATAGOV_API_KEY") or None
AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
RAINFALL_URL = "https://api.data.gov.in/resource/6c05cd1b-ed59-40c2-bc31-e314f39c6971"
MANDI_CACHE_TTL = 3600  # seconds
RAINFALL_CACHE_TTL = 6 * 3600  # rainfall is published daily, so cache longer

# Snapshots of the live data, written by refresh_snapshots.py on a machine
# that can reach api.data.gov.in (Render's servers can't) and committed.
# Served when the live fetch fails, ahead of the bundled sample data.
RAINFALL_SNAPSHOT = DATA_DIR / "rainfall_snapshot.json"
MANDI_SNAPSHOT = DATA_DIR / "mandi_snapshot.json"

# api.data.gov.in silently stalls (no response, no error) on requests' default
# User-Agent — presumably a bot filter. A curl-like UA gets an instant reply.
DATAGOV_HEADERS = {"User-Agent": "curl/8.4.0", "Accept": "*/*"}

# crop key (as used by data/mandi.json and the frontend) -> commodity name
# tokens to match against the Agmarknet "commodity" field.
CROP_COMMODITIES = {
    "paddy": ["Paddy", "Dhan"],
    "maize": ["Maize"],
    "arhar": ["Arhar", "Tur"],
    "tomato": ["Tomato"],
    "potato": ["Potato"],
    "onion": ["Onion"],
    "cauliflower": ["Cauliflower"],
    "veg": ["Vegetables"],
}

app = FastAPI(title="Kisan Dashboard API", version="0.1")

# Allow the React dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # dev only; lock down for production
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models -----------------------------------------------------------------
_model = None
_paddy_model = None
_model_input_details = None
_model_output_details = None
_paddy_input_details = None
_paddy_output_details = None


@app.on_event("startup")
def _load_models():
    """Load both models at startup so the first /predict call isn't slow."""
    global _model, _paddy_model, _model_input_details, _model_output_details
    global _paddy_input_details, _paddy_output_details
    if Path(MODEL_PATH).exists():
        _model = Interpreter(model_path=MODEL_PATH)
        _model.allocate_tensors()
        _model_input_details = _model.get_input_details()
        _model_output_details = _model.get_output_details()
    if Path(PADDY_MODEL_PATH).exists():
        _paddy_model = Interpreter(model_path=PADDY_MODEL_PATH)
        _paddy_model.allocate_tensors()
        _paddy_input_details = _paddy_model.get_input_details()
        _paddy_output_details = _paddy_model.get_output_details()


def get_model():
    if _model is None:
        raise HTTPException(500, f"Model file not found at {MODEL_PATH}")
    return _model, _model_input_details, _model_output_details


def get_paddy_model():
    if _paddy_model is None:
        raise HTTPException(500, f"Paddy model file not found at {PADDY_MODEL_PATH}")
    return _paddy_model, _paddy_input_details, _paddy_output_details


def _load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _load_snapshot(path):
    """Parsed snapshot file, or None if it's missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        logging.warning("snapshot %s unreadable: %s", path.name, type(e).__name__)
        return None


def _iso_date(timestamp):
    return date.fromtimestamp(timestamp).isoformat()


# --- Live mandi prices -------------------------------------------------------
_MANDI_HI = {
    entry["mandi"]["en"]: entry["mandi"]["hi"]
    for entries in _load_json("mandi.json").values()
    for entry in entries
}

_mandi_cache = {"records": None, "fetched_at": 0.0}


def _bilingual_mandi_name(market, district):
    """Bilingual mandi name, reusing known Hindi names where we have them."""
    name = (market or district or "Unknown").strip()
    return {"en": name, "hi": _MANDI_HI.get(name, name)}


def _trend_from_range(modal, low, high):
    """Trend from where modal_price sits between min_price and max_price."""
    if low is None or high is None or high == low:
        return "flat"
    dist_to_high = high - modal
    dist_to_low = modal - low
    if dist_to_high < dist_to_low:
        return "up"
    if dist_to_low < dist_to_high:
        return "down"
    return "flat"


def _fetch_agmarknet_records():
    """Jharkhand mandi records from data.gov.in, cached for MANDI_CACHE_TTL."""
    now = time.time()
    if _mandi_cache["records"] is not None and (now - _mandi_cache["fetched_at"]) < MANDI_CACHE_TTL:
        return _mandi_cache["records"]

    resp = requests.get(
        AGMARKNET_URL,
        params={
            "api-key": DATAGOV_API_KEY,
            "format": "json",
            "limit": 100,
            "filters[state.keyword]": "Jharkhand",
        },
        headers=DATAGOV_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    _mandi_cache["records"] = records
    _mandi_cache["fetched_at"] = now
    return records


def _mandi_data_from_records(records):
    """mandi.json-shaped dict built from Agmarknet records (live or snapshot).

    Falls back to the bundled sample data per-crop when a crop has no
    records.
    """
    fallback = _load_json("mandi.json")
    result = {}
    for crop, tokens in CROP_COMMODITIES.items():
        matches = [
            r for r in records
            if any(tok.lower() in (r.get("commodity") or "").lower() for tok in tokens)
        ]
        entries = []
        for r in matches[:5]:
            try:
                modal = float(r["modal_price"])
            except (KeyError, TypeError, ValueError):
                continue
            low = high = None
            try:
                low = float(r.get("min_price"))
                high = float(r.get("max_price"))
            except (TypeError, ValueError):
                pass
            entries.append({
                "mandi": _bilingual_mandi_name(r.get("market"), r.get("district")),
                "price": modal,
                "unit": "quintal",
                "trend": _trend_from_range(modal, low, high),
            })
        result[crop] = entries or fallback.get(crop, [])
    return result


def _mandi_data():
    """(mandi.json-shaped dict, source, as_of) — never raises.

    Order: live Agmarknet -> committed snapshot -> bundled sample data.
    """
    if DATAGOV_API_KEY:
        try:
            records = _fetch_agmarknet_records()
            if records:
                as_of = _iso_date(_mandi_cache["fetched_at"] or time.time())
                return _mandi_data_from_records(records), "live", as_of
        except Exception as e:
            # Log only the error type: a traceback contains the request URL (and api-key).
            logging.warning("mandi fetch failed: %s", type(e).__name__)

    snapshot = _load_snapshot(MANDI_SNAPSHOT)
    if snapshot and snapshot.get("records"):
        return _mandi_data_from_records(snapshot["records"]), "snapshot", snapshot.get("fetched_at")

    return _load_json("mandi.json"), "sample", None


# --- Live rainfall -----------------------------------------------------------
_rainfall_cache = {}  # district -> {"records": [...], "fetched_at": float}


def _fetch_rainfall_records(district="Ranchi", state="Jharkhand"):
    """Daily district rainfall records from data.gov.in, cached per district."""
    now = time.time()
    cached = _rainfall_cache.get(district)
    if cached is not None and (now - cached["fetched_at"]) < RAINFALL_CACHE_TTL:
        return cached["records"]

    resp = requests.get(
        RAINFALL_URL,
        params={
            "api-key": DATAGOV_API_KEY,
            "format": "json",
            "limit": 1000,
            "filters[State]": state,
            "filters[District]": district,
        },
        headers=DATAGOV_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])

    # The source data has duplicate rows for some dates (same date + value
    # repeated) — dedupe here so every caller gets one row per date.
    deduped = {}
    for r in records:
        date = r.get("Date")
        if date is not None and date not in deduped:
            deduped[date] = r
    records = list(deduped.values())

    _rainfall_cache[district] = {"records": records, "fetched_at": now}
    return records


def _rainfall_records(district):
    """(records, source, as_of) for `district` — never raises.

    Order: live data.gov.in -> committed snapshot. Returns (None, None, None)
    when neither has the district.
    """
    if DATAGOV_API_KEY:
        try:
            records = _fetch_rainfall_records(district)
            fetched_at = _rainfall_cache.get(district, {}).get("fetched_at") or time.time()
            return records, "live", _iso_date(fetched_at)
        except Exception as e:
            # Log only the error type: a traceback contains the request URL (and api-key).
            logging.warning("rainfall fetch failed: %s", type(e).__name__)

    snapshot = _load_snapshot(RAINFALL_SNAPSHOT)
    records = (snapshot or {}).get("districts", {}).get(district)
    if records is not None:
        return records, "snapshot", snapshot.get("fetched_at")

    return None, None, None


# --- Endpoints -------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_present": Path(MODEL_PATH).exists(),
        "paddy_model_present": Path(PADDY_MODEL_PATH).exists(),
    }


@app.get("/weather")
def weather():
    """7-day Ranchi forecast (IMD-shaped sample data; swap to live API later)."""
    return _load_json("weather.json")


@app.get("/mandi")
def mandi(crop: str | None = None):
    """Mandi prices for Ranchi + nearby markets. Optional ?crop=maize filter.

    Uses live Agmarknet (data.gov.in) prices when DATAGOV_API_KEY is set,
    falling back to the committed snapshot, then the bundled sample data.
    The response shape is the same either way (the frontend iterates it);
    /data-status reports which source was used.
    """
    data, _, _ = _mandi_data()
    if crop:
        return {"crop": crop, "prices": data.get(crop, [])}
    return data


@app.get("/rainfall")
def rainfall(district: str = "Ranchi", days: int = 30):
    """Recent daily rainfall for a Jharkhand district (data.gov.in NRSC data).

    Falls back to the committed snapshot when the live fetch fails or
    DATAGOV_API_KEY is unset, and to an empty day list (source/as_of null)
    when the snapshot doesn't have the district either, rather than breaking
    the request.
    """
    records, source, as_of = _rainfall_records(district)
    if records is None:
        return {"district": district, "days": [], "source": None, "as_of": None}

    dated = sorted((r for r in records if r.get("Date")), key=lambda r: r["Date"])
    recent = dated[-days:] if days else dated

    return {
        "district": district,
        "days": [
            {"date": r["Date"], "rain_mm": r.get("Avg_rainfall")}
            for r in recent
        ],
        "source": source,
        "as_of": as_of,
    }


@app.get("/sowing-advisory")
def sowing_advisory(district: str = "Ranchi"):
    """Rainfed Kharif sowing-window recommendation: sow / wait / switch.

    Pulls all cached rainfall records for `district` (not just the last N
    days /rainfall returns) so both the Jun 20-30 sowing-window total and
    the multi-year historical normal used for IMD's departure classification
    are complete (see sowing_advisor.py). If the current season's window has
    no data yet (the upstream feed lags behind today), the advisor falls
    back to the most recent complete window on record and labels the
    response accordingly (`season`, `note`).

    Falls back to the committed rainfall snapshot (real data, just older —
    `source`/`data_as_of` say so; `as_of` keeps its meaning of the last
    rainfall date assessed). Unlike /mandi, it never falls back to sample
    data — a sowing recommendation built on made-up rainfall would be
    misleading rather than merely stale, so it fails loudly instead, but
    only when there's truly no Kharif-season data to work with at all.
    """
    records, source, data_as_of = _rainfall_records(district)
    if records is None:
        raise HTTPException(503, "Could not fetch live rainfall data and no snapshot is available.")

    normalized = [
        {"date": r["Date"], "rain_mm": r.get("Avg_rainfall")}
        for r in records
        if r.get("Date")
    ]

    try:
        result = assess_kharif_sowing(normalized)
    except NoRainfallDataError:
        raise HTTPException(503, "No Kharif-season rainfall data available for this district.")
    return {**result, "source": source, "data_as_of": data_as_of}


@app.get("/data-status")
def data_status(district: str = "Ranchi"):
    """Where /rainfall and /mandi data is currently coming from, and how old it is."""
    _, rain_source, rain_as_of = _rainfall_records(district)
    _, mandi_source, mandi_as_of = _mandi_data()
    return {
        "rainfall": {"source": rain_source, "as_of": rain_as_of},
        "mandi": {"source": mandi_source, "as_of": mandi_as_of},
    }


def _prediction_response(key, confidence, info, is_healthy):
    """Shared response shape for both the PlantVillage and paddy models."""
    low_conf = confidence < 60  # Low-confidence guard: don't give a farmer a confident wrong answer.

    return {
        "status": "ok",
        "class": key,
        "crop": info.get("crop", {"en": "Unknown", "hi": "अज्ञात"}),
        "disease": info.get("disease", {"en": key, "hi": key}),
        "healthy": is_healthy,
        "confidence": confidence,
        "low_confidence": low_conf,
        "description": info.get("desc", {"en": "", "hi": ""}),
        "action": info.get("action", {"en": "", "hi": ""}),
        "note": {
            "en": "Low confidence — please confirm with a local expert or KVK." if low_conf else "",
            "hi": "कम भरोसा — कृपया स्थानीय विशेषज्ञ या KVK से पुष्टि करें।" if low_conf else "",
        },
    }


def _classify_within_crop(preds, crop):
    """(class index, confidence %) restricted to `crop`'s PlantVillage classes.

    `preds` is the model's full 38-class softmax output. Returns None when
    less than CROP_MASS_THRESHOLD of the probability falls on `crop`'s
    classes, i.e. the photo doesn't look like that crop. Confidence is
    renormalized within the crop's classes.
    """
    prefix = PLANTVILLAGE_CROP_PREFIX[crop] + "___"
    idxs = [i for i, name in enumerate(CLASS_NAMES) if name.startswith(prefix)]
    crop_probs = np.asarray(preds, dtype=np.float64)[idxs]
    mass = float(crop_probs.sum())
    if mass < CROP_MASS_THRESHOLD:
        return None
    best = int(np.argmax(crop_probs))
    return idxs[best], round(float(crop_probs[best]) / mass * 100, 1)


@app.post("/predict")
async def predict(file: UploadFile = File(...), crop: str | None = Form(None)):
    """Accept a leaf image, return disease + confidence + bilingual advice.

    crop=paddy routes the image through the paddy MobileNetV2 model;
    maize/potato/tomato use the PlantVillage model restricted to that crop's
    classes ("wrong_crop" if the photo doesn't look like that crop). Any
    other crop (or none) is "unsupported" — we never guess a disease from
    another crop's classes.
    """
    if crop != "paddy" and crop not in PLANTVILLAGE_CROP_PREFIX:
        return {
            "status": "unsupported",
            "message": {
                "en": "Disease check is not available for this crop yet.",
                "hi": "इस फसल के लिए रोग जाँच अभी उपलब्ध नहीं है।",
            },
        }

    try:
        raw = await file.read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Could not read image. Send a valid JPG/PNG.")

    if crop == "paddy":
        arr = np.expand_dims(np.array(img.resize(PADDY_IMG_SIZE), dtype=np.float32), axis=0)
        interpreter, input_details, output_details = get_paddy_model()
        interpreter.set_tensor(input_details[0]["index"], arr)
        interpreter.invoke()
        preds = interpreter.get_tensor(output_details[0]["index"])[0]

        idx = int(np.argmax(preds))
        confidence = round(float(np.max(preds)) * 100, 1)
        key = PADDY_CLASS_NAMES[idx]
        info = PADDY_DISEASE_INFO.get(key, {})
        is_healthy = key == "normal"

        return _prediction_response(key, confidence, info, is_healthy)

    arr = np.expand_dims(np.array(img.resize(IMG_SIZE), dtype=np.float32), axis=0)
    interpreter, input_details, output_details = get_model()
    interpreter.set_tensor(input_details[0]["index"], arr)
    interpreter.invoke()
    preds = interpreter.get_tensor(output_details[0]["index"])[0]

    classified = _classify_within_crop(preds, crop)
    if classified is None:
        label = PLANTVILLAGE_CROP_LABEL[crop]
        return {
            "status": "wrong_crop",
            "message": {
                "en": f"This doesn't look like a {label['en']} leaf — please retake the photo.",
                "hi": f"यह {label['hi']} की पत्ती नहीं लगती — कृपया फिर से फ़ोटो लें।",
            },
        }

    idx, confidence = classified
    key = CLASS_NAMES[idx]
    info = DISEASE_INFO.get(key, {})
    is_healthy = key.endswith("healthy")

    return _prediction_response(key, confidence, info, is_healthy)
