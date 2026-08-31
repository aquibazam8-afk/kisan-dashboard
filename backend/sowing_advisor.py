"""
sowing_advisor.py — Rainfed Kharif sowing-window advisor.

Classifies rainfall over the Jun 20-30 sowing-decision window into a
sow / wait / switch recommendation, per the README's framing: "given
rainfall to date, is it still viable to sow paddy, or is it time to switch
to maize or ragi?"

Grounded in two real sources (no longer placeholders):

1. SOWING WINDOW — ATMA Ranchi's Strategic Research & Extension Plan (SREP),
   Chapter 9 (http://www.atmaranchi.in/srep/chapter9.pdf), which states
   "20th June to 30th June" as the recommended sowing time for upland rice,
   maize and pigeon pea in Ranchi district. The advisor assesses cumulative
   rainfall through this specific 11-day window, not from Jun 1.

2. RAINFALL CLASSIFICATION — the India Meteorological Department's (IMD)
   official departure-from-normal percentage classification, as used in
   IMD's monthly/seasonal rainfall bulletins, in place of the earlier
   placeholder mm thresholds.
"""
from datetime import date, datetime

# --- Sowing window (ATMA Ranchi SREP, Chapter 9) ------------------------------
# "20th June to 30th June" is the recommended sowing time for upland rice,
# maize and pigeon pea in Ranchi district per the SREP. The decision is made
# on cumulative rainfall across this fixed window, not a rolling Jun 1-today
# total.
SOWING_WINDOW_START_MD = (6, 20)
SOWING_WINDOW_END_MD = (6, 30)

WAIT_WINDOW_DAYS = 14  # how long to recommend waiting before reassessing

# --- IMD departure-from-normal rainfall classification -----------------------
# India Meteorological Department's standard bands for classifying rainfall
# as a percentage departure from the historical normal ("LPA" - long period
# average), as published in IMD's monthly/seasonal rainfall bulletins:
#   Large Excess   : >= +60%
#   Excess         : +20% to +59%
#   Normal         : -19% to +19%
#   Deficient      : -20% to -59%
#   Large Deficient: -60% to -99%
#   No Rain        : -100%
# "Normal" here is computed as the historical average of the Jun 20-30
# cumulative rainfall across all years available in the rainfall dataset
# (spans 2018-2025) — not a fixed mm figure.
IMD_DEPARTURE_CATEGORY_TO_STATUS = {
    "Large Excess": "sow",
    "Excess": "sow",
    "Normal": "sow",
    "Deficient": "wait",
    "Large Deficient": "switch",
    "No Rain": "switch",
}

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
    """Raised when records contain no usable Jun 20-30 window data at all."""


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


def _window_for_year(year):
    """The Jun 20-30 sowing-decision window (SREP Ch. 9) for a given year."""
    start = date(year, *SOWING_WINDOW_START_MD)
    end = date(year, *SOWING_WINDOW_END_MD)
    return start, end


def _select_season(parsed, today):
    """Pick which Kharif season's Jun 20-30 window to assess.

    Prefers the current year's window (capped at `today` if the window is
    still in progress). If that window has no records yet — e.g. it's
    before Jun 20, or the upstream data source hasn't caught up — falls
    back to the most recent past year that has any data in its Jun 20-30
    window, using the latest date recorded that year as its effective
    "as of" date. Raises NoRainfallDataError only if there is no Jun 20-30
    window data at all, in any year, to fall back to.
    """
    current_start, current_end = _window_for_year(today.year)
    if today >= current_start:
        as_of = min(today, current_end)
        current_season = [(d, rain) for d, rain in parsed if current_start <= d <= as_of]
        if current_season:
            return current_season, today.year, current_start, current_end, as_of, False

    candidate_years = sorted(
        {d.year for d, _ in parsed if _window_for_year(d.year)[0] <= d <= _window_for_year(d.year)[1]},
        reverse=True,
    )
    if not candidate_years:
        raise NoRainfallDataError("No Jun 20-30 sowing-window rainfall records available.")

    season_year = candidate_years[0]
    season_start, season_end = _window_for_year(season_year)
    season_records = [(d, rain) for d, rain in parsed if season_start <= d <= season_end]
    as_of = max(d for d, _ in season_records)
    return season_records, season_year, season_start, season_end, as_of, True


def _year_window_totals(parsed):
    """{year: cumulative Jun 20-30 rain_mm} for every year present in `parsed`.

    Used to compute the historical "normal" for the IMD departure calculation
    — the average of this window's cumulative rainfall across all years
    available in the dataset (2018-2025), not a fixed mm figure.
    """
    totals = {}
    for d, rain in parsed:
        start, end = _window_for_year(d.year)
        if start <= d <= end:
            totals[d.year] = totals.get(d.year, 0.0) + rain
    return {year: round(total, 1) for year, total in totals.items()}


def _departure_pct(actual_mm, normal_mm):
    """% departure of actual from normal: ((actual - normal) / normal) * 100."""
    if normal_mm <= 0:
        return 0.0 if actual_mm <= 0 else 999.0  # no meaningful baseline; treat as extreme excess
    return round(((actual_mm - normal_mm) / normal_mm) * 100, 1)


