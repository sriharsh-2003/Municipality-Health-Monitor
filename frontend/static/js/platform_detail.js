/* platform_detail.js — Platform profile, edit form, incident history (with
   screenshots), and the raw field-level audit trail for one platform. */

const PLATFORM_ID = window.__PLATFORM_ID__;

async function loadPlatformDetail() {
  try {
    const [platform, logs, incidents] = await Promise.all([
      Api.getPlatform(PLATFORM_ID),
      Api.getLogs(500),
      Api.getIncidents(PLATFORM_ID, 200),
    ]);
    renderHeader(platform);
    renderKpis(platform);
    fillForm(platform);
    renderTimeline(logs.filter((l) => l.platform_id === PLATFORM_ID));
    renderIncidents(incidents);
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
  document.getElementById("camerasValue").textContent = `${p.cameras_online ?? 0} / ${p.cameras_total ?? 0}`;
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

function renderIncidents(incidents) {
  const wrap = document.getElementById("incidentList");
  if (!incidents.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">fact_check</span><div>No incidents logged yet for this platform.</div></div>';
    return;
  }
  wrap.innerHTML = incidents.slice(0, 25).map((inc) => {
    const shots = (inc.screenshots || []).map((name) => {
      const url = `/attachments/${encodeURIComponent(inc.id)}/${encodeURIComponent(name)}`;
      return `<a class="thumb-link" href="${url}" target="_blank"><img src="${url}" alt="Incident screenshot"></a>`;
    }).join("");
    return `
    <div class="incident-card">
      <div class="incident-card-head">
        ${healthBadge(inc.health)}
        ${inc.severity ? `<span class="badge ${severityBadgeClass(inc.severity)}">${escapeHtml(inc.severity)}</span>` : ""}
        ${inc.category ? `<span class="chip">${escapeHtml(inc.category)}</span>` : ""}
        <div class="incident-card-title" style="text-align:right; flex:1;">${escapeHtml(inc.timestamp)}</div>
      </div>
      <div class="incident-card-meta">${escapeHtml(inc.reported_by || "Reporter")} · cycle ${escapeHtml(inc.cycle)}${inc.affected_component ? " · " + escapeHtml(inc.affected_component) : ""}${inc.eta ? " · ETA " + escapeHtml(inc.eta) : ""}</div>
      <div class="incident-card-body">${escapeHtml(inc.notes || "No details provided.")}</div>
      ${inc.resolution_notes ? `<div class="incident-card-resolution"><strong>Resolution:</strong> ${escapeHtml(inc.resolution_notes)}</div>` : ""}
      ${shots ? `<div class="thumb-row" style="margin-top:10px;">${shots}</div>` : ""}
    </div>`;
  }).join("");
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
        <div class="timeline-meta">${escapeHtml(l.changed_by || "Reporter")} · ${escapeHtml(l.timestamp || "")} · cycle ${escapeHtml(l.cycle)}</div>
        <div class="timeline-diff">${escapeHtml(l.old_value ?? "—")} → ${escapeHtml(l.new_value ?? "—")}</div>
      </div>
    </div>
  `).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  loadPlatformDetail();

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
