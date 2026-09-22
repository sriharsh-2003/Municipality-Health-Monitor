/* incident.js — Add Incident: select platform, set status + detail + screenshots.
   Saving updates the platform's status/notes AND writes a full incident record. */

let platformsById = {};
let selectedFiles = [];
const MAX_FILES = 6;

async function loadPlatformOptions() {
  const select = document.getElementById("platformSelect");
  try {
    const platforms = await Api.getPlatforms();
    platforms.forEach((p) => { platformsById[p.id] = p; });
    select.innerHTML = '<option value="">Select a platform…</option>' + platforms.map(
      (p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.project_name)}</option>`
    ).join("");

    if (window.__PRESELECT_PLATFORM__) {
      select.value = window.__PRESELECT_PLATFORM__;
      onPlatformChange();
    }
  } catch (err) {
    showToast(err.message || "Could not load platforms.", true);
  }
}

function onPlatformChange() {
  const select = document.getElementById("platformSelect");
  const box = document.getElementById("currentStateBox");
  const chip = document.getElementById("currentStateChip");
  const p = platformsById[select.value];
  if (!p) { box.style.display = "none"; return; }
  box.style.display = "block";
  chip.innerHTML = `<span class="status-dot ${p.health === "Healthy" ? "healthy" : p.health === "Degraded" ? "degraded" : "down"}"></span>Currently: ${escapeHtml(p.health)} · last visit ${escapeHtml(p.last_visit || "—")}`;
  document.querySelectorAll('input[name="health"]').forEach((r) => { r.checked = r.value === p.health; });
  validateNotes();
}

function validateNotes() {
  const health = document.querySelector('input[name="health"]:checked')?.value;
  const notesInput = document.getElementById("notesInput");
  const field = notesInput.closest(".field");
  if (health && health !== "Healthy" && !notesInput.value.trim()) {
    field.classList.add("has-error");
    return false;
  }
  field.classList.remove("has-error");
  return true;
}

// ---------------------------------------------------------------- files

function renderThumbs() {
  const grid = document.getElementById("thumbGrid");
  grid.innerHTML = selectedFiles.map((file, i) => `
    <div class="thumb-card">
      <img src="${URL.createObjectURL(file)}" alt="${escapeHtml(file.name)}">
      <button type="button" class="thumb-remove" data-index="${i}" title="Remove">
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>
  `).join("");
  grid.querySelectorAll(".thumb-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedFiles.splice(Number(btn.dataset.index), 1);
      renderThumbs();
    });
  });
}

function addFiles(fileList) {
  const incoming = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
  const room = MAX_FILES - selectedFiles.length;
  if (room <= 0) { showToast(`You can attach up to ${MAX_FILES} screenshots.`, true); return; }
  selectedFiles = selectedFiles.concat(incoming.slice(0, room));
  if (incoming.length > room) showToast(`Only added the first ${room} — ${MAX_FILES} max.`, true);
  renderThumbs();
}

function setupDropzone() {
  const zone = document.getElementById("dropzone");
  const input = document.getElementById("fileInput");
  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((evt) => zone.addEventListener(evt, (e) => {
    e.preventDefault(); zone.classList.add("is-dragover");
  }));
  ["dragleave", "drop"].forEach((evt) => zone.addEventListener(evt, (e) => {
    e.preventDefault(); zone.classList.remove("is-dragover");
  }));
  zone.addEventListener("drop", (e) => { if (e.dataTransfer.files) addFiles(e.dataTransfer.files); });
}

// ---------------------------------------------------------------- submit

document.addEventListener("DOMContentLoaded", () => {
  loadPlatformOptions();
  setupDropzone();
  const reportingAsLabel = document.getElementById("reportingAsLabel");
  if (reportingAsLabel) reportingAsLabel.textContent = getOperatorName();
  document.getElementById("platformSelect").addEventListener("change", onPlatformChange);
  document.querySelectorAll('input[name="health"]').forEach((r) => r.addEventListener("change", validateNotes));
  document.getElementById("notesInput").addEventListener("input", validateNotes);

  document.getElementById("nowBtn").addEventListener("click", () => {
    const el = document.getElementById("occurredAtInput");
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    el.value = now.toISOString().slice(0, 16);
  });

  document.getElementById("incidentForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const platformId = document.getElementById("platformSelect").value;
    if (!platformId) { showToast("Choose a platform first.", true); return; }
    if (!validateNotes()) return;

    const fd = new FormData();
    ["health", "notes", "severity", "category", "affected_component", "eta", "last_detection", "resolution_notes", "occurred_at"].forEach((name) => {
      const el = form.querySelector(`[name="${name}"]`);
      if (!el) return;
      if (name === "health") {
        fd.append("health", form.querySelector('input[name="health"]:checked').value);
      } else {
        fd.append(name, el.value || "");
      }
    });
    fd.append("changed_by", getOperatorName());
    selectedFiles.forEach((file) => fd.append("screenshots", file, file.name));

    const btn = document.getElementById("submitBtn");
    btn.disabled = true;
    try {
      await Api.createIncident(platformId, fd);
      showToast("Incident saved — platform status updated.");
      setTimeout(() => { window.location.href = `/platform/${encodeURIComponent(platformId)}`; }, 500);
    } catch (err) {
      showToast(err.message || "Could not save incident.", true);
      btn.disabled = false;
    }
  });
});
