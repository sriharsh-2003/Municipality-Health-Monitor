/* registry.js, Platform Registry: search, status filter, list, and a
   hover popup (1s delay, persists while hovering the popup itself) that
   previews a platform's recent incident history without leaving the page. */

let allPlatforms = [];
let currentFilter = "all";

async function loadRegistry() {
  try {
    allPlatforms = await Api.getPlatforms();
    renderRegistry();
  } catch (err) {
    showToast(err.message || "Could not load platforms.", true);
  }
}

function severityBadgeClass(sev) {
  if (sev === "Critical" || sev === "High") return "badge-down";
  if (sev === "Medium") return "badge-degraded";
  if (sev === "Low") return "badge-healthy";
  return "badge-neutral";
}

function renderRegistry() {
  const body = document.getElementById("registryBody");
  const q = (document.getElementById("searchInput").value || "").toLowerCase().trim();

  let rows = allPlatforms.filter((p) => {
    if (currentFilter !== "all" && p.health !== currentFilter) return false;
    if (!q) return true;
    return (
      (p.project_name || "").toLowerCase().includes(q) ||
      (p.assigned_operator || "").toLowerCase().includes(q) ||
      (p.url || "").toLowerCase().includes(q)
    );
  });

  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-state"><span class="material-symbols-outlined">search_off</span><div>No platforms match.</div></td></tr>';
    return;
  }

  body.innerHTML = rows.map((p) => `
    <tr>
      <td class="row-link" onclick="window.location.href='/platform/${encodeURIComponent(p.id)}'">
        <div class="cell-primary">${escapeHtml(p.project_name)} ${stageBadge(p.stage)}</div>
        <div class="cell-muted">${escapeHtml(p.url || "")}</div>
      </td>
      <td>${healthBadge(p.health)}</td>
      <td>${escapeHtml(p.assigned_operator || "Unassigned")}</td>
      <td class="cell-muted">${escapeHtml(timeAgoOrValue(p.last_visit))}</td>
      <td class="cell-muted">${p.cameras_online ?? 0} / ${p.cameras_total ?? 0}</td>
      <td>
        <span class="chip hover-trigger" data-platform-id="${escapeHtml(p.id)}" data-platform-name="${escapeHtml(p.project_name)}">
          <span class="material-symbols-outlined" style="font-size:15px;">history</span> Preview
        </span>
      </td>
      <td class="row-link" onclick="window.location.href='/platform/${encodeURIComponent(p.id)}'"><span class="material-symbols-outlined" style="color:var(--c-outline);">chevron_right</span></td>
    </tr>
  `).join("");

  setupHoverPopups();
}

// ---------------------------------------------------------------- hover popup

let hoverShowTimer = null;
let hoverHideTimer = null;
let hoverCache = {};

function setupHoverPopups() {
  const popup = document.getElementById("historyPopup");

  document.querySelectorAll(".hover-trigger").forEach((el) => {
    el.addEventListener("mouseenter", () => {
      clearTimeout(hoverHideTimer);
      const rect = el.getBoundingClientRect();
      hoverShowTimer = setTimeout(async () => {
        await showHistoryPopup(el.dataset.platformId, el.dataset.platformName, rect);
      }, 1000);
    });
    el.addEventListener("mouseleave", () => {
      clearTimeout(hoverShowTimer);
      hoverHideTimer = setTimeout(() => hidePopup(), 250);
    });
  });

  popup.addEventListener("mouseenter", () => clearTimeout(hoverHideTimer));
  popup.addEventListener("mouseleave", () => {
    hoverHideTimer = setTimeout(() => hidePopup(), 250);
  });
}

function hidePopup() {
  document.getElementById("historyPopup").classList.remove("is-visible");
}

async function showHistoryPopup(platformId, platformName, triggerRect) {
  const popup = document.getElementById("historyPopup");
  let incidents = hoverCache[platformId];
  if (!incidents) {
    try {
      incidents = await Api.getIncidents(platformId, 3);
      hoverCache[platformId] = incidents;
    } catch (e) {
      incidents = [];
    }
  }

  popup.innerHTML = `<div class="hover-popup-title">${escapeHtml(platformName)}, recent incidents</div>` + (
    incidents.length
      ? incidents.map((inc) => `
        <div class="hover-popup-item">
          <div>${healthBadge(inc.health)} ${inc.severity ? `<span class="badge ${severityBadgeClass(inc.severity)}">${escapeHtml(inc.severity)}</span>` : ""}</div>
          <div class="meta">${escapeHtml((inc.timestamp || "").slice(0, 16).replace("T", " "))} · ${escapeHtml(inc.reported_by || "Reporter")}</div>
          <div>${escapeHtml((inc.notes || "No details provided.").slice(0, 140))}</div>
        </div>`).join("")
      : '<div class="hover-popup-item">No incidents logged yet.</div>'
  );

  // Position near the trigger, keeping the popup on-screen.
  const popupWidth = 320;
  let left = triggerRect.left;
  if (left + popupWidth > window.innerWidth - 16) left = window.innerWidth - popupWidth - 16;
  let top = triggerRect.bottom + 8;
  popup.style.left = `${Math.max(16, left)}px`;
  popup.style.top = `${top}px`;
  popup.classList.add("is-visible");

  // If it would run off the bottom of the viewport, flip it above the trigger instead.
  requestAnimationFrame(() => {
    const popupRect = popup.getBoundingClientRect();
    if (popupRect.bottom > window.innerHeight - 12) {
      popup.style.top = `${Math.max(12, triggerRect.top - popupRect.height - 8)}px`;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadRegistry();
  document.getElementById("searchInput").addEventListener("input", renderRegistry);
  document.querySelectorAll("#statusFilter .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#statusFilter .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      currentFilter = tab.dataset.status;
      renderRegistry();
    });
  });
});
