/* overview.js — Dashboard Overview: range-filtered KPIs, trend/donut charts,
   platform table, recent incidents. Current-status counts stay live;
   trend/incidents respect the selected range. */

const CHART_COLORS = {
  healthy: "#047857", degraded: "#b45309", down: "#ba1a1a", teal: "#00b3a4", plum: "#400938",
};

let trendChartInstance = null;
let donutChartInstance = null;
let currentRange = "7d";
let customStart = null;
let customEnd = null;
let allPlatforms = [];

function rangeQuery() {
  const params = new URLSearchParams({ range: currentRange });
  if (currentRange === "custom") {
    if (customStart) params.set("start", customStart);
    if (customEnd) params.set("end", customEnd);
  }
  return params.toString();
}

async function loadDashboard() {
  try {
    const [dash, platforms] = await Promise.all([
      fetch(`/api/dashboard?${rangeQuery()}`).then((r) => r.json()),
      Api.getPlatforms(),
    ]);
    allPlatforms = platforms;
    renderKpis(dash);
    renderTrendChart(dash.trend);
    renderDonutChart(dash.current);
    renderPlatformTable(platforms);
    renderRecentIncidents(dash.recent_incidents);
  } catch (err) {
    showToast(err.message || "Could not load dashboard data.", true);
  }
}

function renderKpis(dash) {
  const c = dash.current;
  const total = c.total || 0;
  document.getElementById("kpiTotal").textContent = total;
  document.getElementById("kpiHealthy").textContent = c.healthy || 0;
  document.getElementById("kpiWarning").textContent = c.warning || 0;
  document.getElementById("kpiCritical").textContent = c.critical || 0;
  const pct = (n) => (total ? Math.round((n / total) * 100) : 0);
  document.getElementById("kpiHealthyPct").textContent = `${pct(c.healthy)}% of fleet`;
  document.getElementById("kpiWarningPct").textContent = `${pct(c.warning)}% of fleet`;
  document.getElementById("kpiCriticalPct").textContent = `${pct(c.critical)}% of fleet`;

  document.getElementById("kpiIncidents").textContent = dash.incidents_in_range;
  document.getElementById("kpiIncidentsSub").textContent = rangeLabel();
  document.getElementById("kpiCriticalIncidents").textContent = dash.critical_incidents_in_range;
  document.getElementById("kpiOpenIncidents").textContent = dash.open_incidents_in_range;
  document.getElementById("kpiCamerasPct").textContent = `${dash.cameras_online_pct}%`;
  document.getElementById("kpiLatency").textContent = `${dash.avg_latency_ms} ms`;
}

function rangeLabel() {
  return { today: "Today", "7d": "This week", "30d": "This month", "12m": "This year", all: "All time", custom: "Custom range" }[currentRange] || "";
}

function renderTrendChart(trend) {
  const ctx = document.getElementById("trendChart");
  const existingEmpty = document.getElementById("trendEmpty");
  if (existingEmpty) existingEmpty.remove();
  ctx.style.display = "";
  if (!ctx || typeof Chart === "undefined") return;
  if (!trend.length) {
    ctx.parentElement.insertAdjacentHTML("beforeend", '<div class="empty-state" id="trendEmpty"><span class="material-symbols-outlined">show_chart</span><div>No snapshots in this range yet.</div></div>');
    ctx.style.display = "none";
    return;
  }
  const labels = trend.map((t) => (t.timestamp || `Cycle ${t.cycle}`).toString().slice(0, 16).replace("T", " "));
  const data = {
    labels,
    datasets: [
      { label: "Healthy", data: trend.map((t) => t.healthy || 0), borderColor: CHART_COLORS.healthy, backgroundColor: "rgba(4,120,87,0.12)", tension: 0.35, fill: true },
      { label: "Degraded", data: trend.map((t) => t.warning || 0), borderColor: CHART_COLORS.degraded, backgroundColor: "rgba(180,83,9,0.1)", tension: 0.35, fill: true },
      { label: "Down", data: trend.map((t) => t.critical || 0), borderColor: CHART_COLORS.down, backgroundColor: "rgba(186,26,26,0.1)", tension: 0.35, fill: true },
    ],
  };
  if (trendChartInstance) trendChartInstance.destroy();
  trendChartInstance = new Chart(ctx, {
    type: "line", data,
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 6 } } },
    },
  });
}

