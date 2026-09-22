/* audit.js, Audit Log: Incidents tab (searchable, editable, exportable)
   and Field Changes tab (raw log, unchanged from before). */

let allIncidents = [];
let allLogs = [];
let currentIncidentStatusFilter = "all";
let currentFieldFilter = "all";
let editSelectedFiles = [];
let editExistingScreenshots = [];
let editIncidentIdCurrent = null;

const STATUS_NEXT = { "Open": "Acknowledged", "Acknowledged": "In Progress", "In Progress": "Resolved" };
const STATUS_NEXT_LABEL = { "Open": "Acknowledge", "Acknowledged": "Start Progress", "In Progress": "Mark Resolved" };
const STATUS_NEXT_ICON = { "Open": "visibility", "Acknowledged": "engineering", "In Progress": "task_alt" };

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

function openLightbox(url) {
  document.getElementById("lightboxImage").src = url;
  document.getElementById("lightboxModal").classList.add("is-open");
}

function closeLightbox() {
  document.getElementById("lightboxModal").classList.remove("is-open");
  document.getElementById("lightboxImage").src = "";
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
        loadIncidents();
      } catch (err) {
        showToast(err.message || "Could not update status.", true);
        btn.disabled = false;
      }
    });
  });
}

// ---------------------------------------------------------------- incidents tab

async function loadIncidents() {
  try {
    allIncidents = await Api.getAllIncidents(500);
    renderIncidents();
  } catch (err) {
    showToast(err.message || "Could not load incidents.", true);
  }
}

function renderIncidents() {
  const wrap = document.getElementById("incidentAuditList");
  const q = (document.getElementById("incidentSearchInput").value || "").toLowerCase().trim();
  let rows = allIncidents.filter((inc) => {
    if (currentIncidentStatusFilter !== "all" && (inc.status || "Open") !== currentIncidentStatusFilter) return false;
    if (!q) return true;
    return (
      (inc.project_name || "").toLowerCase().includes(q) ||
      (inc.category || "").toLowerCase().includes(q) ||
      (inc.reported_by || "").toLowerCase().includes(q)
    );
  });

  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">fact_check</span><div>No incidents match.</div></div>';
    return;
  }

  wrap.innerHTML = rows.map((inc) => {
    const status = inc.status || "Open";
    const shots = (inc.screenshots || []).map((name) => {
      const url = `/attachments/${encodeURIComponent(inc.id)}/${encodeURIComponent(name)}`;
      return `<button type="button" class="thumb-link screenshot-trigger" data-url="${url}" style="border:1px solid var(--c-border); cursor:zoom-in; padding:0;"><img src="${url}" alt="Incident screenshot"></button>`;
    }).join("");
    const nextStatus = STATUS_NEXT[status];
    let actionsHtml = `<button class="btn btn-secondary btn-sm" onclick="openEditModal('${inc.id}')"><span class="material-symbols-outlined">edit</span>Correct this record</button>`;
    if (nextStatus) {
      actionsHtml += `<button class="btn btn-primary btn-sm status-action" data-incident-id="${inc.id}" data-next-status="${nextStatus}"><span class="material-symbols-outlined">${STATUS_NEXT_ICON[status]}</span>${STATUS_NEXT_LABEL[status]}</button>`;
    }
    if (status === "Resolved") {
      actionsHtml += `<button class="btn btn-ghost btn-sm status-action" data-incident-id="${inc.id}" data-next-status="Open"><span class="material-symbols-outlined">replay</span>Reopen</button>`;
    }
    actionsHtml += `<a class="btn btn-ghost btn-sm" href="/platform/${encodeURIComponent(inc.platform_id)}"><span class="material-symbols-outlined">open_in_new</span>Open platform</a>`;
    return `
    <div class="incident-card">
      <div class="incident-card-head">
        ${healthBadge(inc.health)}
        <span class="badge ${statusChipClass(status)}">${escapeHtml(status)}</span>
        ${inc.severity ? `<span class="badge ${severityBadgeClass(inc.severity)}">${escapeHtml(inc.severity)}</span>` : ""}
        ${inc.category ? `<span class="chip">${escapeHtml(inc.category)}</span>` : ""}
        <div class="incident-card-title" style="text-align:right; flex:1;">${escapeHtml(inc.project_name)}</div>
      </div>
      <div class="incident-card-meta">
        ${escapeHtml((inc.timestamp || "").slice(0, 16).replace("T", " "))}, ${escapeHtml(inc.reported_by || "Reporter")}
        ${inc.edited_by ? `, edited by ${escapeHtml(inc.edited_by)}` : ""}
      </div>
      <div class="incident-card-body">${escapeHtml(inc.notes || "No details provided.")}</div>
      ${inc.resolution_notes ? `<div class="incident-card-resolution"><strong>Resolution:</strong> ${escapeHtml(inc.resolution_notes)}</div>` : ""}
      ${shots ? `<div class="thumb-row" style="margin-top:10px;">${shots}</div>` : ""}
      <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
        ${actionsHtml}
      </div>
    </div>`;
  }).join("");
  wireIncidentCardActions();
}

