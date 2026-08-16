"""
sowing_advisor.py — Rainfed Kharif sowing-window advisor.

Classifies cumulative Jun 1-today rainfall into a sow / wait / switch
recommendation, per the README's framing: "given rainfall to date, is it
still viable to sow paddy, or is it time to switch to maize or ragi?"
"""
from datetime import date, datetime

# --- Placeholder thresholds --------------------------------------------------
# Cumulative rainfall (mm) from Jun 1 to today. These are rough stand-ins
# picked for plausibility, NOT sourced from ATMA Ranchi's Strategic Research
# & Extension Plan yet — swap in real block-level normals once available
# (see README "Data sources" table, Phase 3).
SWITCH_THRESHOLD_MM = 150   # below this: severe deficit -> switch crop now
SOW_THRESHOLD_MM = 300      # at/above this: adequate -> sow paddy as planned
# between the two thresholds: deficient but not severe -> wait and reassess

WAIT_WINDOW_DAYS = 14  # how long to recommend waiting before deciding

# Lower-water alternatives to rainfed upland paddy, per the ATMA Ranchi SREP
# (README, "Rainfed upland reality"). Only `maize` is actively recommended
# below for now — the rest are kept here for when the advisor can rank
# alternatives instead of always defaulting to the first one.
ALTERNATIVE_CROPS = {
    "maize": {"en": "Maize", "hi": "मक्का"},
    "ragi": {"en": "Ragi (finger millet)", "hi": "रागी (मंडुआ)"},
    "black_gram": {"en": "Black gram", "hi": "उड़द"},
    "pigeon_pea": {"en": "Pigeon pea", "hi": "अरहर"},
    "cowpea": {"en": "Cowpea", "hi": "लोबिया"},
    "groundnut": {"en": "Groundnut", "hi": "मूंगफली"},
    "niger": {"en": "Niger", "hi": "रामतिल"},
    "sweet_potato": {"en": "Sweet potato", "hi": "शकरकंद"},
}
DEFAULT_ALTERNATIVE = "maize"


class NoRainfallDataError(Exception):
    """Raised when records contain no usable Kharif-season data at all."""