def _classify_departure(departure_pct):
    """IMD's standard departure-from-normal bands (see module docstring)."""
    if departure_pct >= 60:
        return "Large Excess"
    if departure_pct >= 20:
        return "Excess"
    if departure_pct >= -19:
        return "Normal"
    if departure_pct >= -59:
        return "Deficient"
    if departure_pct >= -99:
        return "Large Deficient"
    return "No Rain"


def assess_kharif_sowing(records, today=None):
    """Sow/wait/switch recommendation from rainfall records.

    `records` is a list of {"date": "YYYY-MM-DD", "rain_mm": float} dicts —
    the shape the /rainfall endpoint's "days" list already uses, and is
    expected to span multiple years (the live feed returns up to 1000
    records per district) so a historical normal can be computed.

    Assesses cumulative rainfall over the Jun 20-30 sowing-decision window
    (ATMA Ranchi SREP, Ch. 9) for the current season when there's data for
    it; otherwise falls back to the most recent complete window on record
    and labels the response accordingly (`season`, `note`). The result is
    classified against IMD's departure-from-normal percentage bands, with
    "normal" computed as the historical average of this window's cumulative
    rainfall across every year present in `records`.

    Raises NoRainfallDataError only when there's no Jun 20-30 window data at
    all to fall back to — callers should treat that as a hard failure, not
    silently classify off zero records.
    """
    today = today or date.today()
    parsed = _parse_records(records)

    (season_records, season_year, window_start, window_end, as_of,
     is_fallback) = _select_season(parsed, today)

    actual_mm = round(sum(rain for _, rain in season_records), 1)

    year_totals = _year_window_totals(parsed)
    if not year_totals:
        raise NoRainfallDataError("No Jun 20-30 sowing-window rainfall records available.")
    normal_mm = round(sum(year_totals.values()) / len(year_totals), 1)

    departure_pct = _departure_pct(actual_mm, normal_mm)
    category = _classify_departure(departure_pct)
    status = IMD_DEPARTURE_CATEGORY_TO_STATUS[category]

    departure_str = f"{departure_pct:+.0f}%"
    base_en = (
        f"{actual_mm}mm received in the Jun 20-30 sowing window vs a historical "
        f"normal of {normal_mm}mm (average across {len(year_totals)} years on record) "
        f"— a {departure_str} departure, classified '{category}' per IMD's rainfall "
        f"standard."
    )
    base_hi = (
        f"20-30 जून की बुआई अवधि में {actual_mm}मिमी बारिश हुई, जबकि ऐतिहासिक सामान्य "
        f"{normal_mm}मिमी है ({len(year_totals)} वर्षों का औसत) — {departure_str} विचलन, "
        f"IMD मानक अनुसार '{category}' श्रेणी।"
    )

    if status == "switch":
        alt = ALTERNATIVE_CROPS[DEFAULT_ALTERNATIVE]
        reasoning = {
            "en": base_en + f" Rainfall is severely deficient — switch to {alt['en']}, "
                             f"a lower-water alternative.",
            "hi": base_hi + f" बारिश में भारी कमी है — कम पानी वाली फसल {alt['hi']} की ओर बदलें।",
        }
        alternative_crop = alt
        wait_window_days = None
    elif status == "wait":
        reasoning = {
            "en": base_en + f" Rainfall is deficient but not severe — wait up to "
                             f"{WAIT_WINDOW_DAYS} more days before deciding whether to "
                             f"sow paddy or switch crops.",
            "hi": base_hi + f" सामान्य से कम है पर गंभीर नहीं — धान बोने या फसल बदलने का "
                             f"फैसला करने से पहले {WAIT_WINDOW_DAYS} दिन और प्रतीक्षा करें।",
        }
        alternative_crop = None
        wait_window_days = WAIT_WINDOW_DAYS
    else:
        reasoning = {
            "en": base_en + " Rainfall is at or above normal — go ahead and sow paddy as planned.",
            "hi": base_hi + " बारिश सामान्य या उससे अधिक है — योजना अनुसार धान बोई जा सकती है।",
        }
        alternative_crop = None
        wait_window_days = None

    if is_fallback:
        note = {
            "en": (
                f"Current season's Jun 20-30 window data not yet available — showing "
                f"the most recent complete window on record (Kharif {season_year})."
            ),
            "hi": (
                f"मौजूदा सीज़न की 20-30 जून अवधि का डेटा अभी उपलब्ध नहीं है — रिकॉर्ड में "
                f"मौजूद सबसे हालिया पूर्ण अवधि (खरीफ {season_year}) दिखाई जा रही है।"
            ),
        }
    else:
        note = None

    return {
        "status": status,
        "season": str(season_year),
        "current_season": not is_fallback,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "as_of": as_of.isoformat(),
        "cumulative_rain_mm": actual_mm,
        "normal_rain_mm": normal_mm,
        "departure_pct": departure_pct,
        "category": category,
        "normal_years_count": len(year_totals),
        "alternative_crop": alternative_crop,
        "wait_window_days": wait_window_days,
        "note": note,
        "reasoning": reasoning,
    }
