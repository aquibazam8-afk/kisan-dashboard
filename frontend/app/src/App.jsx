import React, { useState, useEffect, useRef } from "react";

// ── Backend URL. When running locally: http://localhost:8000 ────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Fallback data so the UI still renders if the backend isn't running yet.
// Weather has none: a forecast is never invented, the tab says it's unavailable.
const WEATHER_UNAVAILABLE = { source: "unavailable", days: [] };
const FALLBACK_MANDI = {
  paddy:       [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 2180, trend: "up" },
                { mandi: { en: "Ramgarh",         hi: "रामगढ़" },         price: 2150, trend: "flat" },
                { mandi: { en: "Khunti",           hi: "खूंटी" },          price: 2120, trend: "down" }],
  maize:       [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 2050, trend: "up" },
                { mandi: { en: "Lohardaga",        hi: "लोहरदगा" },        price: 1990, trend: "up" }],
  arhar:       [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 7200, trend: "up" }],
  veg:         [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 1400, trend: "down" }],
  tomato:      [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 1550, trend: "up" },
                { mandi: { en: "Namkum",           hi: "नामकुम" },          price: 1480, trend: "up" },
                { mandi: { en: "Khunti",           hi: "खूंटी" },          price: 1400, trend: "flat" }],
  potato:      [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 1150, trend: "flat" },
                { mandi: { en: "Ramgarh",         hi: "रामगढ़" },         price: 1080, trend: "down" }],
  onion:       [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 1900, trend: "up" },
                { mandi: { en: "Lohardaga",        hi: "लोहरदगा" },        price: 1820, trend: "up" }],
  cauliflower: [{ mandi: { en: "Ranchi (Pandra)", hi: "रांची (पंडरा)" }, price: 1050, trend: "down" },
                { mandi: { en: "Namkum",           hi: "नामकुम" },          price:  980, trend: "flat" }],
};

const CROPS = [
  { id: "paddy",       en: "Paddy",       hi: "धान",       icon: "🌾" },
  { id: "maize",       en: "Maize",       hi: "मक्का",     icon: "🌽" },
  { id: "arhar",       en: "Arhar",       hi: "अरहर",      icon: "🫘" },
  { id: "veg",         en: "Vegetables",  hi: "सब्ज़ी",    icon: "🥬" },
  { id: "tomato",      en: "Tomato",      hi: "टमाटर",     icon: "🍅" },
  { id: "potato",      en: "Potato",      hi: "आलू",       icon: "🥔" },
  { id: "onion",       en: "Onion",       hi: "प्याज़",    icon: "🧅" },
  { id: "cauliflower", en: "Cauliflower", hi: "फूलगोभी",   icon: "🥦" },
];

