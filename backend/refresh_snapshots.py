"""
Refresh the data.gov.in snapshots the API falls back to when it can't reach
api.data.gov.in live (Render's servers can't). Run locally, where it's
reachable, then commit the two files it writes:

    python refresh_snapshots.py [District ...]      (default: Ranchi)

Writes data/rainfall_snapshot.json and data/mandi_snapshot.json, each with a
"fetched_at" ISO date plus the raw records. Reuses app.py's fetch functions;
DATAGOV_API_KEY comes from backend/.env (app.py loads it on import).
"""
import json
import sys
from datetime import date

import app


def _write_snapshot(path, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    # Belt and braces: the records never contain the key, but never let it
    # reach a committed file.
    if app.DATAGOV_API_KEY in text:
        sys.exit(f"Refusing to write {path.name}: it would contain the API key.")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(path)


def _fetch(label, fn, *args):
    """Records from `fn`, or None (with a message) if it fails or is empty."""
    try:
        records = fn(*args)
    except Exception as e:
        # Only the error type: a traceback contains the request URL (and api-key).
        print(f"{label}: fetch failed ({type(e).__name__})")
        return None
    if not records:
        print(f"{label}: no records")
        return None
    print(f"{label}: {len(records)} records")
    return records


def main(districts):
    if not app.DATAGOV_API_KEY:
        sys.exit("DATAGOV_API_KEY is not set (put it in backend/.env).")

    fetched_at = date.today().isoformat()
    ok = True

    # Each snapshot is written only if all of its data came back, so a bad
    # fetch never replaces a good snapshot with a partial or empty one.
    rainfall = {d: _fetch(f"rainfall {d}", app._fetch_rainfall_records, d) for d in districts}
    if all(records is not None for records in rainfall.values()):
        _write_snapshot(app.RAINFALL_SNAPSHOT, {"fetched_at": fetched_at, "districts": rainfall})
        print(f"Wrote {app.RAINFALL_SNAPSHOT.name}")
    else:
        print(f"{app.RAINFALL_SNAPSHOT.name} not updated")
        ok = False

    # Agmarknet only carries the current day's prices; Jharkhand mandis may
    # not have reported yet, so an empty result here is normal — retry later.
    mandi = _fetch("mandi (Agmarknet, Jharkhand)", app._fetch_agmarknet_records)
    if mandi is not None:
        _write_snapshot(app.MANDI_SNAPSHOT, {"fetched_at": fetched_at, "records": mandi})
        print(f"Wrote {app.MANDI_SNAPSHOT.name}")
    else:
        print(f"{app.MANDI_SNAPSHOT.name} not updated")
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:] or ["Ranchi"])
