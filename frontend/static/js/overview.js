/* overview.js, Dashboard Overview: range-filtered KPIs, trend/donut charts,
   platform table, recent incidents. Current-status counts stay live;
   trend and incident counts respect the selected range. */

const CHART_COLORS = {
  healthy: "#047857", degraded: "#b45309", down: "#ba1a1a",
};

const RANGE_LABELS = {
  today: "Today", "7d": "This Week", "30d": "This Month",
  "12m": "This Year", all: "All Time", custom: "This Range",
};

let trendChartInstance = null;
let donutChartInstance = null;
let incidentBarChartInstance = null;
let currentRange = "7d";
let customStart = null;
let customEnd = null;
let allPlatforms = [];
let activeKpiFilter = "";

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
      fetch(`/api/dashboard?${rangeQuery()}`).then((r) => {
        if (!r.ok) throw new Error("Could not load dashboard data.");
        return r.json();
      }),
      Api.getPlatforms(),
    ]);
    allPlatforms = platforms;
    renderKpis(dash);
    renderTrendChart(dash.trend);
    renderDonutChart(dash.current);
    renderIncidentBarChart(dash.incident_daily_counts);
    renderPlatformTable(platforms, activeKpiFilter);
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

  const label = RANGE_LABELS[currentRange] || "This Range";
  document.getElementById("kpiIncidentsLabel").textContent = `Incidents ${label}`;
  document.getElementById("kpiCriticalIncidentsLabel").textContent = `Critical ${label}`;
  document.getElementById("kpiIncidents").textContent = dash.incidents_in_range;
  document.getElementById("kpiCriticalIncidents").textContent = dash.critical_incidents_in_range;
  document.getElementById("kpiOpenIncidents").textContent = dash.open_incidents_total;
  document.getElementById("recentIncidentsDesc").textContent = `Within ${label.toLowerCase()}`;

  // A Custom range with an end date in the past makes "current" mean "as of
  // that date" rather than "right now"; say so, since the number is the
  // same shape either way and the difference isn't otherwise visible.
  const donutDesc = document.getElementById("donutDesc");
  const rangeEnd = dash.range && dash.range.end ? new Date(dash.range.end) : null;
  const isHistorical = currentRange === "custom" && rangeEnd && (Date.now() - rangeEnd.getTime()) > 60000;
  donutDesc.textContent = isHistorical
    ? `Distribution as of ${rangeEnd.toLocaleDateString()}`
    : "Current distribution, live";
}

function renderTrendChart(trend) {
  const frame = document.querySelector(".chart-frame:has(#trendChart)") || document.getElementById("trendChart").parentElement;
  const existingEmpty = document.getElementById("trendEmpty");
  if (existingEmpty) existingEmpty.remove();
  const ctx = document.getElementById("trendChart");
  ctx.style.display = "";

  if (typeof Chart === "undefined") return;

  if (!trend.length) {
    ctx.style.display = "none";
    frame.insertAdjacentHTML("beforeend", '<div class="empty-state" id="trendEmpty"><span class="material-symbols-outlined">show_chart</span><div>No history in this range yet. Log an incident or wait a day for the trend to build up.</div></div>');
    return;
  }

  const labels = trend.map((t) => t.timestamp);
  const data = {
    labels,
    datasets: [
      { label: "Healthy", data: trend.map((t) => t.healthy || 0), borderColor: CHART_COLORS.healthy, backgroundColor: "rgba(4,120,87,0.12)", tension: 0.3, fill: true, pointRadius: trend.length > 1 ? 3 : 5, pointHoverRadius: 6 },
      { label: "Degraded", data: trend.map((t) => t.warning || 0), borderColor: CHART_COLORS.degraded, backgroundColor: "rgba(180,83,9,0.08)", tension: 0.3, fill: true, pointRadius: trend.length > 1 ? 3 : 5, pointHoverRadius: 6 },
      { label: "Down", data: trend.map((t) => t.critical || 0), borderColor: CHART_COLORS.down, backgroundColor: "rgba(186,26,26,0.08)", tension: 0.3, fill: true, pointRadius: trend.length > 1 ? 3 : 5, pointHoverRadius: 6 },
    ],
  };
  if (trendChartInstance) trendChartInstance.destroy();
  trendChartInstance = new Chart(ctx, {
    type: "line",
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "top", align: "end",
          labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 8, boxHeight: 8, padding: 16, font: { size: 12, weight: "600" } },
        },
        tooltip: {
          backgroundColor: "#2c0526", padding: 10, cornerRadius: 8, titleFont: { size: 12 }, bodyFont: { size: 12 },
        },
      },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0, font: { size: 11 } }, grid: { color: "rgba(64,9,56,0.06)" } },
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