const SOWING = {
  paddy:       { window: { en: "Jun 15 – Jul 15", hi: "15 जून – 15 जुलाई" }, soil: { en: "Clay-loam, standing water", hi: "चिकनी दोमट, पानी रुके" }, tip: { en: "Transplant after 20–25 day nursery; good rain this week.", hi: "20–25 दिन नर्सरी के बाद रोपाई; इस हफ़्ते अच्छी बारिश।" } },
  maize:       { window: { en: "Jun 20 – Jul 10", hi: "20 जून – 10 जुलाई" }, soil: { en: "Well-drained loam", hi: "अच्छी निकासी वाली दोमट" }, tip: { en: "Sow before Mon rain; ridge planting drains better.", hi: "सोम की बारिश से पहले बोएं; मेड़ पर बुआई बेहतर।" } },
  arhar:       { window: { en: "Jun 15 – Jul 05", hi: "15 जून – 5 जुलाई" }, soil: { en: "Sandy-loam, deep", hi: "बलुई दोमट, गहरी" }, tip: { en: "Intercrop with maize; late sowing cuts yield.", hi: "मक्का के साथ मिश्रित; देर बुआई पैदावार घटाती है।" } },
  veg:         { window: { en: "Year-round", hi: "साल भर" }, soil: { en: "Rich loam, raised beds", hi: "उपजाऊ दोमट, ऊँची क्यारी" }, tip: { en: "Raised beds now to survive Mon–Tue rain.", hi: "सोम–मंगल बारिश हेतु अभी ऊँची क्यारी।" } },
  tomato:      { window: { en: "Jun 01 – Jul 15", hi: "1 जून – 15 जुलाई" }, soil: { en: "Well-drained loam, raised beds", hi: "अच्छी निकासी वाली दोमट, ऊँची क्यारी" }, tip: { en: "Raise 25-day nursery; transplant after first good rain; stake early.", hi: "25 दिन नर्सरी तैयार करें; पहली अच्छी बारिश बाद रोपाई; बाँस से सहारा दें।" } },
  potato:      { window: { en: "Jul 15 – Aug 15", hi: "15 जुलाई – 15 अगस्त" }, soil: { en: "Loose sandy-loam, deep ploughed", hi: "भुरभुरी बलुई दोमट, गहरी जुताई" }, tip: { en: "Use short-duration varieties; ridge planting prevents waterlogging.", hi: "कम अवधि की किस्म चुनें; मेड़ पर बोएं ताकि जलभराव न हो।" } },
  onion:       { window: { en: "Jun 15 – Jul 31", hi: "15 जून – 31 जुलाई" }, soil: { en: "Well-drained loam, slightly acidic", hi: "अच्छी निकासी वाली दोमट, हल्की अम्लीय" }, tip: { en: "Transplant 6-week nursery seedlings; avoid waterlogging at bulb stage.", hi: "6 हफ़्ते की पौध रोपें; गठन के समय जलभराव से बचाएं।" } },
  cauliflower: { window: { en: "May 15 – Jun 30", hi: "15 मई – 30 जून" }, soil: { en: "Fertile loam, pH 6–7", hi: "उपजाऊ दोमट, pH 6–7" }, tip: { en: "Use early Kharif variety (Pusa Kartik); shade curd with leaves to keep white.", hi: "अगेती किस्म (पूसा कार्तिक) लगाएं; फूल को पत्तियों से ढकें ताकि सफेद रहे।" } },
};
const PESTS = {
  paddy:       [{ level: "high",   name: { en: "Stem borer",          hi: "तना छेदक" },           note: { en: "Rising in Kanke after rain.",               hi: "बारिश बाद कांके में बढ़ रहा।" } }],
  maize:       [{ level: "medium", name: { en: "Fall armyworm",       hi: "फॉल आर्मीवर्म" },      note: { en: "Scout leaf whorls weekly.",                 hi: "पत्तियों की साप्ताहिक जाँच।" } }],
  arhar:       [{ level: "low",    name: { en: "Pod borer",           hi: "फली छेदक" },            note: { en: "Monitor at flowering.",                     hi: "फूल आने पर देखें।" } }],
  veg:         [{ level: "medium", name: { en: "Leaf blight",         hi: "पत्ती झुलसा" },         note: { en: "Avoid overhead watering.",                  hi: "ऊपर से सिंचाई न करें।" } }],
  tomato:      [{ level: "high",   name: { en: "Fruit borer",         hi: "फल छेदक" },             note: { en: "Spray neem oil at first flower; common in Ranchi Kharif.", hi: "पहले फूल पर नीम तेल छिड़कें; रांची खरीफ में सामान्य।" } }],
  potato:      [{ level: "high",   name: { en: "Late blight",         hi: "पछेती झुलसा" },         note: { en: "Monsoon humidity spikes risk; spray Mancozeb preventively.", hi: "मानसून नमी से खतरा; मेन्कोज़ेब का निवारक छिड़काव करें।" } }],
  onion:       [{ level: "medium", name: { en: "Thrips",              hi: "थ्रिप्स" },              note: { en: "Check leaf tips; use sticky yellow traps.",  hi: "पत्ती की नोक जाँचें; पीले चिपचिपे ट्रैप लगाएं।" } }],
  cauliflower: [{ level: "medium", name: { en: "Diamond-back moth",   hi: "हीरक पृष्ठ शलभ" },     note: { en: "Check leaf undersides; rotate with non-brassica.", hi: "पत्ती की निचली सतह देखें; गैर-सरसों फसल के साथ बदलें।" } }],
};

