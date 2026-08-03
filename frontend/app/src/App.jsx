import React, { useState, useEffect, useRef } from "react";

// ── Backend URL. When running locally: http://localhost:8000 ────────────────
const API_BASE = "http://localhost:8000";

// Fallback data so the UI still renders if the backend isn't running yet.
const FALLBACK_WEATHER = {
  location: { en: "Ranchi, Jharkhand", hi: "रांची, झारखंड" },
  days: [
    { day: { en: "Sat", hi: "शनि" }, tmax: 31, tmin: 24, rain_mm: 2,  cond: { en: "Partly cloudy", hi: "आंशिक बादल" } },
    { day: { en: "Sun", hi: "रवि" }, tmax: 30, tmin: 24, rain_mm: 12, cond: { en: "Light rain", hi: "हल्की बारिश" } },
    { day: { en: "Mon", hi: "सोम" }, tmax: 29, tmin: 23, rain_mm: 24, cond: { en: "Rain", hi: "बारिश" } },
    { day: { en: "Tue", hi: "मंगल" }, tmax: 30, tmin: 23, rain_mm: 8,  cond: { en: "Showers", hi: "बौछारें" } },
    { day: { en: "Wed", hi: "बुध" }, tmax: 32, tmin: 24, rain_mm: 0,  cond: { en: "Sunny", hi: "धूप" } },
    { day: { en: "Thu", hi: "गुरु" }, tmax: 33, tmin: 25, rain_mm: 0,  cond: { en: "Sunny", hi: "धूप" } },
    { day: { en: "Fri", hi: "शुक्र" }, tmax: 31, tmin: 24, rain_mm: 6, cond: { en: "Cloudy", hi: "बादल" } },
  ],
};
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
  title: { en: "Kisan Dashboard", hi: "किसान डैशबोर्ड" },
  sub: { en: "Ranchi District", hi: "रांची ज़िला" },
  weather: { en: "Weather", hi: "मौसम" },
  sowing: { en: "Sowing", hi: "बुआई सलाह" },
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
};

const trendMark = { up: "▲", down: "▼", flat: "—" };
const trendColor = { up: "#2f7d4f", down: "#b23b3b", flat: "#8a7f6b" };
const levelColor = { high: "#b23b3b", medium: "#c98a2b", low: "#2f7d4f" };
const MODULES = ["weather", "sowing", "mandi", "pest", "disease"];
const MODULE_ICON = { weather: "🌦️", sowing: "🌱", mandi: "💰", pest: "🐛", disease: "🔬" };

