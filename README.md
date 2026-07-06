# Kisan Dashboard — Phase 0 (Ranchi District)

One app: weather + mandi rates + sowing advice + pest alerts + AI disease check.
Bilingual (Hindi default / English). Built on the AgriSens CNN model.

## What's here
```
backend/    FastAPI — serves the disease model + weather/mandi data
frontend/   React dashboard (all 5 modules, calls the backend)
```

## Run the backend (Windows — Acer Predator, VS Code / Git Bash)

1. Copy the trained model into `backend/`:
   Copy `trained_plant_disease_model.keras` from the AgriSens repo
   (`AgriSens/PLANT-DISEASE-IDENTIFICATION/`) into `kisan-dashboard/backend/`.

2. In `backend/`:
   ```
   python -m venv venv
   venv\Scripts\activate          # Git Bash: source venv/Scripts/activate
   pip install -r requirements.txt
   uvicorn app:app --reload --port 8000
   ```

3. Check it: open http://localhost:8000/health  → should show model_present: true
   API docs (try /predict in the browser): http://localhost:8000/docs

## Run the frontend

Easiest for Phase 0 — drop `frontend/KisanDashboard.jsx` into any React setup
(Vite recommended):
```
npm create vite@latest kisan -- --template react
# replace src/App.jsx with KisanDashboard.jsx contents, then:
npm install && npm run dev
```
Keep the backend running on port 8000 — the frontend calls it automatically.

## Endpoints
- GET  /health            model status
- GET  /weather           7-day Ranchi forecast
- GET  /mandi?crop=maize  mandi prices (paddy|maize|arhar|veg)
- POST /predict           upload a leaf image → disease + confidence + advice

## IMPORTANT caveats before the farmer pilot
- The disease model covers 14 crops incl. MAIZE, TOMATO, POTATO, veg —
  but NOT paddy (rice) or arhar/tur, the two biggest Ranchi crops.
  Position disease-check around maize + vegetables for the pilot.
- Model is PlantVillage-trained (clean lab images). Real muddy field photos
  drop accuracy — that's why there's a confidence bar + low-confidence warning.
- Weather + mandi are sample JSON right now. Swap to live APIs (IMD / Agmarknet)
  in Phase 2 — the data shape already matches, so it's a drop-in.

## Next (Phase 2+)
- Wire live IMD weather + Agmarknet mandi APIs
- WhatsApp delivery layer for the 20-farmer pilot
- Offline caching of last-known weather/prices