const T = {
  title: { en: "Khet Saathi", hi: "खेत साथी" },
  sub: { en: "Ranchi District", hi: "रांची ज़िला" },
  statusOnline: { en: "Connected to server", hi: "सर्वर से जुड़ा है" },
  statusOffline: { en: "Not connected to server", hi: "सर्वर से नहीं जुड़ा" },
  sections: { en: "Sections", hi: "विभाग" },
  themeName: { en: "Theme", hi: "रंग-रूप" },
  themeChange: { en: "tap to change", hi: "बदलने के लिए दबाएं" },
  weather: { en: "Weather", hi: "मौसम" },
  sowing: { en: "Sowing", hi: "बुआई सलाह" },
  advisory: { en: "Sowing Advisor", hi: "बुआई सलाहकार" },
  mandi: { en: "Mandi rates", hi: "मंडी भाव" },
  pest: { en: "Pest alert", hi: "कीट चेतावनी" },
  disease: { en: "Disease check", hi: "रोग जाँच" },
  yourCrop: { en: "Your crop", hi: "आपकी फसल" },
  window: { en: "Sow window", hi: "बुआई समय" },
  soil: { en: "Soil", hi: "मिट्टी" },
  best: { en: "Best rate", hi: "सबसे अच्छा भाव" },
  uploadHint: { en: "Take/upload a leaf photo to check for disease", hi: "रोग जाँचने हेतु पत्ती की फ़ोटो लें/भेजें" },
  analyzing: { en: "Analyzing…", hi: "जाँच हो रही है…" },
  confidence: { en: "confidence", hi: "भरोसा" },
  whatToDo: { en: "What to do", hi: "क्या करें" },
  offline: { en: "Backend offline — showing sample data. Disease check needs the server running.", hi: "सर्वर बंद — नमूना डेटा दिख रहा। रोग जाँच हेतु सर्वर चालू करें।" },
  advisoryLoading: { en: "Checking this season's rainfall…", hi: "इस सीज़न की बारिश जाँची जा रही है…" },
  advisoryError: { en: "Could not load the sowing advisory. Make sure the server is running.", hi: "बुआई सलाह लोड नहीं हो सकी। सर्वर चालू है या नहीं जाँचें।" },
  paddyAdvice: { en: "Paddy sowing advice", hi: "धान बुआई सलाह" },
  pastResult: (season, v) => ({ en: `Kharif ${season} result: ${v.en}`, hi: `खरीफ ${season} परिणाम: ${v.hi}` }),
  referenceOnly: { en: "Not the current season — for reference only", hi: "यह मौजूदा सीज़न नहीं है — केवल संदर्भ के लिए" },
  retry: { en: "Retry", hi: "फिर कोशिश करें" },
  mandiSample: { en: "Sample prices — live market data unavailable", hi: "नमूना भाव — लाइव मंडी डेटा उपलब्ध नहीं" },
  mandiSnapshot: (d) => ({ en: `Prices as of ${d}`, hi: `${d} के भाव` }),
  rainSnapshot: (d) => ({ en: `Rainfall data saved on ${d}`, hi: `वर्षा डेटा ${d} को सहेजा गया` }),
  weatherUnavailable: { en: "Weather forecast unavailable right now", hi: "मौसम पूर्वानुमान अभी उपलब्ध नहीं है" },
  weatherLoading: { en: "Loading the 7-day forecast…", hi: "7 दिन का पूर्वानुमान लोड हो रहा है…" },
  weatherRetryHint: { en: "If the server was asleep, it can take about a minute to wake up. Try again.", hi: "सर्वर सोया हो तो जागने में लगभग एक मिनट लग सकता है। फिर कोशिश करें।" },
  dayCol: { en: "Day", hi: "दिन" },
  rainCol: { en: "Rain", hi: "बारिश" },
  tempCol: { en: "High / low", hi: "अधिकतम / न्यूनतम" },
  noRain: { en: "Dry", hi: "सूखा" },
  mandiEmpty: { en: "No mandi prices for this crop yet.", hi: "इस फसल के मंडी भाव अभी उपलब्ध नहीं हैं।" },
  perQuintal: { en: " per quintal", hi: " प्रति क्विंटल" },
  weatherCreditOpenMeteo: { en: "Forecast: Open-Meteo", hi: "पूर्वानुमान: Open-Meteo" },
  weatherCreditMetNo: { en: "Forecast based on data from MET Norway", hi: "पूर्वानुमान MET Norway के डेटा पर आधारित" },
  modelCaveat: { en: "Trained on clear leaf photos; field results may vary.", hi: "साफ़ पत्ती की फ़ोटो पर प्रशिक्षित; खेत में नतीजे अलग हो सकते हैं।" },
  predictFailed: { en: "Could not check this photo. Please try again.", hi: "इस फ़ोटो की जाँच नहीं हो सकी। कृपया फिर से कोशिश करें।" },
};

