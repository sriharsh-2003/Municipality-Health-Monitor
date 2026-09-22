/* platform_detail.js, Platform Overview (KPIs, interactive incident
   history with a real status workflow, field audit trail) kept separate
   from the Edit Details tab (profile form + delete), plus a screenshot
   lightbox shared by every incident card. */

const PLATFORM_ID = window.__PLATFORM_ID__;

const STATUS_NEXT = { "Open": "Acknowledged", "Acknowledged": "In Progress", "In Progress": "Resolved" };
const STATUS_NEXT_LABEL = { "Open": "Acknowledge", "Acknowledged": "Start Progress", "In Progress": "Mark Resolved" };
const STATUS_NEXT_ICON = { "Open": "visibility", "Acknowledged": "engineering", "In Progress": "task_alt" };

let allIncidentsForPlatform = [];
let incidentStatusFilter = "all";
let incidentsShown = 6;

async function loadPlatformDetail() {
  try {
    const [platform, logs, incidents] = await Promise.all([
      Api.getPlatform(PLATFORM_ID),
      Api.getLogs(500),
      Api.getIncidents(PLATFORM_ID, 500),
    ]);
    renderHeader(platform);
    renderKpis(platform);
    fillForm(platform);
    renderTimeline(logs.filter((l) => l.platform_id === PLATFORM_ID));
    allIncidentsForPlatform = incidents;
    incidentsShown = 6;
    renderIncidents();
    document.getElementById("logIncidentBtn").href = `/incident?platform=${encodeURIComponent(PLATFORM_ID)}`;
  } catch (err) {
    showToast(err.message || "Could not load this platform.", true);
  }
}

function renderHeader(p) {
  document.getElementById("platformName").textContent = p.project_name;
  document.getElementById("platformUrl").textContent = p.url || "No URL on file";
}

function renderKpis(p) {
  const cls = p.health === "Healthy" ? "" : p.health === "Degraded" ? "amber" : "down";
  const icon = p.health === "Healthy" ? "check_circle" : p.health === "Degraded" ? "warning" : "error";
  document.getElementById("statusIconWrap").className = `kpi-icon ${cls}`;
  document.getElementById("statusIcon").textContent = icon;
  document.getElementById("statusValue").innerHTML = healthBadge(p.health);
  document.getElementById("camerasValue").textContent = `${p.cameras_online ?? 0} of ${p.cameras_total ?? 0}`;
  document.getElementById("latencyValue").textContent = `${p.latency_ms ?? 0} ms`;
}

function fillForm(p) {
  const form = document.getElementById("profileForm");
  ["project_name", "url", "assigned_operator", "last_visit", "cameras_online", "cameras_total",
   "detections_today", "frames_processed", "latency_ms", "buffer_queue_items", "notes"].forEach((key) => {
    const el = form.querySelector(`[name="${key}"]`);
    if (el) el.value = p[key] ?? "";
  });
}

function severityBadgeClass(sev) {
  if (sev === "Critical" || sev === "High") return "badge-down";
  if (sev === "Medium") return "badge-degraded";
  if (sev === "Low") return "badge-healthy";
  return "badge-neutral";
}

function statusChipClass(status) {
  if (status === "Resolved") return "badge-healthy";
  if (status === "In Progress") return "badge-degraded";
  return "badge-neutral";
}

function renderIncidents() {
  const wrap = document.getElementById("incidentList");
  const showMoreBtn = document.getElementById("showMoreIncidentsBtn");

  let rows = allIncidentsForPlatform;
  if (incidentStatusFilter !== "all") {
    rows = rows.filter((inc) => (inc.status || "Open") === incidentStatusFilter);
  }

  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">fact_check</span><div>No incidents match.</div></div>';
    showMoreBtn.style.display = "none";
    return;
  }

  const visible = rows.slice(0, incidentsShown);
  wrap.innerHTML = visible.map(renderIncidentCard).join("");
  wireIncidentCardActions();

  if (rows.length > incidentsShown) {
    showMoreBtn.style.display = "inline-flex";
    showMoreBtn.textContent = `Show ${Math.min(6, rows.length - incidentsShown)} more (${rows.length - incidentsShown} remaining)`;
  } else {
    showMoreBtn.style.display = "none";
  }
}

function renderIncidentCard(inc) {
  const status = inc.status || "Open";
  const shots = (inc.screenshots || []).map((name) => {
    const url = `/attachments/${encodeURIComponent(inc.id)}/${encodeURIComponent(name)}`;
    return `<button type="button" class="thumb-link screenshot-trigger" data-url="${url}" style="border:1px solid var(--c-border); cursor:zoom-in; padding:0;"><img src="${url}" alt="Incident screenshot"></button>`;
  }).join("");

  const nextStatus = STATUS_NEXT[status];
  let actionsHtml = "";
  if (nextStatus) {
    actionsHtml += `<button class="btn btn-primary btn-sm status-action" data-incident-id="${inc.id}" data-next-status="${nextStatus}"><span class="material-symbols-outlined">${STATUS_NEXT_ICON[status]}</span>${STATUS_NEXT_LABEL[status]}</button>`;
  }
  if (status === "Resolved") {
    actionsHtml += `<button class="btn btn-ghost btn-sm status-action" data-incident-id="${inc.id}" data-next-status="Open"><span class="material-symbols-outlined">replay</span>Reopen</button>`;
  }

  return `
    <div class="incident-card">
      <div class="incident-card-head">
        ${healthBadge(inc.health)}
        <span class="badge ${statusChipClass(status)}">${escapeHtml(status)}</span>
        ${inc.severity ? `<span class="badge ${severityBadgeClass(inc.severity)}">${escapeHtml(inc.severity)}</span>` : ""}
        ${inc.category ? `<span class="chip">${escapeHtml(inc.category)}</span>` : ""}
        <div class="incident-card-title" style="text-align:right; flex:1;">${escapeHtml((inc.timestamp || "").slice(0, 16).replace("T", " "))}</div>
      </div>
      <div class="incident-card-meta">${escapeHtml(inc.reported_by || "Reporter")}${inc.affected_component ? ", " + escapeHtml(inc.affected_component) : ""}${inc.eta ? ", ETA " + escapeHtml(inc.eta) : ""}</div>
      <div class="incident-card-body">${escapeHtml(inc.notes || "No details provided.")}</div>
      ${inc.resolution_notes ? `<div class="incident-card-resolution"><strong>Resolution:</strong> ${escapeHtml(inc.resolution_notes)}</div>` : ""}
      ${shots ? `<div class="thumb-row" style="margin-top:10px;">${shots}</div>` : ""}
      ${actionsHtml ? `<div style="margin-top:12px; display:flex; gap:8px;">${actionsHtml}</div>` : ""}
    </div>`;
}