function renderDonutChart(current) {
  const ctx = document.getElementById("donutChart");
  if (!ctx || typeof Chart === "undefined") return;
  if (donutChartInstance) donutChartInstance.destroy();
  donutChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Healthy", "Degraded", "Down"],
      datasets: [{ data: [current.healthy || 0, current.warning || 0, current.critical || 0], backgroundColor: [CHART_COLORS.healthy, CHART_COLORS.degraded, CHART_COLORS.down], borderWidth: 0 }],
    },
    options: { responsive: true, cutout: "68%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } } } },
  });
}

function renderPlatformTable(platforms, filterHealth) {
  const body = document.getElementById("platformTableBody");
  const desc = document.getElementById("platformTableDesc");
  let rows = platforms;
  if (filterHealth) {
    rows = platforms.filter((p) => p.health === filterHealth);
    desc.textContent = `Filtered to ${filterHealth} — click the same KPI again to clear`;
  } else {
    desc.textContent = "Live status of every registered platform";
  }
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">No platforms match.</td></tr>';
    return;
  }
  body.innerHTML = rows.slice(0, 8).map((p) => `
    <tr class="row-link" onclick="window.location.href='/platform/${encodeURIComponent(p.id)}'">
      <td class="cell-primary">${escapeHtml(p.project_name)}</td>
      <td>${healthBadge(p.health)}</td>
      <td>${escapeHtml(p.assigned_operator || "—")}</td>
      <td class="cell-muted">${escapeHtml(timeAgoOrValue(p.last_visit))}</td>
      <td><span class="material-symbols-outlined" style="color:var(--c-outline);">chevron_right</span></td>
    </tr>
  `).join("");
}

function renderRecentIncidents(incidents) {
  const wrap = document.getElementById("recentIncidents");
  if (!incidents.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">fact_check</span><div>No incidents in this range.</div></div>';
    return;
  }
  wrap.innerHTML = incidents.map((inc) => `
    <div class="timeline-item">
      <div class="timeline-dot"></div>
      <div class="timeline-body">
        <div class="timeline-title">${escapeHtml(inc.project_name || inc.platform_id)} <span class="chip">${escapeHtml(inc.status || "Open")}</span></div>
        <div class="timeline-meta">${escapeHtml(inc.reported_by || "Reporter")} · ${escapeHtml((inc.timestamp || "").toString().slice(0, 16).replace("T", " "))}</div>
        <div class="timeline-diff">${healthBadgeText(inc.health)} — ${escapeHtml(inc.notes || "No details provided.")}</div>
      </div>
    </div>
  `).join("");
}

function healthBadgeText(h) { return h || "—"; }

let activeKpiFilter = null;
function setupKpiClicks() {
  document.querySelectorAll(".kpi-clickable").forEach((card) => {
    card.addEventListener("click", () => {
      const val = card.dataset.filter;
      activeKpiFilter = activeKpiFilter === val ? null : val;
      document.querySelectorAll(".kpi-clickable").forEach((c) => c.style.outline = "");
      if (activeKpiFilter) card.style.outline = `2px solid var(--c-teal)`;
      renderPlatformTable(allPlatforms, activeKpiFilter);
      document.getElementById("platformTable").scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  });
}

function setupRangeTabs() {
  document.querySelectorAll("#rangeTabs .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#rangeTabs .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      currentRange = tab.dataset.range;
      document.getElementById("customRangeBox").style.display = currentRange === "custom" ? "flex" : "none";
      if (currentRange !== "custom") loadDashboard();
    });
  });
  document.getElementById("applyCustomRange").addEventListener("click", () => {
    customStart = document.getElementById("rangeStart").value || null;
    customEnd = document.getElementById("rangeEnd").value || null;
    if (!customStart) { showToast("Pick a start date.", true); return; }
    loadDashboard();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();
  setupKpiClicks();
  setupRangeTabs();
  const exportBtn = document.getElementById("exportBtn");
  if (exportBtn) exportBtn.addEventListener("click", () => { window.location.href = "/api/export"; });
});