// "2026-10-21" -> "21/10/2026"
function fmtDay(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

const TREND_MARK = { up: "▲", down: "▼", flat: "—" };
const TREND_LABEL = {
  up:   { en: "Rising", hi: "बढ़ रहा" },
  down: { en: "Falling", hi: "घट रहा" },
  flat: { en: "Steady", hi: "स्थिर" },
};
const LEVEL_LABEL = {
  high:   { en: "High", hi: "अधिक" },
  medium: { en: "Medium", hi: "मध्यम" },
  low:    { en: "Low", hi: "कम" },
};
const MODULES = ["weather", "sowing", "advisory", "mandi", "pest", "disease"];
const MODULE_ICON = { weather: "🌦️", sowing: "🌱", advisory: "🧭", mandi: "💰", pest: "🐛", disease: "🔬" };

const ADVISORY_STATUS_LABEL = {
  sow:    { en: "Sow now", hi: "अभी बोएं" },
  wait:   { en: "Wait", hi: "प्रतीक्षा करें" },
  switch: { en: "Switch crop", hi: "फसल बदलें" },
};
const ADVISORY_STATUS_ICON = { sow: "✅", wait: "⏳", switch: "🔁" };
// Verdict for a past season's window (current_season: false): stated as that
// window's result, not as something to do now, in a neutral colour.
const ADVISORY_PAST_VERDICT = {
  sow:    { en: "Sow", hi: "बोएं" },
  wait:   { en: "Wait", hi: "प्रतीक्षा" },
  switch: { en: "Switch crop", hi: "फसल बदलें" },
};

// Theme: "auto" follows the phone's setting. Stored in localStorage; the
// inline script in index.html applies it before first paint.
const THEMES = ["auto", "light", "dark"];
const THEME_LABEL = {
  auto:  { en: "Auto", hi: "स्वतः" },
  light: { en: "Light", hi: "हल्का" },
  dark:  { en: "Dark", hi: "गहरा" },
};
const THEME_ICON = { auto: "◐", light: "☀", dark: "☾" };
const THEME_KEY = "ks-theme";

function readTheme() {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return THEMES.includes(v) ? v : "auto";
  } catch {
    return "auto";
  }
}

function Skeleton({ lines = 3, head = false }) {
  return (
    <div aria-hidden="true">
      {head && <span className="ks-skel ks-skel-head" />}
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="ks-skel" style={{ width: `${92 - (i % 3) * 14}%` }} />
      ))}
    </div>
  );
}

function Note({ children, icon = "⚠️" }) {
  return (
    <div className="ks-note">
      <span aria-hidden="true">{icon}</span>
      <span>{children}</span>
    </div>
  );
}

function EmptyState({ icon, text, action }) {
  return (
    <div className="ks-empty">
      <div className="ks-empty-icon" aria-hidden="true">{icon}</div>
      <p className="ks-empty-text">{text}</p>
      {action}
    </div>
  );
}

