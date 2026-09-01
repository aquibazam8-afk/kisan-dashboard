import React, { useState, useEffect, useCallback } from "react";

// ── District Situation Dashboard ─────────────────────────────────────────
// Separate route (/staff) for ATMA/KVK extension staff. Dense, table-first
// ops view — not the farmer app's card UI. Ranchi district only for now.
const API_BASE = "http://localhost:8000";
const DISTRICT = "Ranchi";

const CROPS = [
  { id: "paddy", en: "Paddy", hi: "धान" },
  { id: "maize", en: "Maize", hi: "मक्का" },
  { id: "arhar", en: "Arhar", hi: "अरहर" },
  { id: "veg", en: "Vegetables", hi: "सब्ज़ी" },
  { id: "tomato", en: "Tomato", hi: "टमाटर" },
  { id: "potato", en: "Potato", hi: "आलू" },
  { id: "onion", en: "Onion", hi: "प्याज़" },
  { id: "cauliflower", en: "Cauliflower", hi: "फूलगोभी" },
];

const CATEGORY_COLOR = {
  "Large Excess": "#1d5fa8",
  "Excess": "#2f7d4f",
  "Normal": "#2f7d4f",
  "Deficient": "#c98a2b",
  "Large Deficient": "#b23b3b",
  "No Rain": "#7a1f1f",
};

const STATUS_LABEL = {
  sow: { en: "SOW", hi: "बोएं" },
  wait: { en: "WAIT", hi: "प्रतीक्षा" },
  switch: { en: "SWITCH", hi: "बदलें" },
};
const STATUS_COLOR = { sow: "#2f7d4f", wait: "#c98a2b", switch: "#b23b3b" };
const TREND_MARK = { up: "▲", down: "▼", flat: "—" };
const TREND_COLOR = { up: "#2f7d4f", down: "#b23b3b", flat: "#8a7f6b" };