// ---------------------------------------------------------------- edit modal

function openEditModal(incidentId) {
  const inc = allIncidents.find((i) => i.id === incidentId);
  if (!inc) return;
  editIncidentIdCurrent = incidentId;
  editSelectedFiles = [];
  editExistingScreenshots = [...(inc.screenshots || [])];

  document.getElementById("editIncidentId").value = incidentId;
  document.getElementById("editStatus").value = inc.status || "Open";
  document.getElementById("editHealth").value = inc.health || "Healthy";
  document.getElementById("editSeverity").value = inc.severity || "";
  document.getElementById("editCategory").value = inc.category || "";
  document.getElementById("editComponent").value = inc.affected_component || "";
  document.getElementById("editEta").value = inc.eta || "";
  document.getElementById("editNotes").value = inc.notes || "";
  document.getElementById("editResolution").value = inc.resolution_notes || "";
  if (inc.timestamp) {
    document.getElementById("editOccurredAt").value = inc.timestamp.slice(0, 16);
  }
  renderEditThumbs(incidentId);
  document.getElementById("editModal").classList.add("is-open");
}

function renderEditThumbs(incidentId) {
  const grid = document.getElementById("editThumbGrid");
  const existingHtml = editExistingScreenshots.map((name) => {
    const url = `/attachments/${encodeURIComponent(incidentId)}/${encodeURIComponent(name)}`;
    return `
      <div class="thumb-card">
        <img src="${url}" alt="${escapeHtml(name)}">
        <button type="button" class="thumb-remove" data-existing="${escapeHtml(name)}" title="Remove"><span class="material-symbols-outlined">close</span></button>
      </div>`;
  }).join("");
  const newHtml = editSelectedFiles.map((file, i) => `
    <div class="thumb-card">
      <img src="${URL.createObjectURL(file)}" alt="${escapeHtml(file.name)}">
      <button type="button" class="thumb-remove" data-new-index="${i}" title="Remove"><span class="material-symbols-outlined">close</span></button>
    </div>`).join("");
  grid.innerHTML = existingHtml + newHtml;

  grid.querySelectorAll("[data-existing]").forEach((btn) => {
    btn.addEventListener("click", () => {
      editExistingScreenshots = editExistingScreenshots.filter((n) => n !== btn.dataset.existing);
      renderEditThumbs(incidentId);
    });
  });
  grid.querySelectorAll("[data-new-index]").forEach((btn) => {
    btn.addEventListener("click", () => {
      editSelectedFiles.splice(Number(btn.dataset.newIndex), 1);
      renderEditThumbs(incidentId);
    });
  });
}

function closeEditModal() {
  document.getElementById("editModal").classList.remove("is-open");
}

// ---------------------------------------------------------------- field changes tab

async function loadAuditFields() {
  try {
    allLogs = await Api.getLogs(500);
    renderFieldLogs();
  } catch (err) {
    showToast(err.message || "Could not load the audit log.", true);
  }
}

function renderFieldLogs() {
  const body = document.getElementById("auditBody");
  const q = (document.getElementById("searchInput").value || "").toLowerCase().trim();
  let rows = allLogs.filter((l) => {
    if (currentFieldFilter !== "all" && l.field !== currentFieldFilter) return false;
    if (!q) return true;
    return (
      (l.project_name || "").toLowerCase().includes(q) ||
      (l.field || "").toLowerCase().includes(q) ||
      (l.changed_by || "").toLowerCase().includes(q)
    );
  });
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-state"><span class="material-symbols-outlined">history_toggle_off</span><div>No matching log entries.</div></td></tr>';
    return;
  }
  body.innerHTML = rows.map((l) => `
    <tr>
      <td class="cell-muted">${escapeHtml(l.timestamp)}</td>
      <td class="cell-primary">${escapeHtml(l.project_name || l.platform_id)}</td>
      <td><span class="chip">${escapeHtml(l.field)}</span></td>
      <td class="cell-muted">${escapeHtml(l.old_value ?? "Not set")}</td>
      <td>${escapeHtml(l.new_value ?? "Not set")}</td>
      <td class="cell-muted">${escapeHtml(l.changed_by || "Not set")}</td>
      <td class="cell-muted">${escapeHtml(l.cycle)}</td>
    </tr>
  `).join("");
}

