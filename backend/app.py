"""
Kisan Dashboard — backend API (Phase 0)
Wraps the AgriSens CNN disease model + serves Ranchi weather/mandi data.

Run:  uvicorn app:app --reload --port 8000
Model: copy trained_plant_disease_model.keras into this backend/ folder,
       OR set MODEL_PATH below to point at the file in the AgriSens repo.
"""
import io
import json
import os
import time
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from disease_info import DISEASE_INFO, CLASS_NAMES
from paddy_disease_info import PADDY_DISEASE_INFO, PADDY_CLASS_NAMES

# --- Config ----------------------------------------------------------------
BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

# Default: model sits next to this file. Change if you keep it in the repo.
MODEL_PATH = os.environ.get("MODEL_PATH", str(BASE / "trained_plant_disease_model.keras"))
PADDY_MODEL_PATH = os.environ.get("PADDY_MODEL_PATH", str(BASE / "paddy_disease_model.keras"))
DATA_DIR = BASE / "data"
IMG_SIZE = (128, 128)  # must match the PlantVillage model's training input
PADDY_IMG_SIZE = (224, 224)  # must match the paddy MobileNetV2 model's input

# Live mandi + rainfall data (data.gov.in). Only read the key from the env —
# never hardcode it. Absent key means these endpoints stay on sample/empty
# data.
DATAGOV_API_KEY = os.environ.get("DATAGOV_API_KEY") or None
AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
RAINFALL_URL = "https://api.data.gov.in/resource/6c05cd1b-ed59-40c2-bc31-e314f39c6971"
MANDI_CACHE_TTL = 3600  # seconds
RAINFALL_CACHE_TTL = 6 * 3600  # rainfall is published daily, so cache longer

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


@app.on_event("startup")
def _load_models():
    """Load both models at startup so the first /predict call isn't slow."""
    global _model, _paddy_model
    import tensorflow as tf
    if Path(MODEL_PATH).exists():
        _model = tf.keras.models.load_model(MODEL_PATH)
    if Path(PADDY_MODEL_PATH).exists():
        _paddy_model = tf.keras.models.load_model(PADDY_MODEL_PATH)


def get_model():
    if _model is None:
        raise HTTPException(500, f"Model file not found at {MODEL_PATH}")
    return _model


def get_paddy_model():
    if _paddy_model is None:
        raise HTTPException(500, f"Paddy model file not found at {PADDY_MODEL_PATH}")
    return _paddy_model


def _load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


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


def _live_mandi_data():
    """mandi.json-shaped dict built from live Agmarknet records.

    Falls back to the bundled sample data per-crop when live coverage is
    missing, and for the whole dataset if the fetch fails or times out, so
    the app never breaks.
    """
    fallback = _load_json("mandi.json")
    try:
        records = _fetch_agmarknet_records()
    except Exception:
        return fallback

    if not records:
        return fallback

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
    falling back to the bundled sample data otherwise or on any failure.
    """
    data = _live_mandi_data() if DATAGOV_API_KEY else _load_json("mandi.json")
    if crop:
        return {"crop": crop, "prices": data.get(crop, [])}
    return data


@app.get("/rainfall")
def rainfall(district: str = "Ranchi", days: int = 30):
    """Recent daily rainfall for a Jharkhand district (data.gov.in NRSC data).

    Returns an empty day list when DATAGOV_API_KEY is unset or the live fetch
    fails, rather than breaking the request.
    """
    if not DATAGOV_API_KEY:
        return {"district": district, "days": []}

    try:
        records = _fetch_rainfall_records(district)
    except Exception:
        return {"district": district, "days": []}

    dated = sorted((r for r in records if r.get("Date")), key=lambda r: r["Date"])
    recent = dated[-days:] if days else dated

    return {
        "district": district,
        "days": [
            {"date": r["Date"], "rain_mm": r.get("Avg_rainfall")}
            for r in recent
        ],
    }


def _prediction_response(key, confidence, info, is_healthy):
    """Shared response shape for both the PlantVillage and paddy models."""
    low_conf = confidence < 60  # Low-confidence guard: don't give a farmer a confident wrong answer.

    return {
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


@app.post("/predict")
async def predict(file: UploadFile = File(...), crop: str | None = Form(None)):
    """Accept a leaf image, return disease + confidence + bilingual advice.

    ?crop=paddy routes the image through the paddy MobileNetV2 model;
    any other value (or none) keeps the existing PlantVillage behavior.
    """
    try:
        raw = await file.read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Could not read image. Send a valid JPG/PNG.")

    if crop == "paddy":
        arr = np.expand_dims(np.array(img.resize(PADDY_IMG_SIZE), dtype=np.float32), axis=0)
        preds = get_paddy_model().predict(arr, verbose=0)[0]

        idx = int(np.argmax(preds))
        confidence = round(float(np.max(preds)) * 100, 1)
        key = PADDY_CLASS_NAMES[idx]
        info = PADDY_DISEASE_INFO.get(key, {})
        is_healthy = key == "normal"

        return _prediction_response(key, confidence, info, is_healthy)

    arr = np.expand_dims(np.array(img.resize(IMG_SIZE), dtype=np.float32), axis=0)
    preds = get_model().predict(arr, verbose=0)[0]

    idx = int(np.argmax(preds))
    confidence = round(float(np.max(preds)) * 100, 1)
    key = CLASS_NAMES[idx]
    info = DISEASE_INFO.get(key, {})
    is_healthy = key.endswith("healthy")

    return _prediction_response(key, confidence, info, is_healthy)
