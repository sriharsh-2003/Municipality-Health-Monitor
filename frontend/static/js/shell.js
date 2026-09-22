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

let _toastTimer = null;
function showToast(message, isError) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.toggle("is-error", !!isError);
  el.classList.add("is-visible");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("is-visible"), 3200);
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