function fmtDate(iso) {
  if (!iso) return "—";
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function ErrorBox({ onRetry }) {
  return (
    <div style={S.errBox}>
      <span>⚠ Could not load. <span style={S.hiText}>लोड नहीं हो सका।</span></span>
      <button style={S.retryBtn} onClick={onRetry}>Retry / फिर कोशिश करें</button>
    </div>
  );
}

export default function StaffDashboard() {
  const [advisory, setAdvisory] = useState(null);
  const [advisoryLoading, setAdvisoryLoading] = useState(true);
  const [advisoryError, setAdvisoryError] = useState(false);

  const [mandi, setMandi] = useState(null);
  const [mandiLoading, setMandiLoading] = useState(true);
  const [mandiError, setMandiError] = useState(false);

  const [advisoryAt, setAdvisoryAt] = useState(null);
  const [mandiAt, setMandiAt] = useState(null);

  const loadAdvisory = useCallback(() => {
    setAdvisoryLoading(true);
    setAdvisoryError(false);
    fetch(`${API_BASE}/sowing-advisory?district=${DISTRICT}`)
      .then((r) => { if (!r.ok) throw new Error("advisory fetch failed"); return r.json(); })
      .then((d) => { setAdvisory(d); setAdvisoryAt(new Date()); })
      .catch(() => setAdvisoryError(true))
      .finally(() => setAdvisoryLoading(false));
  }, []);

  const loadMandi = useCallback(() => {
    setMandiLoading(true);
    setMandiError(false);
    // /mandi with no ?crop= returns every crop's price list in one call.
    fetch(`${API_BASE}/mandi`)
      .then((r) => { if (!r.ok) throw new Error("mandi fetch failed"); return r.json(); })
      .then((d) => { setMandi(d); setMandiAt(new Date()); })
      .catch(() => setMandiError(true))
      .finally(() => setMandiLoading(false));
  }, []);

  // Independent effects — one section's failure never blocks the other.
  useEffect(() => { loadAdvisory(); }, [loadAdvisory]);
  useEffect(() => { loadMandi(); }, [loadMandi]);

  const mandiRows = CROPS.map((c) => {
    const prices = (mandi && mandi[c.id]) || [];
    const best = prices.reduce(
      (a, b) => (b.price > (a?.price ?? -Infinity) ? b : a),
      null
    );
    return { crop: c, best };
  });

  return (
    <div style={S.page}>
      <style>{css}</style>
      <header style={S.header}>
        <div>
          <div style={S.h1}>
            District Situation Dashboard <span style={S.h1hi}>ज़िला स्थिति डैशबोर्ड</span>
          </div>
          <div style={S.sub}>
            Ranchi District <span style={S.hiText}>राँची ज़िला</span> · ATMA / KVK Staff View
          </div>
        </div>
        <button
          style={S.refreshBtn}
          onClick={() => { loadAdvisory(); loadMandi(); }}
        >
          ⟳ Refresh / ताज़ा करें
        </button>
      </header>

      <div className="sd-grid">
        {/* ── Rainfall status ──────────────────────────────────────── */}
        <section style={S.panel}>
          <h2 style={S.h2}>
            Rainfall Status <span style={S.h2hi}>वर्षा स्थिति</span>
          </h2>

          {advisoryLoading && <p style={S.loading}>Loading… <span style={S.hiText}>लोड हो रहा है…</span></p>}
          {!advisoryLoading && advisoryError && <ErrorBox onRetry={loadAdvisory} />}

          {!advisoryLoading && !advisoryError && advisory && (
            <>
              {!advisory.current_season && advisory.note && (
                <div style={S.warnNote}>
                  ⚠ {advisory.note.en}
                  <br />
                  <span style={S.hiText}>{advisory.note.hi}</span>
                </div>
              )}
              <table style={S.kvTable}>
                <tbody>
                  <tr>
                    <td style={S.kCell}>Window <span style={S.hiText}>अवधि</span></td>
                    <td style={S.vCell}>
                      {fmtDate(advisory.window_start)}–{fmtDate(advisory.window_end)}
                      <span style={S.dim}> (as of {fmtDate(advisory.as_of)})</span>
                    </td>
                  </tr>
                  <tr>
                    <td style={S.kCell}>Actual <span style={S.hiText}>वास्तविक</span></td>
                    <td style={S.vCellNum}>{advisory.cumulative_rain_mm} mm</td>
                  </tr>
                  <tr>
                    <td style={S.kCell}>Normal <span style={S.hiText}>सामान्य</span></td>
                    <td style={S.vCellNum}>
                      {advisory.normal_rain_mm} mm
                      <span style={S.dim}> ({advisory.normal_years_count}-yr avg)</span>
                    </td>
                  </tr>
                  <tr>
                    <td style={S.kCell}>Departure <span style={S.hiText}>विचलन</span></td>
                    <td style={{ ...S.vCellNum, fontWeight: 800 }}>
                      {advisory.departure_pct > 0 ? "+" : ""}
                      {advisory.departure_pct}%
                    </td>
                  </tr>
                  <tr>
                    <td style={S.kCell}>Category <span style={S.hiText}>श्रेणी</span></td>
                    <td style={S.vCell}>
                      <span
                        style={{
                          ...S.badge,
                          background: CATEGORY_COLOR[advisory.category] || "#555",
                        }}
                      >
                        {advisory.category}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
              {advisoryAt && (
                <div style={S.footnote}>Updated {advisoryAt.toLocaleTimeString("en-IN")}</div>
              )}
            </>
          )}
        </section>

        {/* ── Sowing recommendation ────────────────────────────────── */}
        <section style={S.panel}>
          <h2 style={S.h2}>
            Sowing Recommendation <span style={S.h2hi}>बुआई सलाह</span>
          </h2>

          {advisoryLoading && <p style={S.loading}>Loading… <span style={S.hiText}>लोड हो रहा है…</span></p>}
          {!advisoryLoading && advisoryError && <ErrorBox onRetry={loadAdvisory} />}

          {!advisoryLoading && !advisoryError && advisory && (
            <>
              <div style={{ ...S.statusBadge, background: STATUS_COLOR[advisory.status] }}>
                {STATUS_LABEL[advisory.status].en} · {STATUS_LABEL[advisory.status].hi}
              </div>
              <p style={S.reasonEn}>{advisory.reasoning.en}</p>
              <p style={S.reasonHi}>{advisory.reasoning.hi}</p>
              {advisory.alternative_crop && (
                <div style={S.meta}>
                  Alternative crop: <strong>{advisory.alternative_crop.en}</strong> / {advisory.alternative_crop.hi}
                </div>
              )}
              {advisory.wait_window_days != null && (
                <div style={S.meta}>
                  Reassess in {advisory.wait_window_days} days / {advisory.wait_window_days} दिन बाद फिर जाँचें
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {/* ── Mandi prices ───────────────────────────────────────────── */}
      <section style={S.panelWide}>
        <h2 style={S.h2}>
          Mandi Prices — All Crops <span style={S.h2hi}>मंडी भाव — सभी फसलें</span>
        </h2>

        {mandiLoading && <p style={S.loading}>Loading… <span style={S.hiText}>लोड हो रहा है…</span></p>}
        {!mandiLoading && mandiError && <ErrorBox onRetry={loadMandi} />}

        {!mandiLoading && !mandiError && mandi && (
          <>
            <table style={S.mandiTable} className="sd-mandi-table">
              <thead>
                <tr>
                  <th style={S.th}>Crop <span style={S.hiText}>फसल</span></th>
                  <th style={S.th}>Best Mandi <span style={S.hiText}>सबसे अच्छी मंडी</span></th>
                  <th style={S.thNum}>Price (₹/qtl)</th>
                  <th style={S.thNum}>Trend</th>
                </tr>
              </thead>
              <tbody>
                {mandiRows.map(({ crop, best }) => (
                  <tr key={crop.id}>
                    <td style={S.td}>
                      {crop.en} <span style={S.hiText}>{crop.hi}</span>
                    </td>
                    <td style={S.td}>
                      {best ? (
                        <>
                          {best.mandi.en} <span style={S.hiText}>{best.mandi.hi}</span>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td style={S.tdNum}>{best ? `₹${best.price.toLocaleString("en-IN")}` : "—"}</td>
                    <td style={{ ...S.tdNum, color: best ? TREND_COLOR[best.trend] : "#999" }}>
                      {best ? TREND_MARK[best.trend] : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {mandiAt && (
              <div style={S.footnote}>Updated {mandiAt.toLocaleTimeString("en-IN")}</div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

const ink = "#1a2233", line = "#d7dbe3", panelBg = "#ffffff", pageBg = "#eef0f4";
const css = `
  .sd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  @media (max-width: 760px) { .sd-grid { grid-template-columns: 1fr; } }
  .sd-mandi-table tbody tr:nth-child(even) { background: #f6f7fa; }
  .sd-mandi-table tbody tr:hover { background: #eef2fb; }
`;

const S = {
  page: {
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    background: pageBg,
    color: ink,
    minHeight: "100vh",
    padding: "18px 20px 40px",
    maxWidth: 1080,
    margin: "0 auto",
    lineHeight: 1.35,
    letterSpacing: "normal",
    fontSize: 13,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: ink,
    color: "#fff",
    borderRadius: 8,
    padding: "12px 16px",
    marginBottom: 14,
  },
  h1: { fontSize: 18, fontWeight: 800, margin: 0 },
  h1hi: { fontSize: 14, fontWeight: 500, color: "#c9cfdc", marginLeft: 6 },
  sub: { fontSize: 12, color: "#aab0c0", marginTop: 3, fontWeight: 600 },
  hiText: { color: "#6b7285", fontWeight: 500 },
  refreshBtn: {
    background: "#2c3650",
    color: "#fff",
    border: "1px solid #445071",
    borderRadius: 6,
    padding: "7px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  panel: {
    background: panelBg,
    border: `1px solid ${line}`,
    borderRadius: 8,
    padding: "12px 14px",
  },
  panelWide: {
    background: panelBg,
    border: `1px solid ${line}`,
    borderRadius: 8,
    padding: "12px 14px",
  },
  h2: {
    fontSize: 13,
    fontWeight: 800,
    textTransform: "uppercase",
    letterSpacing: "0.4px",
    margin: "0 0 10px",
    paddingBottom: 8,
    borderBottom: `2px solid ${ink}`,
    color: ink,
  },
  h2hi: { fontSize: 12, fontWeight: 500, color: "#6b7285", textTransform: "none", letterSpacing: 0, marginLeft: 4 },
  loading: { fontSize: 12, color: "#6b7285", fontWeight: 600, margin: "6px 0" },
  errBox: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "#fbeaea", border: "1px solid #eec2c2", borderRadius: 6, padding: "8px 10px", fontSize: 12, color: "#8a2c2c" },
  retryBtn: { background: "#b23b3b", color: "#fff", border: "none", borderRadius: 5, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" },
  warnNote: { fontSize: 11, background: "#fbf0d5", border: "1px solid #e6cf8f", borderRadius: 6, padding: "6px 8px", marginBottom: 10, color: "#7a5c1e", lineHeight: 1.4 },
  kvTable: { width: "100%", borderCollapse: "collapse" },
  kCell: { fontSize: 12, color: "#6b7285", fontWeight: 600, padding: "6px 8px 6px 0", borderBottom: `1px dashed ${line}`, whiteSpace: "nowrap", verticalAlign: "top" },
  vCell: { fontSize: 12, fontWeight: 700, padding: "6px 0", borderBottom: `1px dashed ${line}`, textAlign: "right" },
  vCellNum: { fontSize: 13, fontWeight: 800, padding: "6px 0", borderBottom: `1px dashed ${line}`, textAlign: "right", fontVariantNumeric: "tabular-nums" },
  dim: { fontSize: 11, fontWeight: 500, color: "#8a90a3" },
  badge: { display: "inline-block", color: "#fff", fontSize: 11, fontWeight: 800, padding: "3px 8px", borderRadius: 4 },
  footnote: { fontSize: 10, color: "#9aa0b0", marginTop: 8, textAlign: "right" },
  statusBadge: { display: "inline-block", color: "#fff", fontSize: 13, fontWeight: 900, padding: "5px 12px", borderRadius: 5, marginBottom: 10, letterSpacing: "0.5px" },
  reasonEn: { fontSize: 12, lineHeight: 1.5, margin: "0 0 6px", color: "#2a3142" },
  reasonHi: { fontSize: 12, lineHeight: 1.5, margin: "0 0 8px", color: "#6b7285" },
  meta: { fontSize: 11, color: "#4a5164", background: "#f4f5f8", borderLeft: `3px solid ${ink}`, padding: "5px 8px", borderRadius: 4, marginTop: 6 },
  mandiTable: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: { textAlign: "left", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.3px", color: "#6b7285", padding: "6px 8px", borderBottom: `2px solid ${ink}` },
  thNum: { textAlign: "right", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.3px", color: "#6b7285", padding: "6px 8px", borderBottom: `2px solid ${ink}` },
  td: { padding: "7px 8px", borderBottom: `1px solid ${line}`, fontWeight: 600 },
  tdNum: { padding: "7px 8px", borderBottom: `1px solid ${line}`, fontWeight: 800, textAlign: "right", fontVariantNumeric: "tabular-nums" },
};