export default function KisanDashboard() {
  const [lang, setLang] = useState("hi");
  const [crop, setCrop] = useState("paddy");
  const [tab, setTab] = useState("weather");
  const [weather, setWeather] = useState(FALLBACK_WEATHER);
  const [mandi, setMandi] = useState(FALLBACK_MANDI);
  const [online, setOnline] = useState(false);
  const [pred, setPred] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();
  const t = (o) => (o ? o[lang] : "");

  useEffect(() => {
    fetch(`${API_BASE}/weather`).then(r => r.json()).then(d => { setWeather(d); setOnline(true); }).catch(() => {});
    fetch(`${API_BASE}/mandi`).then(r => r.json()).then(setMandi).catch(() => {});
  }, []);

  const prices = (mandi[crop] || []);
  const best = prices.reduce((a, b) => (b.price > (a?.price ?? 0) ? b : a), prices[0]);

  async function onFile(e) {
    const f = e.target.files[0];
    if (!f) return;
    setBusy(true); setPred(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("crop", crop);
      const r = await fetch(`${API_BASE}/predict`, { method: "POST", body: fd });
      setPred(await r.json());
    } catch {
      setPred({ error: true });
    }
    setBusy(false);
  }

  return (
    <div style={S.page}>
      <style>{css}</style>
      <header style={S.header}>
        <div>
          <h1 style={S.h1}>{t(T.title)}</h1>
          <p style={S.subline}>{t(T.sub)} {online ? "🟢" : "🟡"}</p>
        </div>
        <button style={S.langBtn} onClick={() => setLang(lang === "hi" ? "en" : "hi")}>
          {lang === "hi" ? "English" : "हिंदी"}
        </button>
      </header>

      {!online && <div style={S.offline}>{t(T.offline)}</div>}

      {/* Crop selector — big tap targets */}
      <div style={S.cropRow}>
        {CROPS.map((c) => (
          <button key={c.id} onClick={() => setCrop(c.id)}
            style={{ ...S.cropBtn, ...(crop === c.id ? S.cropOn : {}) }}>
            <span style={S.cropIcon}>{c.icon}</span>
            <span>{t(c)}</span>
          </button>
        ))}
      </div>

      {/* Module tabs — icon-first for low literacy */}
      <div style={S.tabs}>
        {MODULES.map((m) => (
          <button key={m} onClick={() => setTab(m)}
            style={{ ...S.tab, ...(tab === m ? S.tabOn : {}) }}>
            <span style={S.tabIcon}>{MODULE_ICON[m]}</span>
            <span style={S.tabLabel}>{t(T[m])}</span>
          </button>
        ))}
      </div>

      <div style={S.panel}>
        {tab === "weather" && (
          <div style={S.weekRow}>
            {weather.days.map((w, i) => (
              <div key={i} style={S.day}>
                <div style={S.dayName}>{t(w.day)}</div>
                <div style={S.temp}>{w.tmax}°</div>
                <div style={S.tempMin}>{w.tmin}°</div>
                <div style={{ ...S.rain, opacity: w.rain_mm > 0 ? 1 : 0.3 }}>
                  {w.rain_mm > 0 ? `${w.rain_mm}mm` : "—"}
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "sowing" && (
          <div>
            <div style={S.kv}><span style={S.k}>{t(T.window)}</span><span style={S.v}>{t(SOWING[crop].window)}</span></div>
            <div style={S.kv}><span style={S.k}>{t(T.soil)}</span><span style={S.v}>{t(SOWING[crop].soil)}</span></div>
            <p style={S.tip}>{t(SOWING[crop].tip)}</p>
          </div>
        )}

        {tab === "mandi" && (
          <div>
            {prices.map((p, i) => (
              <div key={i} style={S.priceRow}>
                <span style={S.mandiName}>{t(p.mandi)}</span>
                <span style={S.price}>₹{p.price.toLocaleString("en-IN")}</span>
                <span style={{ ...S.trend, color: trendColor[p.trend] }}>{trendMark[p.trend]}</span>
              </div>
            ))}
            {best && <div style={S.bestBox}>{t(T.best)}: <strong>{t(best.mandi)}</strong> · ₹{best.price.toLocaleString("en-IN")}/क्विंटल</div>}
          </div>
        )}

        {tab === "pest" && (
          <div>
            {PESTS[crop].map((p, i) => (
              <div key={i} style={S.pestRow}>
                <span style={{ ...S.badge, background: levelColor[p.level] }}>●</span>
                <div><div style={S.pestName}>{t(p.name)}</div><div style={S.pestNote}>{t(p.note)}</div></div>
              </div>
            ))}
          </div>
        )}

        {tab === "disease" && (
          <div style={S.diseaseBox}>
            <input ref={fileRef} type="file" accept="image/*" capture="environment"
              onChange={onFile} style={{ display: "none" }} />
            <button style={S.uploadBtn} onClick={() => fileRef.current.click()}>
              📷 {t(T.disease)}
            </button>
            <p style={S.uploadHint}>{t(T.uploadHint)}</p>

            {busy && <p style={S.analyzing}>{t(T.analyzing)}</p>}

            {pred && pred.error && <p style={S.err}>{t(T.offline)}</p>}
            {pred && !pred.error && (
              <div style={S.result}>
                <div style={S.resultHead}>
                  <span style={S.resultCrop}>{t(pred.crop)}</span>
                  <span style={{ ...S.resultDisease, color: pred.healthy ? "#2f7d4f" : "#b23b3b" }}>
                    {t(pred.disease)}
                  </span>
                </div>
                <div style={S.confBar}>
                  <div style={{ ...S.confFill, width: `${pred.confidence}%`,
                    background: pred.low_confidence ? "#c98a2b" : "#6b8e23" }} />
                </div>
                <div style={S.confText}>{pred.confidence}% {t(T.confidence)}</div>
                <p style={S.resultDesc}>{t(pred.description)}</p>
                {!pred.healthy && (
                  <div style={S.actionBox}>
                    <strong>{t(T.whatToDo)}:</strong> {t(pred.action)}
                  </div>
                )}
                {pred.low_confidence && <p style={S.lowConf}>⚠️ {t(pred.note)}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const soil = "#efe7d6", ink = "#2c2419", clay = "#a0522d", line = "#d8ccb4";
const css = `@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`;
const S = {
  page: { fontFamily: "'Segoe UI', system-ui, sans-serif", background: soil, color: ink, minHeight: "100vh", padding: 16, maxWidth: 640, margin: "0 auto", animation: "rise .4s ease" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: `3px solid ${clay}`, paddingBottom: 10, marginBottom: 12 },
  h1: { fontSize: 24, margin: 0, fontWeight: 800 },
  subline: { margin: "2px 0 0", fontSize: 13, color: "#7a6d54", fontWeight: 600 },
  langBtn: { background: ink, color: soil, border: "none", borderRadius: 6, padding: "8px 14px", fontSize: 14, fontWeight: 700, cursor: "pointer" },
  offline: { background: "#fbf0d5", border: "1px solid #e6cf8f", borderRadius: 8, padding: 8, fontSize: 12, color: "#7a5c1e", marginBottom: 12 },
  cropRow: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8, marginBottom: 12 },
  cropBtn: { display: "flex", flexDirection: "column", alignItems: "center", gap: 4, border: `1.5px solid ${line}`, background: "#fff", borderRadius: 12, padding: "10px 4px", fontSize: 13, fontWeight: 700, cursor: "pointer", color: ink },
  cropOn: { background: clay, color: "#fff", borderColor: clay },
  cropIcon: { fontSize: 24 },
  tabs: { display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 6, marginBottom: 14 },
  tab: { display: "flex", flexDirection: "column", alignItems: "center", gap: 3, border: `1px solid ${line}`, background: "#fffdf8", borderRadius: 10, padding: "8px 2px", cursor: "pointer", color: ink },
  tabOn: { background: "#3a2e1a", color: "#fff", borderColor: "#3a2e1a" },
  tabIcon: { fontSize: 20 },
  tabLabel: { fontSize: 10, fontWeight: 700, textAlign: "center", lineHeight: 1.1 },
  panel: { background: "#fffdf8", border: `1px solid ${line}`, borderRadius: 12, padding: 16, minHeight: 180, boxShadow: "0 1px 3px rgba(80,60,20,.06)" },
  weekRow: { display: "flex", justifyContent: "space-between", gap: 4 },
  day: { textAlign: "center", flex: 1 },
  dayName: { fontSize: 12, fontWeight: 700, color: "#7a6d54" },
  temp: { fontSize: 17, fontWeight: 800, marginTop: 4 },
  tempMin: { fontSize: 12, color: "#9a8d72" },
  rain: { fontSize: 11, color: "#3a6ea5", fontWeight: 700, marginTop: 2 },
  kv: { display: "flex", justifyContent: "space-between", gap: 10, padding: "8px 0", borderBottom: `1px dashed ${line}` },
  k: { fontSize: 14, color: "#7a6d54", fontWeight: 600 },
  v: { fontSize: 14, fontWeight: 700, textAlign: "right" },
  tip: { fontSize: 14, marginTop: 10, marginBottom: 0, lineHeight: 1.5, color: "#4a3f2c", background: "#f4efe2", padding: 10, borderRadius: 8, borderLeft: `3px solid #6b8e23` },
  priceRow: { display: "grid", gridTemplateColumns: "1fr auto auto", alignItems: "center", gap: 10, padding: "9px 0", borderBottom: `1px dashed ${line}` },
  mandiName: { fontSize: 15, fontWeight: 600 },
  price: { fontSize: 16, fontWeight: 800 },
  trend: { fontSize: 14, fontWeight: 800, width: 16, textAlign: "center" },
  bestBox: { marginTop: 12, background: "#f0f5ec", border: "1px solid #cfe0c2", borderRadius: 8, padding: 10, fontSize: 14, color: "#2f5d38" },
  pestRow: { display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 0" },
  badge: { color: "#fff", fontSize: 16, lineHeight: 1 },
  pestName: { fontSize: 15, fontWeight: 700 },
  pestNote: { fontSize: 13, color: "#6a5f48", marginTop: 2 },
  diseaseBox: { textAlign: "center" },
  uploadBtn: { background: clay, color: "#fff", border: "none", borderRadius: 12, padding: "16px 24px", fontSize: 18, fontWeight: 800, cursor: "pointer", width: "100%" },
  uploadHint: { fontSize: 13, color: "#7a6d54", marginTop: 8 },
  analyzing: { fontSize: 15, fontWeight: 700, color: clay },
  err: { fontSize: 13, color: "#b23b3b" },
  result: { textAlign: "left", marginTop: 12, background: "#faf6 ", borderRadius: 10 },
  resultHead: { display: "flex", justifyContent: "space-between", alignItems: "baseline" },
  resultCrop: { fontSize: 15, fontWeight: 700, color: "#7a6d54" },
  resultDisease: { fontSize: 19, fontWeight: 800 },
  confBar: { height: 8, background: "#e8ddc5", borderRadius: 4, marginTop: 10, overflow: "hidden" },
  confFill: { height: "100%", borderRadius: 4 },
  confText: { fontSize: 12, color: "#7a6d54", marginTop: 4, fontWeight: 600 },
  resultDesc: { fontSize: 14, lineHeight: 1.5, marginTop: 10 },
  actionBox: { background: "#f4efe2", borderLeft: `3px solid #6b8e23`, padding: 10, borderRadius: 8, fontSize: 14, lineHeight: 1.5, marginTop: 8 },
  lowConf: { fontSize: 13, color: "#c98a2b", marginTop: 8, fontWeight: 600 },
};