export default function KisanDashboard() {
  const [lang, setLang] = useState("hi");
  const [theme, setTheme] = useState(readTheme);
  const [crop, setCrop] = useState("paddy");
  const [tab, setTab] = useState("weather");
  const [weather, setWeather] = useState(null); // null while loading
  const [mandi, setMandi] = useState(null); // null while loading
  const [mandiFallback, setMandiFallback] = useState(false);
  const [online, setOnline] = useState(false);
  const [pred, setPred] = useState(null);
  const [busy, setBusy] = useState(false);
  const [advisory, setAdvisory] = useState(null);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);
  const [advisoryError, setAdvisoryError] = useState(false);
  const [dataStatus, setDataStatus] = useState(null);
  const fileRef = useRef();
  const t = (o) => (o ? o[lang] : "");

  function loadWeather() {
    setWeather(null);
    fetch(`${API_BASE}/weather`)
      .then(r => { if (!r.ok) throw new Error("weather fetch failed"); return r.json(); })
      .then(d => { setWeather(d); setOnline(true); })
      .catch(() => setWeather(WEATHER_UNAVAILABLE));
  }

  useEffect(() => {
    loadWeather();
    // If /mandi fails the bundled sample prices are shown, labelled as sample.
    fetch(`${API_BASE}/mandi`)
      .then(r => { if (!r.ok) throw new Error("mandi fetch failed"); return r.json(); })
      .then(setMandi)
      .catch(() => { setMandi(FALLBACK_MANDI); setMandiFallback(true); });
    // Where mandi/rainfall data came from (live/snapshot/sample). On failure
    // dataStatus stays null and no source notes are shown.
    fetch(`${API_BASE}/data-status`)
      .then(r => { if (!r.ok) throw new Error("data-status fetch failed"); return r.json(); })
      .then(setDataStatus)
      .catch(() => {});
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Storage blocked (private mode etc.): the choice lasts for this visit only.
    }
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = lang === "hi" ? "खेत साथी — Khet Saathi" : "Khet Saathi — खेत साथी";
  }, [lang]);

  useEffect(() => {
    if (tab !== "advisory" || advisory || advisoryLoading) return;
    setAdvisoryLoading(true);
    setAdvisoryError(false);
    fetch(`${API_BASE}/sowing-advisory?district=Ranchi`)
      .then(r => { if (!r.ok) throw new Error("advisory fetch failed"); return r.json(); })
      .then(setAdvisory)
      .catch(() => setAdvisoryError(true))
      .finally(() => setAdvisoryLoading(false));
  }, [tab, advisory, advisoryLoading]);

  const prices = mandi?.[crop] || [];
  const best = prices.reduce((a, b) => (b.price > (a?.price ?? 0) ? b : a), prices[0]);

  const mandiSource = dataStatus?.mandi?.source;
  const mandiNote =
    mandiFallback || mandiSource === "sample" ? T.mandiSample :
    mandiSource === "snapshot" ? T.mandiSnapshot(fmtDay(dataStatus.mandi.as_of)) :
    null;
  // /weather marks its own source. Day cards are shown only for a live
  // forecast; anything else (incl. an older backend's "sample") is unavailable.
  const weatherLive = weather?.source === "live";
  // Rain bars share one scale per week; at least 10 mm so a drizzle stays small.
  const rainScale = weatherLive ? Math.max(10, ...weather.days.map(w => w.rain_mm)) : 10;
  const rainNote =
    dataStatus?.rainfall?.source === "snapshot" ? T.rainSnapshot(fmtDay(dataStatus.rainfall.as_of)) : null;

  // Disease result: "ok" (or no status but the usual fields — older backend),
  // a wrong_crop/unsupported notice, or otherwise a failure notice — never blank.
  const predOk = pred && !pred.error &&
    (pred.status === "ok" || (!pred.status && pred.disease && pred.confidence != null));
  const predNotice = pred && !pred.error && !predOk && pred.status && pred.message;
  const predFailed = pred && !predOk && !predNotice;

  async function onFile(e) {
    const f = e.target.files[0];
    if (!f) return;
    setBusy(true); setPred(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("crop", crop);
      const r = await fetch(`${API_BASE}/predict`, { method: "POST", body: fd });
      if (!r.ok) throw new Error("predict failed");
      setPred(await r.json());
    } catch {
      setPred({ error: true });
    }
    setBusy(false);
    e.target.value = ""; // allow re-checking the same photo
  }

  const retryButton = (onClick) => (
    <button type="button" className="ks-btn" onClick={onClick}>{t(T.retry)}</button>
  );

  return (
    <div className="ks-app">
      <header className="ks-header">
        <div>
          <h1 className="ks-title">{t(T.title)}</h1>
          <p className="ks-district">
            {t(T.sub)}
            <span className="ks-dot" data-online={online} role="img"
              aria-label={t(online ? T.statusOnline : T.statusOffline)} />
          </p>
        </div>
        <div className="ks-header-actions">
          <button type="button" className="ks-theme"
            onClick={() => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length])}
            aria-label={`${t(T.themeName)}: ${t(THEME_LABEL[theme])}, ${t(T.themeChange)}`}>
            <span aria-hidden="true">{THEME_ICON[theme]}</span>
            <span>{t(THEME_LABEL[theme])}</span>
          </button>
          <button type="button" className="ks-lang" onClick={() => setLang(lang === "hi" ? "en" : "hi")}
            lang={lang === "hi" ? "en" : "hi"}>
            {lang === "hi" ? "English" : "हिंदी"}
          </button>
        </div>
      </header>

      {!online && weather && <div className="ks-banner"><Note>{t(T.offline)}</Note></div>}

      {/* Crop selector — big tap targets */}
      <h2 className="ks-label" id="crop-label">{t(T.yourCrop)}</h2>
      <div className="ks-crops" role="group" aria-labelledby="crop-label">
        {CROPS.map((c) => (
          <button type="button" key={c.id} className="ks-crop" aria-pressed={crop === c.id}
            onClick={() => setCrop(c.id)}>
            <span className="ks-crop-icon" aria-hidden="true">{c.icon}</span>
            <span>{t(c)}</span>
          </button>
        ))}
      </div>

      {/* Module tabs — icon-first for low literacy */}
      <div className="ks-tabs" role="group" aria-label={t(T.sections)}>
        {MODULES.map((m) => (
          <button type="button" key={m} className="ks-tab" aria-pressed={tab === m} onClick={() => setTab(m)}>
            <span className="ks-tab-icon" aria-hidden="true">{MODULE_ICON[m]}</span>
            <span>{t(T[m])}</span>
          </button>
        ))}
      </div>

      <section className="ks-panel" aria-live="polite">
        {tab === "weather" && (
          <div>
            {!weather && (
              <>
                <Skeleton lines={7} />
                <p className="ks-loading-text">{t(T.weatherLoading)}</p>
              </>
            )}
            {weather && !weatherLive && (
              <>
                <Note>{t(T.weatherUnavailable)}</Note>
                <EmptyState icon="🌦️" text={t(T.weatherRetryHint)} action={retryButton(loadWeather)} />
              </>
            )}
            {weatherLive && (
              <>
                <div className="ks-week-head" aria-hidden="true">
                  <span>{t(T.dayCol)}</span>
                  <span>{t(T.rainCol)}</span>
                  <span className="ks-temps">{t(T.tempCol)}</span>
                </div>
                <ul className="ks-week">
                  {weather.days.map((w, i) => (
                    <li key={i} className="ks-day">
                      <span className="ks-day-name">{t(w.day)}</span>
                      <span className="ks-rain">
                        <span className="ks-rain-track" aria-hidden="true">
                          <span className="ks-rain-fill" style={{ display: "block", width: `${Math.min(100, (w.rain_mm / rainScale) * 100)}%` }} />
                        </span>
                        <span className="ks-rain-mm" data-dry={!(w.rain_mm > 0)}>
                          {w.rain_mm > 0 ? `${w.rain_mm} mm` : t(T.noRain)}
                        </span>
                      </span>
                      <span className="ks-temps">
                        <span className="ks-tmax">{w.tmax}°</span>
                        <span className="ks-tmin"> / {w.tmin}°</span>
                      </span>
                    </li>
                  ))}
                </ul>
                {weather.provider === "met-no" ? (
                  // MET Norway data is CC BY 4.0: credit plus a link to the licence.
                  <p className="ks-credit">
                    <a href="https://www.met.no/en" target="_blank" rel="noopener noreferrer">{t(T.weatherCreditMetNo)}</a>
                    {" ("}
                    <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>
                    {")"}
                  </p>
                ) : (
                  // "open-meteo", or no provider field (older backend: Open-Meteo only).
                  <p className="ks-credit">
                    <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">{t(T.weatherCreditOpenMeteo)}</a>
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {tab === "sowing" && (
          <div>
            <div className="ks-kv"><span className="ks-k">{t(T.window)}</span><span className="ks-v">{t(SOWING[crop].window)}</span></div>
            <div className="ks-kv"><span className="ks-k">{t(T.soil)}</span><span className="ks-v">{t(SOWING[crop].soil)}</span></div>
            <p className="ks-tip">{t(SOWING[crop].tip)}</p>
          </div>
        )}

        {tab === "advisory" && (
          <div>
            {advisoryLoading && (
              <>
                <Skeleton head lines={4} />
                <p className="ks-loading-text">{t(T.advisoryLoading)}</p>
              </>
            )}

            {!advisoryLoading && advisoryError && (
              <EmptyState icon="🧭" text={t(T.advisoryError)}
                action={retryButton(() => { setAdvisory(null); setAdvisoryError(false); })} />
            )}

            {!advisoryLoading && !advisoryError && advisory && (
              <div>
                <p className="ks-advice-for">{t(T.paddyAdvice)}</p>
                {advisory.current_season === false ? (
                  <>
                    <p className="ks-verdict" data-status="past">
                      {t(T.pastResult(advisory.season, ADVISORY_PAST_VERDICT[advisory.status]))}
                    </p>
                    <Note icon="ℹ️">{t(T.referenceOnly)}</Note>
                  </>
                ) : (
                  <p className="ks-verdict" data-status={advisory.status}>
                    <span aria-hidden="true">{ADVISORY_STATUS_ICON[advisory.status]}</span>
                    {t(ADVISORY_STATUS_LABEL[advisory.status])}
                  </p>
                )}
                <p className="ks-reasoning">{t(advisory.reasoning)}</p>
                {advisory.note && <Note>{t(advisory.note)}</Note>}
                {rainNote && <Note icon="ℹ️">{t(rainNote)}</Note>}
              </div>
            )}
          </div>
        )}

        {tab === "mandi" && (
          <div>
            {!mandi && <Skeleton lines={4} />}
            {mandi && mandiNote && <Note>{t(mandiNote)}</Note>}
            {mandi && prices.length === 0 && (
              <EmptyState icon="💰" text={t(T.mandiEmpty)} />
            )}
            {prices.map((p, i) => (
              <div key={i} className="ks-price">
                <span className="ks-price-name">{t(p.mandi)}</span>
                <span className="ks-price-value">₹{p.price.toLocaleString("en-IN")}</span>
                <span className="ks-trend" data-trend={p.trend} role="img" aria-label={t(TREND_LABEL[p.trend])}
                  title={t(TREND_LABEL[p.trend])}>
                  {TREND_MARK[p.trend]}
                </span>
              </div>
            ))}
            {best && (
              <p className="ks-best">
                {t(T.best)}: <strong>{t(best.mandi)}</strong>, ₹{best.price.toLocaleString("en-IN")}{t(T.perQuintal)}
              </p>
            )}
          </div>
        )}

        {tab === "pest" && (
          <div>
            {PESTS[crop].map((p, i) => (
              <div key={i} className="ks-pest">
                <span className="ks-level" data-level={p.level}>{t(LEVEL_LABEL[p.level])}</span>
                <div><div className="ks-pest-name">{t(p.name)}</div><div className="ks-pest-note">{t(p.note)}</div></div>
              </div>
            ))}
          </div>
        )}

        {tab === "disease" && (
          <div>
            <input ref={fileRef} type="file" accept="image/*" capture="environment"
              onChange={onFile} hidden />
            <button type="button" className="ks-btn ks-btn-big" onClick={() => fileRef.current.click()} disabled={busy}>
              <span aria-hidden="true">📷</span> {t(T.disease)}
            </button>
            <p className="ks-hint">{t(T.uploadHint)}</p>

            {busy && (
              <div className="ks-result">
                <Skeleton head lines={3} />
                <p className="ks-loading-text">{t(T.analyzing)}</p>
              </div>
            )}

            {predFailed && <div className="ks-result"><Note>{t(T.predictFailed)}</Note></div>}
            {/* wrong_crop / unsupported: a notice, never a disease result */}
            {predNotice && <div className="ks-result"><Note>{t(pred.message)}</Note></div>}
            {predOk && (
              <div className="ks-result">
                <div className="ks-result-head">
                  <span className="ks-result-crop">{t(pred.crop)}</span>
                  <span className="ks-result-disease" data-healthy={!!pred.healthy}>{t(pred.disease)}</span>
                </div>
                <div className="ks-conf" aria-hidden="true">
                  <div className="ks-conf-fill" data-low={!!pred.low_confidence} style={{ width: `${pred.confidence}%` }} />
                </div>
                <div className="ks-conf-text">{pred.confidence}% {t(T.confidence)}</div>
                <p className="ks-result-desc">{t(pred.description)}</p>
                {!pred.healthy && (
                  <div className="ks-action">
                    <strong>{t(T.whatToDo)}:</strong> {t(pred.action)}
                  </div>
                )}
                {pred.low_confidence && <Note>{t(pred.note)}</Note>}
                <p className="ks-credit">{t(T.modelCaveat)}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