def _parse_records(records):
    """[{"date": "YYYY-MM-DD", "rain_mm": float}, ...] -> [(date, float), ...]."""
    parsed = []
    for r in records:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            rain = float(r.get("rain_mm") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        parsed.append((d, rain))
    return parsed


def _select_season(parsed, today):
    """Pick which Kharif season to assess.

    Prefers the current year (Jun 1 of `today`'s year through `today`). If
    that window has no records yet — e.g. the upstream data source hasn't
    caught up to the current date — falls back to the most recent past year
    that has any Jun 1-onward data, using the latest date recorded that year
    as its effective "as of" date. Raises NoRainfallDataError only if there
    is no Kharif-season data at all to fall back to.
    """
    current_season_start = date(today.year, 6, 1)
    current_season = [(d, rain) for d, rain in parsed if current_season_start <= d <= today]
    if current_season:
        return current_season, today.year, current_season_start, today, False

    candidate_years = sorted(
        {d.year for d, _ in parsed if d >= date(d.year, 6, 1)},
        reverse=True,
    )
    if not candidate_years:
        raise NoRainfallDataError("No Kharif-season rainfall records available.")

    season_year = candidate_years[0]
    season_start = date(season_year, 6, 1)
    season_records = [(d, rain) for d, rain in parsed if season_start <= d]
    as_of = max(d for d, _ in season_records)
    return season_records, season_year, season_start, as_of, True


def assess_kharif_sowing(records, today=None):
    """Sow/wait/switch recommendation from rainfall records.

    `records` is a list of {"date": "YYYY-MM-DD", "rain_mm": float} dicts —
    the shape the /rainfall endpoint's "days" list already uses. Assesses
    the current Kharif season (Jun 1 of `today`'s year through `today`) when
    there's data for it; otherwise falls back to the most recent complete
    season on record and labels the response accordingly (`season`, `note`).
    Raises NoRainfallDataError only when there's no Kharif-season data at
    all to fall back to — callers should treat that as a hard failure, not
    silently classify off zero records.
    """
    today = today or date.today()
    parsed = _parse_records(records)

    season_records, season_year, season_start, as_of, is_fallback = _select_season(parsed, today)

    days_elapsed = (as_of - season_start).days + 1
    cumulative_mm = round(sum(rain for _, rain in season_records), 1)
    avg_daily_mm = round(cumulative_mm / days_elapsed, 2) if days_elapsed else 0.0

    if cumulative_mm < SWITCH_THRESHOLD_MM:
        status = "switch"
        alt = ALTERNATIVE_CROPS[DEFAULT_ALTERNATIVE]
        reasoning = {
            "en": (
                f"{cumulative_mm}mm received vs {SWITCH_THRESHOLD_MM}mm expected minimum "
                f"by now ({days_elapsed} days into the Kharif season, avg "
                f"{avg_daily_mm}mm/day). Rainfall is significantly deficient — switch to "
                f"{alt['en']}, a lower-water alternative."
            ),
            "hi": (
                f"अब तक {cumulative_mm}मिमी बारिश हुई, जबकि न्यूनतम {SWITCH_THRESHOLD_MM}मिमी अपेक्षित थी "
                f"(खरीफ सीज़न के {days_elapsed} दिन बीत चुके हैं, औसत {avg_daily_mm}मिमी/दिन)। "
                f"बारिश में भारी कमी है — कम पानी वाली फसल {alt['hi']} की ओर बदलें।"
            ),
        }
        alternative_crop = alt
        wait_window_days = None
    elif cumulative_mm < SOW_THRESHOLD_MM:
        status = "wait"
        reasoning = {
            "en": (
                f"{cumulative_mm}mm received vs {SOW_THRESHOLD_MM}mm expected by now "
                f"({days_elapsed} days into the Kharif season, avg {avg_daily_mm}mm/day). "
                f"Below normal but not severe — wait up to {WAIT_WINDOW_DAYS} more days "
                f"before deciding whether to sow paddy or switch crops."
            ),
            "hi": (
                f"अब तक {cumulative_mm}मिमी बारिश हुई, जबकि {SOW_THRESHOLD_MM}मिमी अपेक्षित थी "
                f"(खरीफ सीज़न के {days_elapsed} दिन बीत चुके हैं, औसत {avg_daily_mm}मिमी/दिन)। "
                f"सामान्य से कम है पर गंभीर नहीं — धान बोने या फसल बदलने का फैसला करने से पहले "
                f"{WAIT_WINDOW_DAYS} दिन और प्रतीक्षा करें।"
            ),
        }
        alternative_crop = None
        wait_window_days = WAIT_WINDOW_DAYS
    else:
        status = "sow"
        reasoning = {
            "en": (
                f"{cumulative_mm}mm received vs {SOW_THRESHOLD_MM}mm expected by now "
                f"({days_elapsed} days into the Kharif season, avg {avg_daily_mm}mm/day). "
                f"Rainfall is reasonably adequate — go ahead and sow paddy as planned."
            ),
            "hi": (
                f"अब तक {cumulative_mm}मिमी बारिश हुई, जबकि {SOW_THRESHOLD_MM}मिमी अपेक्षित थी "
                f"(खरीफ सीज़न के {days_elapsed} दिन बीत चुके हैं, औसत {avg_daily_mm}मिमी/दिन)। "
                f"बारिश पर्याप्त है — योजना अनुसार धान बोई जा सकती है।"
            ),
        }
        alternative_crop = None
        wait_window_days = None

    if is_fallback:
        note = {
            "en": (
                f"Current season data not yet available — showing the most recent "
                f"complete season on record (Kharif {season_year})."
            ),
            "hi": (
                f"मौजूदा सीज़न का डेटा अभी उपलब्ध नहीं है — रिकॉर्ड में मौजूद सबसे हालिया "
                f"पूर्ण सीज़न (खरीफ {season_year}) दिखाया जा रहा है।"
            ),
        }
    else:
        note = None

    return {
        "status": status,
        "season": str(season_year),
        "current_season": not is_fallback,
        "season_start": season_start.isoformat(),
        "as_of": as_of.isoformat(),
        "days_elapsed": days_elapsed,
        "cumulative_rain_mm": cumulative_mm,
        "avg_daily_rain_mm": avg_daily_mm,
        "switch_threshold_mm": SWITCH_THRESHOLD_MM,
        "sow_threshold_mm": SOW_THRESHOLD_MM,
        "alternative_crop": alternative_crop,
        "wait_window_days": wait_window_days,
        "note": note,
        "reasoning": reasoning,
    }
