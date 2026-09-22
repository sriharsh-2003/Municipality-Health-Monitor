/* shell.js — sidebar behavior, operator name, toast notifications. Shared by every page. */

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
  if (roleSelect) {
    roleSelect.value = getOperatorRole();
    roleSelect.addEventListener("change", () => setOperatorRole(roleSelect.value));
  }

  const operatorInput = document.getElementById("operatorNameInput");
  if (operatorInput) {
    operatorInput.value = getOperatorDisplayName();
    operatorInput.addEventListener("change", () => {
      const val = operatorInput.value.trim();
      setOperatorName(val);
      operatorInput.value = val;
    });

    // First-ever visit on this browser: no name typed yet, so pull the
    // office-wide default (set on the Settings page) instead of leaving
    // it blank / showing a generic role with no name attached.
    if (!getOperatorDisplayName()) {
      fetch("/api/app-settings").then((r) => r.json()).then((s) => {
        if (s.default_reporter_name && !getOperatorDisplayName()) {
          setOperatorName(s.default_reporter_name);
          operatorInput.value = s.default_reporter_name;
        }
      }).catch(() => {});
    }
  }
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
  return v || "—";
}