// ---------------------------------------------------------------- wiring

document.addEventListener("DOMContentLoaded", () => {
  loadIncidents();

  document.querySelectorAll("#auditTabs .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#auditTabs .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      const isIncidents = tab.dataset.tab === "incidents";
      document.getElementById("tabIncidents").style.display = isIncidents ? "block" : "none";
      document.getElementById("tabFields").style.display = isIncidents ? "none" : "block";
      if (!isIncidents && !allLogs.length) loadAuditFields();
    });
  });

  document.getElementById("incidentSearchInput").addEventListener("input", renderIncidents);
  document.querySelectorAll("#incidentStatusFilter .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#incidentStatusFilter .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      currentIncidentStatusFilter = tab.dataset.status;
      renderIncidents();
    });
  });

  document.getElementById("searchInput").addEventListener("input", renderFieldLogs);
  document.querySelectorAll("#fieldFilter .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#fieldFilter .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      currentFieldFilter = tab.dataset.field;
      renderFieldLogs();
    });
  });

  document.getElementById("exportBtn").addEventListener("click", () => { window.location.href = "/api/export"; });
  document.getElementById("exportCsvBtn").addEventListener("click", () => { window.location.href = Api.incidentsCsvUrl(); });

  document.getElementById("closeEditModal").addEventListener("click", closeEditModal);
  document.getElementById("cancelEditBtn").addEventListener("click", closeEditModal);
  document.getElementById("editModal").addEventListener("click", (e) => { if (e.target.id === "editModal") closeEditModal(); });

  document.getElementById("closeLightbox").addEventListener("click", closeLightbox);
  document.getElementById("lightboxModal").addEventListener("click", (e) => { if (e.target.id === "lightboxModal") closeLightbox(); });

  const editDropzone = document.getElementById("editDropzone");
  const editFileInput = document.getElementById("editFileInput");
  editDropzone.addEventListener("click", () => editFileInput.click());
  editFileInput.addEventListener("change", () => {
    const room = 6 - editExistingScreenshots.length - editSelectedFiles.length;
    const incoming = Array.from(editFileInput.files).filter((f) => f.type.startsWith("image/")).slice(0, Math.max(room, 0));
    editSelectedFiles = editSelectedFiles.concat(incoming);
    renderEditThumbs(editIncidentIdCurrent);
    editFileInput.value = "";
  });

  document.getElementById("editIncidentForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const inc = allIncidents.find((i) => i.id === editIncidentIdCurrent);
    const originalScreenshots = inc ? (inc.screenshots || []) : [];
    const removed = originalScreenshots.filter((n) => !editExistingScreenshots.includes(n));

    const fd = new FormData();
    fd.append("status", document.getElementById("editStatus").value);
    fd.append("health", document.getElementById("editHealth").value);
    fd.append("severity", document.getElementById("editSeverity").value);
    fd.append("category", document.getElementById("editCategory").value);
    fd.append("affected_component", document.getElementById("editComponent").value);
    fd.append("eta", document.getElementById("editEta").value);
    fd.append("notes", document.getElementById("editNotes").value);
    fd.append("resolution_notes", document.getElementById("editResolution").value);
    fd.append("occurred_at", document.getElementById("editOccurredAt").value);
    fd.append("changed_by", getOperatorName());
    if (removed.length) fd.append("remove_screenshots", removed.join(","));
    editSelectedFiles.forEach((file) => fd.append("screenshots", file, file.name));

    const btn = document.getElementById("saveEditBtn");
    btn.disabled = true;
    try {
      await Api.updateIncident(editIncidentIdCurrent, fd);
      showToast("Incident record updated.");
      closeEditModal();
      loadIncidents();
    } catch (err) {
      showToast(err.message || "Could not save the correction.", true);
    } finally {
      btn.disabled = false;
    }
  });
});
