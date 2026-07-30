const state = {
  view: "overview",
  overview: null,
  records: [],
  anomalies: [],
  quality: null,
  lineage: null,
  audit: null,
};

const content = document.querySelector("#content");
const drawer = document.querySelector("#detailDrawer");
const backdrop = document.querySelector("#drawerBackdrop");
const toast = document.querySelector("#toast");

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const money = (value, compact = false) => new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: compact ? 0 : 2,
  notation: compact ? "compact" : "standard",
}).format(value);

const number = (value) => new Intl.NumberFormat("en-GB").format(value);
const percent = (value) => `${Number(value).toFixed(1)}%`;
const shortHash = (value) => `${String(value).slice(0, 10)}…${String(value).slice(-5)}`;

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { Accept: "application/json", ...options.headers }, ...options });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function notify(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function pageHeading(eyebrow, title, subtitle, actions = "") {
  return `
    <div class="page-heading">
      <div><p class="eyebrow">${escapeHtml(eyebrow)}</p><h1>${escapeHtml(title)}</h1><p class="subtitle">${escapeHtml(subtitle)}</p></div>
      <div class="heading-actions">${actions}</div>
    </div>`;
}

function badge(label, tone = "") {
  return `<span class="badge ${tone}">${escapeHtml(label)}</span>`;
}

function kpiCard(label, value, unit, meta, tone = "", metaTone = "") {
  return `<article class="card kpi-card ${tone}">
    <div class="kpi-label"><span>${escapeHtml(label)}</span><span class="info-dot">i</span></div>
    <div class="kpi-value">${escapeHtml(value)}${unit ? `<small>${escapeHtml(unit)}</small>` : ""}</div>
    <div class="kpi-meta ${metaTone}">${escapeHtml(meta)}</div>
  </article>`;
}

function trendChart(series) {
  if (!series.length) return '<div class="empty-state">No time-series data.</div>';
  const width = 820;
  const height = 220;
  const pad = { top: 24, right: 18, bottom: 34, left: 56 };
  const max = Math.max(...series.map((item) => item.net_revenue_eur)) * 1.08;
  const min = Math.min(...series.map((item) => item.net_revenue_eur)) * 0.8;
  const x = (index) => pad.left + (index / Math.max(series.length - 1, 1)) * (width - pad.left - pad.right);
  const y = (value) => pad.top + ((max - value) / Math.max(max - min, 1)) * (height - pad.top - pad.bottom);
  const path = series.map((item, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(item.net_revenue_eur).toFixed(1)}`).join(" ");
  const area = `${path} L${x(series.length - 1)},${height - pad.bottom} L${x(0)},${height - pad.bottom} Z`;
  const grid = [0, 1, 2, 3].map((index) => {
    const gy = pad.top + index * ((height - pad.top - pad.bottom) / 3);
    const value = max - index * ((max - min) / 3);
    return `<line class="chart-grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${gy}" y2="${gy}"/><text class="chart-label" x="4" y="${gy + 4}">${money(value, true)}</text>`;
  }).join("");
  const points = series.map((item, index) => `<circle class="chart-point" cx="${x(index)}" cy="${y(item.net_revenue_eur)}" r="4"><title>${item.date}: ${money(item.net_revenue_eur)}</title></circle>`).join("");
  const labels = series.map((item, index) => index % Math.max(Math.ceil(series.length / 6), 1) === 0
    ? `<text class="chart-label" x="${x(index)}" y="${height - 7}" text-anchor="middle">${escapeHtml(item.date.slice(5))}</text>` : "").join("");
  return `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Net revenue trend">
    <defs><linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f8b83" stop-opacity=".22"/><stop offset="1" stop-color="#0f8b83" stop-opacity="0"/></linearGradient></defs>
    ${grid}<path class="chart-area" d="${area}"/><path class="chart-line" d="${path}"/>${points}${labels}
  </svg>`;
}

function sourceRows(items) {
  return items.map((source) => `<div class="source-row">
    <div class="source-icon">${source.source_type === "excel" ? "XL" : source.source_type === "api" ? "API" : "SQL"}</div>
    <div><strong>${escapeHtml(source.name)}</strong><span>${source.freshness} freshness · ${source.quality_issues} quality exception(s)</span></div>
    <span class="source-metric">${number(source.normalized_rows)}<small>rows</small></span>
  </div>`).join("");
}

function anomalyRows(items) {
  if (!items.length) return '<tr><td colspan="6" class="empty-state">No findings match this filter.</td></tr>';
  return items.map((item) => `<tr class="clickable anomaly-row" data-anomaly="${escapeHtml(item.anomaly_id)}">
    <td><span class="risk-score ${item.severity}">${item.risk_score}</span></td>
    <td><strong class="cell-main">${escapeHtml(item.title)}</strong><span class="cell-sub">${escapeHtml(item.anomaly_type.replaceAll("_", " "))}</span></td>
    <td><strong>${escapeHtml(item.order_id)}</strong></td>
    <td>${badge(item.severity, item.severity === "critical" ? "danger" : item.severity === "high" ? "warning" : "teal")}</td>
    <td><span class="cell-main">${escapeHtml(item.model_version)}</span><span class="cell-sub">Explainable hybrid</span></td>
    <td><button class="button small">Review →</button></td>
  </tr>`).join("");
}

function overviewView() {
  const { kpis, source_stats: sources, anomalies, recent_audit: audit, metadata } = state.overview;
  return `
    ${pageHeading("Revenue data reliability", "Trust every number before it reaches the board", `Run ${metadata.run_id} reconciles heterogeneous Excel, API and SQL sources through one auditable control plane.`, `
      ${badge("SYNTHETIC DATA", "teal")}
      <button class="button primary" id="runPipeline">↻ Run pipeline</button>`)}
    <div class="kpi-grid">
      ${kpiCard("Controlled net revenue", money(kpis.net_revenue_eur, true), "EUR", `${number(kpis.canonical_records)} canonical revenue events`)}
      ${kpiCard("Data trust score", kpis.data_quality_score, "/100", `${percent(kpis.quality_pass_rate)} records passed`, kpis.data_quality_score < 90 ? "warning" : "", kpis.data_quality_score < 90 ? "warning" : "")}
      ${kpiCard("Duplicate leakage prevented", money(kpis.net_revenue_eur * kpis.duplicate_rate / 100, true), "EUR", `${kpis.duplicates_removed} overlapping records resolved`)}
      ${kpiCard("Findings requiring review", kpis.anomaly_count, "findings", `${kpis.critical_findings} critical · human approval required`, kpis.critical_findings ? "danger" : "", kpis.critical_findings ? "danger" : "")}
    </div>
    <div class="dashboard-grid">
      <div class="dashboard-stack">
        <section class="card panel">
          <div class="panel-header"><div><h2 class="panel-title">Controlled revenue trend</h2><p class="panel-subtitle">Normalized to EUR using the deterministic demo rate table</p></div>${badge("Lineage complete", "success")}</div>
          <div class="panel-body chart-wrap">${trendChart(kpis.time_series)}</div>
        </section>
        <section class="card panel">
          <div class="panel-header"><div><h2 class="panel-title">Priority review queue</h2><p class="panel-subtitle">Explainable findings ranked by impact and confidence</p></div><button class="button small" data-go="anomalies">Open anomaly lab →</button></div>
          <div class="table-scroll"><table><thead><tr><th>Risk</th><th>Finding</th><th>Order</th><th>Severity</th><th>Model</th><th></th></tr></thead><tbody>${anomalyRows(anomalies)}</tbody></table></div>
        </section>
      </div>
      <div class="dashboard-stack">
        <section class="card panel">
          <div class="panel-header"><div><h2 class="panel-title">Source health</h2><p class="panel-subtitle">Freshness, volume and contract status</p></div>${badge("3 connected", "success")}</div>
          <div class="panel-body source-list">${sourceRows(sources)}</div>
        </section>
        <section class="card panel">
          <div class="panel-header"><div><h2 class="panel-title">Control coverage</h2><p class="panel-subtitle">Deterministic validation gates</p></div>${badge(`${kpis.controls_passed}/${kpis.controls_total} passed`, kpis.controls_passed === kpis.controls_total ? "success" : "warning")}</div>
          <div class="panel-body">
            <div class="quality-ring" style="--score:${kpis.data_quality_score}"><div><strong>${kpis.data_quality_score}</strong><span>TRUST SCORE</span></div></div>
            <div class="control-progress"><span style="width:${(kpis.controls_passed / kpis.controls_total) * 100}%"></span></div>
            <div class="control-labels"><span>Schema · arithmetic · freshness</span><strong>${kpis.quality_issue_count} exceptions</strong></div>
          </div>
        </section>
        <section class="card panel">
          <div class="panel-header"><div><h2 class="panel-title">Recent audit events</h2><p class="panel-subtitle">Tamper-evident hash chain</p></div>${badge("Verified", "success")}</div>
          <div class="panel-body source-list">${audit.slice(0, 4).map((item) => `<div class="source-row"><div class="source-icon">${String(item.sequence).padStart(2, "0")}</div><div><strong>${escapeHtml(item.action)}</strong><span>${escapeHtml(item.actor)} · ${escapeHtml(item.object_ref)}</span></div><span class="hash">${shortHash(item.entry_hash)}</span></div>`).join("")}</div>
        </section>
      </div>
    </div>`;
}

function sourcesView() {
  const sources = state.overview.source_stats;
  const kpis = state.overview.kpis;
  return `
    ${pageHeading("Multi-source ingestion", "One contract across fragmented operational data", "Two differently structured Excel workbooks, a CRM JSON API and an ERP SQLite ledger converge into a governed revenue model.", `<a class="button" href="/api/source/crm" target="_blank" rel="noreferrer">Inspect API fixture</a><button class="button primary" id="runPipeline">↻ Refresh sources</button>`)}
    <div class="source-grid">${sources.map((source) => `<article class="card feature-card">
      <div class="feature-head"><div class="feature-icon">${source.source_type === "excel" ? "XL" : source.source_type === "api" ? "{}" : "DB"}</div>${badge(source.status, source.status === "healthy" ? "success" : "warning")}</div>
      <h3>${escapeHtml(source.name)}</h3><p>${source.source_type === "excel" ? "Header aliasing, date coercion and workbook-level lineage." : source.source_type === "api" ? "Contract-limited JSON ingestion with size, media-type and timeout controls." : "Read-only parameter-free query against the operational ledger."}</p>
      <div class="feature-stats"><span>INGESTED<strong>${number(source.raw_rows)}</strong></span><span>NORMALIZED<strong>${number(source.normalized_rows)}</strong></span><span>FRESHNESS<strong>${source.freshness}</strong></span></div>
    </article>`).join("")}</div>
    <div class="metric-strip"><div><span>Raw records</span><strong>${kpis.raw_records}</strong></div><div><span>Canonical records</span><strong>${kpis.canonical_records}</strong></div><div><span>Duplicates removed</span><strong>${kpis.duplicates_removed}</strong></div><div><span>Duplicate rate</span><strong>${percent(kpis.duplicate_rate)}</strong></div></div>
    <section class="card panel">
      <div class="panel-header"><div><h2 class="panel-title">Canonical revenue events</h2><p class="panel-subtitle">Searchable normalized output with per-record lineage</p></div>${badge("PII minimized", "teal")}</div>
      <div class="table-toolbar"><span class="badge">${state.records.length} events</span><span class="badge success">EUR normalized</span></div>
      <div class="table-scroll"><table><thead><tr><th>Order / account</th><th>Date</th><th>Region</th><th>Product</th><th>Net revenue</th><th>Margin</th><th>Quality</th><th>Source</th></tr></thead><tbody id="recordRows">${recordRows(state.records)}</tbody></table></div>
    </section>`;
}

function recordRows(records) {
  if (!records.length) return '<tr><td colspan="8" class="empty-state">No records match your search.</td></tr>';
  return records.map((record) => `<tr class="clickable record-row" data-record="${escapeHtml(record.record_id)}">
    <td><strong class="cell-main">${escapeHtml(record.order_id)}</strong><span class="cell-sub">${escapeHtml(record.customer_label)}</span></td>
    <td>${escapeHtml(record.transaction_date)}</td><td>${escapeHtml(record.region)} · ${escapeHtml(record.country)}</td><td>${escapeHtml(record.product_family)}<span class="cell-sub">${escapeHtml(record.channel)}</span></td>
    <td><strong>${money(record.net_eur)}</strong><span class="cell-sub">${escapeHtml(record.currency)} source</span></td><td>${money(record.margin_eur)}</td>
    <td>${badge(`${record.quality_score}/100`, record.quality_score >= 95 ? "success" : "warning")}</td><td>${badge(record.source_type.toUpperCase(), "teal")}</td>
  </tr>`).join("");
}

function qualityView() {
  const { summary, rules, issues } = state.quality;
  const issueRules = new Set(issues.map((item) => item.rule_id));
  return `
    ${pageHeading("Automated controls", "Data quality is a release gate, not a chart decoration", "Every canonical event is checked against versioned schema, financial arithmetic, domain and temporal rules before it reaches reporting.", `<button class="button primary" data-go="audit">View signed audit trail →</button>`)}
    <div class="metric-strip"><div><span>Quality score</span><strong>${summary.score}/100</strong></div><div><span>Record pass rate</span><strong>${percent(summary.pass_rate)}</strong></div><div><span>Passed records</span><strong>${summary.records_passed}</strong></div><div><span>Open exceptions</span><strong>${summary.issue_count}</strong></div></div>
    <div class="rule-grid">${rules.map((rule) => `<article class="card rule-card"><div class="rule-check ${issueRules.has(rule.id) ? "fail" : ""}">${issueRules.has(rule.id) ? "!" : "✓"}</div><div><h3>${escapeHtml(rule.name)}</h3><p>${escapeHtml(rule.id)} · ${escapeHtml(rule.severity)} severity</p></div>${badge(issueRules.has(rule.id) ? `${issues.filter((item) => item.rule_id === rule.id).length} exceptions` : "passing", issueRules.has(rule.id) ? "warning" : "success")}</article>`).join("")}</div>
    <section class="card panel"><div class="panel-header"><div><h2 class="panel-title">Exception register</h2><p class="panel-subtitle">Observed values are retained for review; source values are never silently corrected</p></div>${badge("Human review", "warning")}</div>
      <div class="table-scroll"><table><thead><tr><th>Issue</th><th>Rule</th><th>Field</th><th>Severity</th><th>Explanation</th><th>Observed</th></tr></thead><tbody>${issues.length ? issues.map((item) => `<tr><td><strong>${escapeHtml(item.issue_id)}</strong><span class="cell-sub">${escapeHtml(item.record_id)}</span></td><td>${escapeHtml(item.rule_id)}</td><td>${escapeHtml(item.field)}</td><td>${badge(item.severity, item.severity === "critical" ? "danger" : "warning")}</td><td>${escapeHtml(item.message)}</td><td class="hash">${escapeHtml(JSON.stringify(item.observed))}</td></tr>`).join("") : '<tr><td colspan="6" class="empty-state">All records passed.</td></tr>'}</tbody></table></div>
    </section>`;
}

function anomaliesView() {
  return `
    ${pageHeading("Explainable anomaly intelligence", "Review the evidence, not a black-box label", "The offline detector combines robust statistics, margin and discount policy thresholds, plus data-quality confidence. It recommends action but never posts transactions.", `${badge("robust-rules-v1.0", "teal")}<button class="button" data-go="lineage">Inspect lineage →</button>`)}
    <div class="table-toolbar card" style="margin-bottom:14px"><div class="segmented" id="anomalyFilters"><button class="segment active" data-filter="all">All</button><button class="segment" data-filter="critical">Critical</button><button class="segment" data-filter="high">High</button><button class="segment" data-filter="medium">Medium</button></div><span class="badge">${state.anomalies.length} findings</span></div>
    <div class="anomaly-list" id="anomalyCards">${anomalyCards(state.anomalies)}</div>`;
}

function anomalyCards(items) {
  if (!items.length) return '<div class="card empty-state">No findings match this severity.</div>';
  return items.map((item) => `<article class="anomaly-card" data-anomaly="${escapeHtml(item.anomaly_id)}">
    <span class="risk-score ${item.severity}">${item.risk_score}</span>
    <div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.explanation)}</p><div class="anomaly-meta">${badge(item.severity, item.severity === "critical" ? "danger" : item.severity === "high" ? "warning" : "teal")}${badge(item.order_id)}${badge(item.anomaly_type.replaceAll("_", " "))}</div></div>
    <button class="button small">Open evidence →</button>
  </article>`).join("");
}

function lineageView() {
  return `
    ${pageHeading("End-to-end lineage", "Trace a board-level KPI back to its source row", "Each canonical event carries a stable lineage hash; every pipeline stage emits a chained audit event.", `${badge(`${state.lineage.records.length} traceable records`, "success")}`)}
    <section class="card lineage-canvas">
      <div class="lineage-flow">
        <div class="lineage-column">
          <div class="lineage-node"><div class="feature-icon">XL</div><div><strong>Excel workbooks</strong><span>2 schemas · cell-level source refs</span></div></div>
          <div class="lineage-node"><div class="feature-icon">API</div><div><strong>CRM REST API</strong><span>JSON contract · payload limits</span></div></div>
          <div class="lineage-node"><div class="feature-icon">DB</div><div><strong>ERP SQL ledger</strong><span>Read-only deterministic query</span></div></div>
        </div>
        <div class="lineage-arrow">→</div>
        <div class="lineage-column"><div class="lineage-node process"><div class="feature-icon">01</div><div><strong>Canonical mapping</strong><span>Aliases · dates · FX · statuses</span></div></div><div class="lineage-node process"><div class="feature-icon">02</div><div><strong>Contract controls</strong><span>6 versioned validation rules</span></div></div></div>
        <div class="lineage-arrow">→</div>
        <div class="lineage-column"><div class="lineage-node process"><div class="feature-icon">03</div><div><strong>Identity resolution</strong><span>Stable deterministic fingerprints</span></div></div><div class="lineage-node process"><div class="feature-icon">04</div><div><strong>Anomaly scoring</strong><span>MAD baseline + policy evidence</span></div></div></div>
        <div class="lineage-arrow">→</div>
        <div class="lineage-column"><div class="lineage-node target"><div class="feature-icon">WH</div><div><strong>Revenue warehouse</strong><span>SQLite facts · governed view</span></div></div><div class="lineage-node target"><div class="feature-icon">BI</div><div><strong>Power BI model</strong><span>CSV/API · DAX starter pack</span></div></div></div>
      </div>
      <div class="lineage-note">Select any revenue event in Data sources to inspect its exact source reference, transformation hash, quality result and related anomaly evidence.</div>
    </section>`;
}

function auditView() {
  return `
    ${pageHeading("Tamper-evident audit ledger", "Every material pipeline action leaves verifiable evidence", "The demo uses a SHA-256-linked event chain. Modifying or reordering any event causes verification to fail.", `<a class="button" href="/api/audit" target="_blank" rel="noreferrer">Open audit API</a>`)}
    <div class="audit-status"><div class="seal">✓</div><div><h3>${state.audit.verified ? "Integrity chain verified" : "Integrity verification failed"}</h3><p>${state.audit.items.length} ordered events · genesis to current snapshot · independently recomputed by the API</p></div></div>
    <section class="card panel"><div class="panel-header"><div><h2 class="panel-title">Event chain</h2><p class="panel-subtitle">Payload content is summarized as a digest to minimize sensitive data exposure</p></div>${badge("SHA-256", "teal")}</div>
      <div class="table-scroll"><table><thead><tr><th>Seq.</th><th>Timestamp</th><th>Actor</th><th>Action</th><th>Object</th><th>Previous hash</th><th>Entry hash</th></tr></thead><tbody>${state.audit.items.map((item) => `<tr><td><strong>${String(item.sequence).padStart(2, "0")}</strong></td><td>${escapeHtml(item.timestamp)}</td><td>${escapeHtml(item.actor)}</td><td><strong>${escapeHtml(item.action)}</strong></td><td>${escapeHtml(item.object_ref)}</td><td class="hash" title="${escapeHtml(item.previous_hash)}">${shortHash(item.previous_hash)}</td><td class="hash" title="${escapeHtml(item.entry_hash)}">${shortHash(item.entry_hash)}</td></tr>`).join("")}</tbody></table></div>
    </section>`;
}

function powerBiView() {
  return `
    ${pageHeading("Power BI enablement kit", "A governed semantic layer, ready for visual analytics", "Use the pre-shaped fact export, reproducible Power Query and documented DAX measures. The browser dashboard remains the source-code demo; Power BI is an optional consumer.", `<a class="button primary" href="/api/powerbi/export.csv" download>↓ Download governed facts</a>`)}
    <div class="integration-grid">
      <article class="card integration-card"><div class="feature-icon">API</div><h3>Refreshable API</h3><p>Connect Power Query to the same controlled dataset exposed by the local dashboard API.</p>${badge("Same-origin demo", "success")}</article>
      <article class="card integration-card"><div class="feature-icon">DAX</div><h3>Measure library</h3><p>Revenue, margin, quality, anomaly and duplicate-prevention measures with explicit definitions.</p>${badge("Git-friendly", "teal")}</article>
      <article class="card integration-card"><div class="feature-icon">TMD</div><h3>Semantic contract</h3><p>Canonical field names, grain, units, lineage and decision boundaries documented for reviewers.</p>${badge("Version 1.0", "teal")}</article>
    </div>
    <section class="card panel"><div class="panel-header"><div><h2 class="panel-title">Power Query endpoint</h2><p class="panel-subtitle">The CSV endpoint is generated from the same in-memory snapshot used by this interface</p></div>${badge("No hidden workbook links", "success")}</div><div class="panel-body"><div class="code-block">let<br>&nbsp;&nbsp;Source = Csv.Document(Web.Contents("http://127.0.0.1:8787/api/powerbi/export.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),<br>&nbsp;&nbsp;Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])<br>in<br>&nbsp;&nbsp;Promoted</div></div></section>`;
}

const renderers = { overview: overviewView, sources: sourcesView, quality: qualityView, anomalies: anomaliesView, lineage: lineageView, audit: auditView, powerbi: powerBiView };

async function ensureData(view) {
  if (!state.overview) state.overview = await api("/api/overview");
  if (view === "sources" && !state.records.length) state.records = (await api("/api/records")).items;
  if (view === "quality" && !state.quality) state.quality = await api("/api/quality");
  if (view === "anomalies" && !state.anomalies.length) state.anomalies = (await api("/api/anomalies")).items;
  if (view === "lineage" && !state.lineage) state.lineage = await api("/api/lineage");
  if (view === "audit" && !state.audit) state.audit = await api("/api/audit");
}

async function render(view = state.view) {
  state.view = view;
  content.innerHTML = '<div class="loading-state"><span class="loader"></span><p>Loading governed data…</p></div>';
  try {
    await ensureData(view);
    content.innerHTML = renderers[view]();
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
    wireContentEvents();
  } catch (error) {
    content.innerHTML = `<div class="card empty-state"><h2>Unable to load the demo snapshot</h2><p>${escapeHtml(error.message)}</p><button class="button primary" id="retryButton">Retry</button></div>`;
    document.querySelector("#retryButton")?.addEventListener("click", () => render(view));
  }
}

function wireContentEvents() {
  document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => render(button.dataset.go)));
  document.querySelector("#runPipeline")?.addEventListener("click", runPipeline);
  document.querySelectorAll(".record-row").forEach((row) => row.addEventListener("click", () => openRecord(row.dataset.record)));
  document.querySelectorAll("[data-anomaly]").forEach((row) => row.addEventListener("click", () => openAnomaly(row.dataset.anomaly)));
  document.querySelectorAll("#anomalyFilters .segment").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("#anomalyFilters .segment").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    const items = button.dataset.filter === "all" ? state.anomalies : state.anomalies.filter((item) => item.severity === button.dataset.filter);
    document.querySelector("#anomalyCards").innerHTML = anomalyCards(items);
    document.querySelectorAll("#anomalyCards [data-anomaly]").forEach((row) => row.addEventListener("click", () => openAnomaly(row.dataset.anomaly)));
  }));
}

