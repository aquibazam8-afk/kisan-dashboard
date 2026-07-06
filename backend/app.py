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
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from disease_info import DISEASE_INFO, CLASS_NAMES

# --- Config ----------------------------------------------------------------
BASE = Path(__file__).parent
# Default: model sits next to this file. Change if you keep it in the repo.
MODEL_PATH = os.environ.get("MODEL_PATH", str(BASE / "trained_plant_disease_model.keras"))
DATA_DIR = BASE / "data"
IMG_SIZE = (128, 128)  # must match the model's training input

app = FastAPI(title="Kisan Dashboard API", version="0.1")

# Allow the React dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # dev only; lock down for production
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Model (loaded lazily so the server starts even without TF ready) ------
_model = None


def get_model():
    global _model
    if _model is None:
        import tensorflow as tf  # imported here to keep startup fast
        if not Path(MODEL_PATH).exists():
            raise HTTPException(500, f"Model file not found at {MODEL_PATH}")
        _model = tf.keras.models.load_model(MODEL_PATH)
    return _model


def _load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


# --- Endpoints -------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "model_present": Path(MODEL_PATH).exists()}


@app.get("/weather")
def weather():
    """7-day Ranchi forecast (IMD-shaped sample data; swap to live API later)."""
    return _load_json("weather.json")


@app.get("/mandi")
def mandi(crop: str | None = None):
    """Mandi prices for Ranchi + nearby markets. Optional ?crop=maize filter."""
    data = _load_json("mandi.json")
    if crop:
        return {"crop": crop, "prices": data.get(crop, [])}
    return data


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    """Accept a leaf image, return disease + confidence + bilingual advice."""
    try:
        raw = await file.read()
        img = Image.open(io.BytesIO(raw)).convert("RGB").resize(IMG_SIZE)
    except Exception:
        raise HTTPException(400, "Could not read image. Send a valid JPG/PNG.")

    arr = np.expand_dims(np.array(img, dtype=np.float32), axis=0)
    preds = get_model().predict(arr, verbose=0)[0]

    idx = int(np.argmax(preds))
    confidence = round(float(np.max(preds)) * 100, 1)
    key = CLASS_NAMES[idx]
    info = DISEASE_INFO.get(key, {})
    is_healthy = key.endswith("healthy")

    # Low-confidence guard: don't give a farmer a confident wrong answer.
    low_conf = confidence < 60

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
