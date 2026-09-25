/* shell.js, sidebar behavior, operator name, toast notifications. Shared by every page. */

(function () {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebarToggle");

  function applyCollapsed(collapsed) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-collapsed", collapsed);
    const icon = toggleBtn && toggleBtn.querySelector(".material-symbols-outlined");
    if (icon) icon.textContent = collapsed ? "chevron_right" : "chevron_left";
  }

  const storedCollapsed = localStorage.getItem("sidebarCollapsed") === "1";
  applyCollapsed(storedCollapsed);

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const collapsed = !sidebar.classList.contains("is-collapsed");
      applyCollapsed(collapsed);
      localStorage.setItem("sidebarCollapsed", collapsed ? "1" : "0");
    });
  }

  const roleSelect = document.getElementById("operatorRoleSelect");
  const operatorInput = document.getElementById("operatorNameInput");
  const identityButton = document.getElementById("identityButton");
  const identityPopover = document.getElementById("identityPopover");
  const identitySummary = document.getElementById("identitySummary");
  const identityDoneBtn = document.getElementById("identityDoneBtn");

  function refreshIdentitySummary() {
    if (!identitySummary) return;
    const name = getOperatorDisplayName();
    const role = getOperatorRole();
    identitySummary.textContent = name ? `${name}, ${role}` : role;
  }

  if (roleSelect) {
    roleSelect.value = getOperatorRole();
    roleSelect.addEventListener("change", () => {
      setOperatorRole(roleSelect.value);
      refreshIdentitySummary();
    });
  }

  if (operatorInput) {
    operatorInput.value = getOperatorDisplayName();
    operatorInput.addEventListener("input", () => {
      setOperatorName(operatorInput.value.trim());
      refreshIdentitySummary();
    });

    // First-ever visit on this browser: no name typed yet, so pull the
    // office-wide default (set on the Settings page) instead of leaving
    // it blank, or showing only a generic role with no name attached.
    if (!getOperatorDisplayName()) {
      fetch("/api/app-settings").then((r) => r.json()).then((s) => {
        if (s.default_reporter_name && !getOperatorDisplayName()) {
          setOperatorName(s.default_reporter_name);
          operatorInput.value = s.default_reporter_name;
          refreshIdentitySummary();
        }
      }).catch(() => {});
    }
  }

  if (identityButton && identityPopover) {
    identityButton.addEventListener("click", (e) => {
      e.stopPropagation();
      identityPopover.classList.toggle("is-open");
    });
    identityDoneBtn.addEventListener("click", () => identityPopover.classList.remove("is-open"));
    document.addEventListener("click", (e) => {
      if (!identityPopover.contains(e.target) && e.target !== identityButton) {
        identityPopover.classList.remove("is-open");
      }
    });
  }

  refreshIdentitySummary();
})();

let dismissTimer = null;
function showToast(message, isError) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.toggle("is-error", !!isError);
  el.classList.add("is-visible");
  clearTimeout(dismissTimer);
  dismissTimer = setTimeout(() => el.classList.remove("is-visible"), 3200);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function healthBadge(health) {
  const cls = health === "Healthy" ? "badge-healthy" : health === "Degraded" ? "badge-degraded" : "badge-down";
  return `<span class="badge ${cls}">${escapeHtml(health || "Unknown")}</span>`;
}

function stageBadge(stage) {
  // Only rendered for the non-default case, a Running platform (the vast
  // majority) doesn't need a badge cluttering every row.
  if (stage !== "Under Development") return "";
  return '<span class="badge badge-dev">Under Development</span>';
}

function timeAgoOrValue(v) {
  return v || "Not set";
}

/* ---------------------------------------------------------------- hints
   One-time popup tips, replacing static banners that used to sit in the
   page permanently. Each hint has an id: once shown in this browser
   session it will not show again until the tab/browser session ends. */
function showHint(id, message, icon) {
  icon = icon || "info";
  const key = `hint_seen_${id}`;
  if (sessionStorage.getItem(key)) return;
  sessionStorage.setItem(key, "1");

  let stack = document.getElementById("hintStack");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "hintStack";
    stack.className = "hint-stack";
    document.body.appendChild(stack);
  }

  const el = document.createElement("div");
  el.className = "hint-toast";
  el.innerHTML = `
    <span class="material-symbols-outlined">${icon}</span>
    <div class="hint-toast-text">${message}</div>
    <button class="hint-toast-close" type="button" aria-label="Dismiss"><span class="material-symbols-outlined">close</span></button>
  `;
  stack.appendChild(el);
  requestAnimationFrame(() => el.classList.add("is-visible"));

  let dismissTimer = null;
  const remove = () => {
    clearTimeout(dismissTimer);
    el.classList.remove("is-visible");
    setTimeout(() => el.remove(), 200);
  };
  el.querySelector(".hint-toast-close").addEventListener("click", remove);
  dismissTimer = setTimeout(remove, 9000);
}