async function runPipeline() {
  const button = document.querySelector("#runPipeline");
  if (button) { button.disabled = true; button.textContent = "Running controls…"; }
  try {
    const result = await api("/api/runs", { method: "POST", headers: { "X-Demo-Role": "analyst", "Content-Type": "application/json" }, body: "{}" });
    Object.assign(state, { overview: null, records: [], anomalies: [], quality: null, lineage: null, audit: null });
    notify(`Pipeline ${result.run_id} completed and reconciled.`);
    await render(state.view);
  } catch (error) {
    notify(error.message);
    if (button) { button.disabled = false; button.textContent = "↻ Run pipeline"; }
  }
}

async function openRecord(recordId) {
  const detail = await api(`/api/records/${encodeURIComponent(recordId)}`);
  const record = detail.record;
  showDrawer(`
    <div class="drawer-header"><button class="drawer-close" aria-label="Close">×</button><p class="eyebrow">Canonical revenue event</p><h2>${escapeHtml(record.order_id)}</h2><p>${escapeHtml(record.customer_label)} · ${escapeHtml(record.region)}</p></div>
    <div class="drawer-body">
      <div class="detail-section"><h3>Financial view</h3><div class="detail-grid">
        ${detailCell("Net revenue", money(record.net_eur))}${detailCell("Margin", money(record.margin_eur))}${detailCell("Gross source", `${record.gross_amount.toLocaleString()} ${record.currency}`)}${detailCell("Status", record.status)}
      </div></div>
      <div class="detail-section"><h3>Source and lineage</h3><div class="detail-grid">
        ${detailCell("Connector", record.source_type.toUpperCase())}${detailCell("Source reference", record.source_ref)}${detailCell("Lineage hash", record.lineage_hash)}${detailCell("Quality score", `${record.quality_score}/100`)}
      </div></div>
      <div class="detail-section"><h3>Quality and risk</h3>${detail.quality_issues.length ? `<ul class="evidence-list">${detail.quality_issues.map((item) => `<li>${escapeHtml(item.rule_id)} · ${escapeHtml(item.message)}</li>`).join("")}</ul>` : `<p>${badge("All contract checks passed", "success")}</p>`}${detail.anomalies.length ? `<ul class="evidence-list">${detail.anomalies.flatMap((item) => item.evidence).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</div>
      <p class="subtitle">Decision boundary: evidence supports a human reviewer. The demo never approves, posts or moves funds.</p>
    </div>`);
}

function openAnomaly(anomalyId) {
  const item = (state.anomalies.length ? state.anomalies : state.overview.anomalies).find((entry) => entry.anomaly_id === anomalyId);
  if (!item) return;
  showDrawer(`
    <div class="drawer-header"><button class="drawer-close" aria-label="Close">×</button><p class="eyebrow">Explainable finding · ${escapeHtml(item.severity)}</p><h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.order_id)} · risk score ${item.risk_score}/100</p></div>
    <div class="drawer-body">
      <div class="detail-section"><h3>Why it was flagged</h3><p class="subtitle">${escapeHtml(item.explanation)}</p><ul class="evidence-list">${item.evidence.map((evidence) => `<li>${escapeHtml(evidence)}</li>`).join("")}</ul></div>
      <div class="detail-section"><h3>Model controls</h3><div class="detail-grid">${detailCell("Model", item.model_version)}${detailCell("Finding type", item.anomaly_type)}${detailCell("Risk score", `${item.risk_score}/100`)}${detailCell("Decision", "Human review")}</div></div>
      <div class="detail-section"><h3>Recommended action</h3><div class="code-block">${escapeHtml(item.recommended_action)}</div></div>
      <button class="button primary" data-close-drawer>Mark as reviewed in demo</button>
    </div>`);
}

function detailCell(label, value) {
  return `<div class="detail-cell"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function showDrawer(markup) {
  drawer.innerHTML = markup;
  backdrop.hidden = false;
  drawer.setAttribute("aria-hidden", "false");
  requestAnimationFrame(() => drawer.classList.add("open"));
  drawer.querySelector(".drawer-close")?.addEventListener("click", closeDrawer);
  drawer.querySelector("[data-close-drawer]")?.addEventListener("click", () => { closeDrawer(); notify("Review acknowledgement recorded locally for this demo session."); });
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  window.setTimeout(() => { backdrop.hidden = true; drawer.innerHTML = ""; }, 230);
}

document.querySelector("#primaryNav").addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (button) render(button.dataset.view);
});
backdrop.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeDrawer();
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault(); document.querySelector("#globalSearch").focus();
  }
});
document.querySelector("#globalSearch").addEventListener("input", async (event) => {
  if (state.view !== "sources") await render("sources");
  const search = event.target.value.trim().toLowerCase();
  const filtered = state.records.filter((record) => !search || [record.order_id, record.customer_label, record.region, record.country, record.product_family].join(" ").toLowerCase().includes(search));
  const rows = document.querySelector("#recordRows");
  if (rows) { rows.innerHTML = recordRows(filtered); document.querySelectorAll(".record-row").forEach((row) => row.addEventListener("click", () => openRecord(row.dataset.record))); }
});
document.querySelector("#helpButton").addEventListener("click", () => {
  showDrawer(`<div class="drawer-header"><button class="drawer-close" aria-label="Close">×</button><p class="eyebrow">Demo boundary</p><h2>What this project proves</h2><p>A portfolio-grade, locally runnable data control plane.</p></div><div class="drawer-body"><div class="detail-section"><h3>Included</h3><ul class="evidence-list"><li>Real Excel, HTTP JSON and SQLite connectors</li><li>Canonical mapping, quality gates and deterministic deduplication</li><li>Explainable anomaly scoring with human review</li><li>Traceable lineage, hash-chained audit and Power BI export</li></ul></div><div class="detail-section"><h3>Not included</h3><p class="subtitle">No production credentials, customer data, cloud infrastructure or autonomous financial decisions. Every entity and amount is synthetic.</p></div></div>`);
});

Promise.all([api("/api/audit"), api("/api/anomalies")]).then(([audit, anomalies]) => {
  document.querySelector("#sidebarAudit").textContent = audit.verified ? "Verified" : "Failed";
  document.querySelector("#navAnomalyCount").textContent = anomalies.total;
  state.audit = audit;
  state.anomalies = anomalies.items;
}).catch(() => { document.querySelector("#sidebarAudit").textContent = "Unavailable"; });

render();