function renderDonutChart(current) {
  const ctx = document.getElementById("donutChart");
  if (typeof Chart === "undefined") return;
  if (donutChartInstance) donutChartInstance.destroy();
  const total = (current.healthy || 0) + (current.warning || 0) + (current.critical || 0);
  if (!total) {
    ctx.style.display = "none";
    if (!document.getElementById("donutEmpty")) {
      ctx.parentElement.insertAdjacentHTML("beforeend", '<div class="empty-state" id="donutEmpty"><span class="material-symbols-outlined">donut_large</span><div>No platforms registered yet.</div></div>');
    }
    return;
  }
  ctx.style.display = "";
  const existingEmpty = document.getElementById("donutEmpty");
  if (existingEmpty) existingEmpty.remove();
  donutChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Healthy", "Degraded", "Down"],
      datasets: [{
        data: [current.healthy || 0, current.warning || 0, current.critical || 0],
        backgroundColor: [CHART_COLORS.healthy, CHART_COLORS.degraded, CHART_COLORS.down],
        borderWidth: 3, borderColor: "#ffffff", hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "66%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 9, boxHeight: 9, padding: 18, font: { size: 12, weight: "600" } },
        },
        tooltip: { backgroundColor: "#2c0526", padding: 10, cornerRadius: 8 },
      },
    },
  });
}

function renderIncidentBarChart(dailyCounts) {
  const frame = document.getElementById("incidentBarChart").parentElement;
  const existingEmpty = document.getElementById("incidentBarEmpty");
  if (existingEmpty) existingEmpty.remove();
  const ctx = document.getElementById("incidentBarChart");
  ctx.style.display = "";

  if (typeof Chart === "undefined") return;

  if (!dailyCounts || !dailyCounts.length) {
    ctx.style.display = "none";
    frame.insertAdjacentHTML("beforeend", '<div class="empty-state" id="incidentBarEmpty"><span class="material-symbols-outlined">bar_chart</span><div>No days to show yet for this range.</div></div>');
    return;
  }

  const labels = dailyCounts.map((d) => d.date);
  const counts = dailyCounts.map((d) => d.count);
  const zeroDays = counts.filter((c) => c === 0).length;
  document.getElementById("incidentBarDesc").textContent =
    `One bar per day across the selected range. ${zeroDays} of ${counts.length} day${counts.length === 1 ? "" : "s"} had no incidents.`;

  if (incidentBarChartInstance) incidentBarChartInstance.destroy();
  incidentBarChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Incidents",
        data: counts,
        backgroundColor: counts.map((c) => (c === 0 ? "rgba(64,9,56,0.08)" : "rgba(0,179,164,0.55)")),
        hoverBackgroundColor: counts.map((c) => (c === 0 ? "rgba(64,9,56,0.14)" : "#007e73")),
        borderRadius: 4,
        borderSkipped: false,
        maxBarThickness: 28,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#2c0526", padding: 10, cornerRadius: 8, titleFont: { size: 12 }, bodyFont: { size: 12 },
          callbacks: {
            label: (item) => `${item.parsed.y} incident${item.parsed.y === 1 ? "" : "s"}`,
          },
        },
      },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0, font: { size: 11 } }, grid: { color: "rgba(64,9,56,0.06)" } },
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10, font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

function renderPlatformTable(platforms, filterHealth) {
  const body = document.getElementById("platformTableBody");
  const desc = document.getElementById("platformTableDesc");
  let rows = platforms;
  if (filterHealth) {
    rows = platforms.filter((p) => p.health === filterHealth);
    desc.textContent = `Filtered to ${filterHealth}. Click the same tile again to clear.`;
  } else {
    desc.textContent = "Live status of every registered platform";
  }
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">No platforms match.</td></tr>';
    return;
  }
  body.innerHTML = rows.slice(0, 8).map((p) => `
    <tr class="row-link" onclick="window.location.href='/platform/${encodeURIComponent(p.id)}'">
      <td class="cell-primary">${escapeHtml(p.project_name)} ${stageBadge(p.stage)}</td>
      <td>${healthBadge(p.health)}</td>
      <td>${escapeHtml(p.assigned_operator || "Unassigned")}</td>
      <td class="cell-muted">${escapeHtml(timeAgoOrValue(p.last_visit))}</td>
      <td><span class="material-symbols-outlined" style="color:var(--c-outline);">chevron_right</span></td>
    </tr>
  `).join("");
}

function renderRecentIncidents(incidents) {
  const wrap = document.getElementById("recentIncidents");
  if (!incidents || !incidents.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">fact_check</span><div>No incidents in this range.</div></div>';
    return;
  }
  wrap.innerHTML = incidents.map((inc) => `
    <div class="timeline-item">
      <div class="timeline-dot"></div>
      <div class="timeline-body">
        <div class="timeline-title">${escapeHtml(inc.project_name || inc.platform_id)} <span class="chip">${escapeHtml(inc.status || "Open")}</span></div>
        <div class="timeline-meta">${escapeHtml(inc.reported_by || "Reporter")} · ${escapeHtml((inc.timestamp || "").toString().slice(0, 16).replace("T", " "))}</div>
        <div class="timeline-diff">${escapeHtml(inc.health || "")}: ${escapeHtml(inc.notes || "No details provided.")}</div>
      </div>
    </div>
  `).join("");
}

function setupKpiClicks() {
  document.querySelectorAll(".kpi-clickable").forEach((card) => {
    card.addEventListener("click", () => {
      const val = card.dataset.filter;
      activeKpiFilter = activeKpiFilter === val ? "" : val;
      document.querySelectorAll(".kpi-clickable").forEach((c) => c.classList.remove("is-active"));
      if (activeKpiFilter) card.classList.add("is-active");
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
    if (!customStart) { showToast("Pick a start date first.", true); return; }
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