/* ---------------------------------------------------------------- resolve modal
   Used wherever an incident's status is moved to Resolved (Platform
   Details, Audit Log). Offers to also set the platform back to Healthy,
   and afterward offers quick links to log a follow-up incident or go look
   at the platform, instead of just silently updating a status chip. */
function openResolveModal({ incidentId, platformId, platformName, resolutionNotes, onResolved }) {
  let overlay = document.getElementById("resolveModalOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "resolveModalOverlay";
    overlay.className = "modal-overlay";
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:460px; position:relative;">
      <button class="btn btn-ghost btn-sm modal-close" id="resolveModalClose" type="button"><span class="material-symbols-outlined">close</span></button>
      <h2 style="font-size:16px; margin-bottom:4px;">Resolve Incident</h2>
      <p style="font-size:12.5px; color:var(--c-on-surface-var); margin-bottom:16px;">${escapeHtml(platformName)}</p>
      <div class="field">
        <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-weight:600;">
          <input type="checkbox" id="resolveSetHealthy" checked style="width:16px;height:16px;">
          Also set this platform's status back to Healthy
        </label>
        <div class="hint">Uncheck this if the platform still has a separate, unrelated issue.</div>
      </div>
      <div class="field">
        <label>Resolution notes</label>
        <textarea class="input" id="resolveNotesInput" placeholder="What fixed it, or the outcome">${escapeHtml(resolutionNotes || "")}</textarea>
      </div>
      <div class="form-actions">
        <button class="btn btn-ghost" id="resolveModalCancel" type="button">Cancel</button>
        <button class="btn btn-primary" id="resolveModalConfirm" type="button"><span class="material-symbols-outlined">task_alt</span>Confirm Resolution</button>
      </div>
    </div>
  `;
  overlay.classList.add("is-open");

  const close = () => overlay.classList.remove("is-open");
  overlay.querySelector("#resolveModalClose").addEventListener("click", close);
  overlay.querySelector("#resolveModalCancel").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

  overlay.querySelector("#resolveModalConfirm").addEventListener("click", async () => {
    const btn = overlay.querySelector("#resolveModalConfirm");
    btn.disabled = true;
    const setHealthy = overlay.querySelector("#resolveSetHealthy").checked;
    const notes = overlay.querySelector("#resolveNotesInput").value;
    try {
      const fd = new FormData();
      fd.append("status", "Resolved");
      fd.append("resolution_notes", notes);
      fd.append("changed_by", getOperatorName());
      await Api.updateIncident(incidentId, fd);
      if (setHealthy) {
        await Api.updatePlatform(platformId, { health: "Healthy" }, getOperatorName());
      }
      close();
      showResolvedFollowUp(platformId, platformName);
      if (onResolved) onResolved();
    } catch (err) {
      showToast(err.message || "Could not resolve incident.", true);
      btn.disabled = false;
    }
  });
}

function showResolvedFollowUp(platformId, platformName) {
  let stack = document.getElementById("hintStack");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "hintStack";
    stack.className = "hint-stack";
    document.body.appendChild(stack);
  }
  const el = document.createElement("div");
  el.className = "hint-toast";
  el.innerHTML = `
    <span class="material-symbols-outlined">task_alt</span>
    <div class="hint-toast-text">
      Incident resolved for ${escapeHtml(platformName)}.
      <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
        <a href="/incident?platform=${encodeURIComponent(platformId)}" class="btn btn-secondary btn-sm">Log Follow-up</a>
        <a href="/platform/${encodeURIComponent(platformId)}" class="btn btn-ghost btn-sm">View Platform</a>
      </div>
    </div>
    <button class="hint-toast-close" type="button" aria-label="Dismiss"><span class="material-symbols-outlined">close</span></button>
  `;
  stack.appendChild(el);
  requestAnimationFrame(() => el.classList.add("is-visible"));
  const remove = () => { el.classList.remove("is-visible"); setTimeout(() => el.remove(), 200); };
  el.querySelector(".hint-toast-close").addEventListener("click", remove);
  setTimeout(remove, 15000);
}
