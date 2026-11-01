import React, { useState, useEffect, useCallback } from "react";

// ── District Situation Dashboard ─────────────────────────────────────────
// Separate route (/staff) for ATMA/KVK extension staff. Dense, table-first
// ops view — not the farmer app's card UI. Ranchi district only for now.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
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
  "Excess": "#1F6B3E",
  "Normal": "#1F6B3E",
  "Deficient": "#7A4E00",
  "Large Deficient": "#9C2A22",
  "No Rain": "#6E1C17",
};

const STATUS_LABEL = {
  sow: { en: "SOW", hi: "बोएं" },
  wait: { en: "WAIT", hi: "प्रतीक्षा" },
  switch: { en: "SWITCH", hi: "बदलें" },
};
// Badge backgrounds behind white text; each meets WCAG AA (≥4.5:1).
const STATUS_COLOR = { sow: "#1F6B3E", wait: "#7A4E00", switch: "#9C2A22" };
// current_season: false — a past window's result, shown in a neutral colour.
const PAST_STATUS_COLOR = "#635B49";
const TREND_MARK = { up: "▲", down: "▼", flat: "—" };
const TREND_COLOR = { up: "var(--good)", down: "var(--bad)", flat: "var(--muted)" };

function fmtDate(iso) {
  if (!iso) return "—";
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

// "2026-10-21" -> "21/10/2026" (data dates can be from an earlier year)
function fmtFullDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

// Bilingual note on where a section's data came from, or null when it's live
// (the footnote's data date covers that) or /data-status is unavailable.
function SourceNote({ status, kind }) {
  if (!status) return null;
  const d = fmtFullDate(status.as_of);
  let en, hi;
  if (kind === "mandi" && status.source === "sample") {
    en = "Sample prices — live market data unavailable";
    hi = "नमूना भाव — लाइव मंडी डेटा उपलब्ध नहीं";
  } else if (kind === "mandi" && status.source === "snapshot") {
    en = `Prices as of ${d}`;
    hi = `${d} के भाव`;
  } else if (kind === "rainfall" && status.source === "snapshot") {
    en = `Rainfall data saved on ${d}`;
    hi = `वर्षा डेटा ${d} को सहेजा गया`;
  } else {
    return null;
  }
  return (
    <div style={S.warnNote}>
      ⚠ {en}
      <br />
      <span style={S.hiText}>{hi}</span>
    </div>
  );
}

// Footnote with the data's own date (not the browser's fetch time, which
// says nothing about how fresh the data is). Shown only for live data —
// SourceNote already gives the date for snapshots.
function DataDate({ status }) {
  if (status?.source !== "live" || !status.as_of) return null;
  const d = fmtFullDate(status.as_of);
  return <div style={S.footnote}>Data date {d} · डेटा तिथि {d}</div>;
}

function Loading() {
  return (
    <div>
      <span className="ks-skel" aria-hidden="true" style={{ width: "90%" }} />
      <span className="ks-skel" aria-hidden="true" style={{ width: "70%" }} />
      <span className="ks-skel" aria-hidden="true" style={{ width: "80%" }} />
      <p style={S.loading}>Loading… <span style={S.hiText}>लोड हो रहा है…</span></p>
    </div>
  );
}

function ErrorBox({ onRetry }) {
  return (
    <div style={S.errBox}>
      <span>⚠ Could not load. <span style={S.hiText}>लोड नहीं हो सका।</span></span>
      <button type="button" style={S.retryBtn} onClick={onRetry}>Retry / फिर कोशिश करें</button>
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

  const [dataStatus, setDataStatus] = useState(null);

  const loadAdvisory = useCallback(() => {
    setAdvisoryLoading(true);
    setAdvisoryError(false);
    fetch(`${API_BASE}/sowing-advisory?district=${DISTRICT}`)
      .then((r) => { if (!r.ok) throw new Error("advisory fetch failed"); return r.json(); })
      .then(setAdvisory)
      .catch(() => setAdvisoryError(true))
      .finally(() => setAdvisoryLoading(false));
  }, []);

  const loadMandi = useCallback(() => {
    setMandiLoading(true);
    setMandiError(false);
    // /mandi with no ?crop= returns every crop's price list in one call.
    fetch(`${API_BASE}/mandi`)
      .then((r) => { if (!r.ok) throw new Error("mandi fetch failed"); return r.json(); })
      .then(setMandi)
      .catch(() => setMandiError(true))
      .finally(() => setMandiLoading(false));
  }, []);

  // Where the data came from (live/snapshot/sample) and its date. On failure
  // dataStatus is null and the source notes/data dates are simply hidden.
  const loadDataStatus = useCallback(() => {
    fetch(`${API_BASE}/data-status?district=${DISTRICT}`)
      .then((r) => { if (!r.ok) throw new Error("data-status fetch failed"); return r.json(); })
      .then(setDataStatus)
      .catch(() => setDataStatus(null));
  }, []);

  useEffect(() => { document.title = "Khet Saathi — District dashboard"; }, []);

  // Independent effects — one section's failure never blocks the other.
  useEffect(() => { loadAdvisory(); }, [loadAdvisory]);
  useEffect(() => { loadMandi(); }, [loadMandi]);
  useEffect(() => { loadDataStatus(); }, [loadDataStatus]);

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
          <h1 style={S.h1}>
            District Situation Dashboard <span style={S.h1hi} lang="hi">ज़िला स्थिति डैशबोर्ड</span>
          </h1>
          <div style={S.sub}>
            Khet Saathi <span lang="hi">खेत साथी</span> · Ranchi District <span lang="hi">राँची ज़िला</span> · ATMA / KVK Staff View
          </div>
        </div>
        <button
          type="button"
          style={S.refreshBtn}
          onClick={() => { loadAdvisory(); loadMandi(); loadDataStatus(); }}
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

          {advisoryLoading && <Loading />}
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
              <SourceNote status={dataStatus?.rainfall} kind="rainfall" />
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
                          background: CATEGORY_COLOR[advisory.category] || "#635B49",
                        }}
                      >
                        {advisory.category}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <DataDate status={dataStatus?.rainfall} />
            </>
          )}
        </section>

        {/* ── Sowing recommendation ────────────────────────────────── */}
        <section style={S.panel}>
          <h2 style={S.h2}>
            Sowing Recommendation <span style={S.h2hi}>बुआई सलाह</span>
          </h2>

          {advisoryLoading && <Loading />}
          {!advisoryLoading && advisoryError && <ErrorBox onRetry={loadAdvisory} />}

          {!advisoryLoading && !advisoryError && advisory && (
            <>
              <div style={S.cropLabel}>
                Paddy sowing advice <span style={S.hiText}>धान बुआई सलाह</span>
              </div>
              {advisory.current_season === false ? (
                <>
                  <div style={{ ...S.statusBadge, background: PAST_STATUS_COLOR }}>
                    Kharif {advisory.season} result: {STATUS_LABEL[advisory.status].en}
                    {" · "}खरीफ {advisory.season} परिणाम: {STATUS_LABEL[advisory.status].hi}
                  </div>
                  <div style={S.warnNote}>
                    Not the current season — for reference only
                    <br />
                    <span style={S.hiText}>यह मौजूदा सीज़न नहीं है — केवल संदर्भ के लिए</span>
                  </div>
                </>
              ) : (
                <div style={{ ...S.statusBadge, background: STATUS_COLOR[advisory.status] }}>
                  {STATUS_LABEL[advisory.status].en} · {STATUS_LABEL[advisory.status].hi}
                </div>
              )}
              <p style={S.reasonEn}>{advisory.reasoning.en}</p>
              <p style={S.reasonHi}>{advisory.reasoning.hi}</p>
              {advisory.alternative_crop && (
                <div style={S.meta}>
                  Alternative crop: <strong>{advisory.alternative_crop.en}</strong> / {advisory.alternative_crop.hi}
                </div>
              )}
              {/* "Reassess in N days" is an instruction for now — not for a past season. */}
              {advisory.wait_window_days != null && advisory.current_season !== false && (
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

        {mandiLoading && <Loading />}
        {!mandiLoading && mandiError && <ErrorBox onRetry={loadMandi} />}

        {!mandiLoading && !mandiError && mandi && (
          <>
            <SourceNote status={dataStatus?.mandi} kind="mandi" />
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
                    <td style={{ ...S.tdNum, color: best ? TREND_COLOR[best.trend] : "var(--muted)" }}>
                      {best ? TREND_MARK[best.trend] : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <DataDate status={dataStatus?.mandi} />
          </>
        )}
      </section>
    </div>
  );
}

// Same palette as the farmer app: CSS variables from index.css (with dark mode).
const ink = "var(--ink)", line = "var(--line)", panelBg = "var(--surface)", pageBg = "var(--bg)";
const css = `
  .sd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  @media (max-width: 760px) { .sd-grid { grid-template-columns: 1fr; } }
  .sd-mandi-table tbody tr:nth-child(even) { background: var(--bg); }
  .sd-mandi-table tbody tr:hover { background: var(--chip); }
`;

const S = {
  page: {
    fontFamily: "var(--font)",
    background: pageBg,
    color: ink,
    minHeight: "100vh",
    padding: "16px 14px 40px",
    maxWidth: 1080,
    margin: "0 auto",
    lineHeight: 1.45,
    fontSize: 14,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
    background: "var(--primary)",
    color: "var(--on-primary)",
    borderRadius: 12,
    borderBottom: "4px solid var(--accent)",
    padding: "12px 16px",
    marginBottom: 14,
  },
  h1: { fontSize: 19, fontWeight: 700, margin: 0, lineHeight: 1.3 },
  h1hi: { fontSize: 15, fontWeight: 400, marginLeft: 6 },
  sub: { fontSize: 13, marginTop: 3, fontWeight: 400 },
  hiText: { color: "var(--muted)", fontWeight: 400 },
  refreshBtn: {
    minHeight: 48,
    background: "transparent",
    color: "inherit",
    border: "2px solid currentColor",
    borderRadius: 10,
    padding: "0 14px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  panel: {
    background: panelBg,
    border: `1px solid ${line}`,
    borderRadius: 16,
    padding: "12px 14px",
  },
  panelWide: {
    background: panelBg,
    border: `1px solid ${line}`,
    borderRadius: 16,
    padding: "12px 14px",
  },
  h2: {
    fontSize: 16,
    fontWeight: 700,
    margin: "0 0 10px",
    paddingBottom: 8,
    borderBottom: "2px solid var(--accent)",
    color: "var(--primary)",
  },
  h2hi: { fontSize: 13, fontWeight: 400, color: "var(--muted)", marginLeft: 4 },
  loading: { fontSize: 13, color: "var(--muted)", fontWeight: 700, margin: "6px 0" },
  errBox: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "var(--surface)", border: "2px solid var(--bad)", borderRadius: 8, padding: "8px 10px", fontSize: 13, color: "var(--bad)", fontWeight: 700 },
  retryBtn: { minHeight: 48, background: "var(--primary)", color: "var(--on-primary)", border: "none", borderRadius: 10, padding: "0 14px", fontSize: 13, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" },
  warnNote: { fontSize: 13, fontWeight: 700, background: "var(--note-bg)", border: "1px solid var(--note-line)", borderRadius: 8, padding: "8px 10px", marginBottom: 10, color: "var(--note-ink)", lineHeight: 1.45 },
  kvTable: { width: "100%", borderCollapse: "collapse" },
  kCell: { fontSize: 13, color: "var(--muted)", fontWeight: 700, padding: "6px 8px 6px 0", borderBottom: `1px dashed ${line}`, whiteSpace: "nowrap", verticalAlign: "top" },
  vCell: { fontSize: 13, fontWeight: 700, padding: "6px 0", borderBottom: `1px dashed ${line}`, textAlign: "right" },
  vCellNum: { fontSize: 13, fontWeight: 800, padding: "6px 0", borderBottom: `1px dashed ${line}`, textAlign: "right", fontVariantNumeric: "tabular-nums" },
  dim: { fontSize: 12, fontWeight: 400, color: "var(--muted)" },
  badge: { display: "inline-block", color: "#fff", fontSize: 11, fontWeight: 800, padding: "3px 8px", borderRadius: 4 },
  footnote: { fontSize: 12, color: "var(--muted)", marginTop: 8, textAlign: "right" },
  cropLabel: { fontSize: 13, fontWeight: 700, color: "var(--muted)", marginBottom: 6 },
  statusBadge: { display: "inline-block", color: "#fff", fontSize: 13, fontWeight: 900, padding: "5px 12px", borderRadius: 5, marginBottom: 10, letterSpacing: "0.5px" },
  reasonEn: { fontSize: 14, lineHeight: 1.5, margin: "0 0 6px", color: "var(--ink)" },
  reasonHi: { fontSize: 14, lineHeight: 1.65, margin: "0 0 8px", color: "var(--muted)" },
  meta: { fontSize: 13, color: "var(--ink)", background: "var(--chip)", borderLeft: "3px solid var(--primary)", padding: "5px 8px", borderRadius: 4, marginTop: 6 },
  mandiTable: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: { textAlign: "left", fontSize: 13, fontWeight: 700, color: "var(--muted)", padding: "6px 8px", borderBottom: `2px solid ${ink}` },
  thNum: { textAlign: "right", fontSize: 13, fontWeight: 700, color: "var(--muted)", padding: "6px 8px", borderBottom: `2px solid ${ink}` },
  td: { padding: "7px 8px", borderBottom: `1px solid ${line}`, fontWeight: 600 },
  tdNum: { padding: "7px 8px", borderBottom: `1px solid ${line}`, fontWeight: 800, textAlign: "right", fontVariantNumeric: "tabular-nums" },
};