function wireIncidentCardActions() {
  document.querySelectorAll(".screenshot-trigger").forEach((btn) => {
    btn.addEventListener("click", () => openLightbox(btn.dataset.url));
  });
  document.querySelectorAll(".status-action").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const fd = new FormData();
      fd.append("status", btn.dataset.nextStatus);
      fd.append("changed_by", getOperatorName());
      try {
        await Api.updateIncident(btn.dataset.incidentId, fd);
        showToast(`Status set to ${btn.dataset.nextStatus}.`);
        loadPlatformDetail();
      } catch (err) {
        showToast(err.message || "Could not update status.", true);
        btn.disabled = false;
      }
    });
  });
}

function openLightbox(url) {
  document.getElementById("lightboxImage").src = url;
  document.getElementById("lightboxModal").classList.add("is-open");
}

function closeLightbox() {
  document.getElementById("lightboxModal").classList.remove("is-open");
  document.getElementById("lightboxImage").src = "";
}

function renderTimeline(logs) {
  const wrap = document.getElementById("platformTimeline");
  if (!logs.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">history_toggle_off</span><div>No field changes recorded yet.</div></div>';
    return;
  }
  wrap.innerHTML = logs.slice(0, 40).map((l) => `
    <div class="timeline-item">
      <div class="timeline-dot"></div>
      <div class="timeline-body">
        <div class="timeline-title">${escapeHtml(l.field)} changed</div>
        <div class="timeline-meta">${escapeHtml(l.changed_by || "Reporter")}, ${escapeHtml(l.timestamp || "")}, cycle ${escapeHtml(l.cycle)}</div>
        <div class="timeline-diff">${escapeHtml(l.old_value ?? "not set")} became ${escapeHtml(l.new_value ?? "not set")}</div>
      </div>
    </div>
  `).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  loadPlatformDetail();

  document.querySelectorAll("#detailTabs .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#detailTabs .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      const isOverview = tab.dataset.tab === "overview";
      document.getElementById("tabOverview").style.display = isOverview ? "block" : "none";
      document.getElementById("tabEdit").style.display = isOverview ? "none" : "block";
    });
  });

  document.querySelectorAll("#incidentStatusFilterDetail .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#incidentStatusFilterDetail .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      incidentStatusFilter = tab.dataset.status;
      incidentsShown = 6;
      renderIncidents();
    });
  });

  document.getElementById("showMoreIncidentsBtn").addEventListener("click", () => {
    incidentsShown += 6;
    renderIncidents();
  });

  document.getElementById("toggleAuditTrailBtn").addEventListener("click", () => {
    const timeline = document.getElementById("platformTimeline");
    const btn = document.getElementById("toggleAuditTrailBtn");
    const isHidden = timeline.style.display === "none";
    timeline.style.display = isHidden ? "block" : "none";
    btn.innerHTML = isHidden
      ? 'Hide<span class="material-symbols-outlined">expand_less</span>'
      : 'Show<span class="material-symbols-outlined">expand_more</span>';
  });

  document.getElementById("closeLightbox").addEventListener("click", closeLightbox);
  document.getElementById("lightboxModal").addEventListener("click", (e) => {
    if (e.target.id === "lightboxModal") closeLightbox();
  });

  document.getElementById("profileForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const record = {};
    for (const [key, value] of fd.entries()) {
      if (["cameras_online", "cameras_total", "detections_today", "frames_processed", "latency_ms", "buffer_queue_items"].includes(key)) {
        record[key] = Number(value) || 0;
      } else {
        record[key] = value;
      }
    }
    const btn = document.getElementById("saveProfileBtn");
    btn.disabled = true;
    try {
      await Api.updatePlatform(PLATFORM_ID, record, getOperatorName());
      showToast("Platform updated.");
      loadPlatformDetail();
    } catch (err) {
      showToast(err.message || "Could not save changes.", true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("deleteBtn").addEventListener("click", async () => {
    if (!confirm("Remove this platform from the registry? This cannot be undone.")) return;
    try {
      await Api.deletePlatform(PLATFORM_ID, getOperatorName());
      showToast("Platform removed.");
      setTimeout(() => { window.location.href = "/registry"; }, 500);
    } catch (err) {
      showToast(err.message || "Could not remove platform.", true);
    }
  });
});
