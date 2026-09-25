/* email.js, Email Center: preview, in-place editing, send, automation settings. */

let currentIframe = null;
let isEditMode = false;
let originalGeneratedHtml = null;
let allIncidentsForAttach = [];
let selectedIncidentIds = new Set();
let currentReportType = "daily";

const REPORT_TYPE_HINTS = {
  daily: "A table of today's incidents, plus current platform status.",
  weekly: "This week's totals by status and severity, plus the week's incident table.",
  monthly: "A monthly rollup: totals, resolution rate, and incidents grouped by platform.",
};

async function generatePreview() {
  const sender = document.getElementById("senderInput").value.trim() || getOperatorName();
  const recipient = document.getElementById("recipientInput").value.trim() || "Manager";
  const frame = document.getElementById("previewFrame");
  frame.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">hourglass_top</span><div>Building preview</div></div>';
  document.getElementById("editToggleBtn").style.display = "none";
  document.getElementById("editStateChip").style.display = "none";
  isEditMode = false;

  try {
    const built = await Api.getEmailPreview(sender, recipient, currentReportType);
    originalGeneratedHtml = built.html;

    const iframe = document.createElement("iframe");
    iframe.style.width = "100%";
    iframe.style.height = "500px";
    iframe.style.border = "none";
    frame.innerHTML = "";
    frame.appendChild(iframe);
    iframe.srcdoc = built.html;
    currentIframe = iframe;

    document.getElementById("editToggleBtn").style.display = "inline-flex";
    setEditChip(false);
    document.getElementById("previewDesc").textContent = "Rendered as it will appear in the recipient's inbox";
  } catch (err) {
    showToast(err.message || "Could not build preview.", true);
    frame.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">error</span><div>Could not build preview.</div></div>';
  }
}

function setEditChip(editing) {
  const chip = document.getElementById("editStateChip");
  const btn = document.getElementById("editToggleBtn");
  chip.style.display = "inline-flex";
  if (editing) {
    chip.innerHTML = '<span class="status-dot degraded"></span>Editing. Click into the preview to change text.';
    btn.innerHTML = '<span class="material-symbols-outlined">lock</span>Lock Preview';
  } else {
    chip.innerHTML = '<span class="status-dot healthy"></span>Preview locked';
    btn.innerHTML = '<span class="material-symbols-outlined">edit</span>Edit Content';
  }
}

function toggleEditMode() {
  if (!currentIframe || !currentIframe.contentDocument) { showToast("Generate a preview first.", true); return; }
  isEditMode = !isEditMode;
  try {
    currentIframe.contentDocument.designMode = isEditMode ? "on" : "off";
  } catch (e) {
    showToast("Could not enable editing in this browser.", true);
    isEditMode = false;
  }
  setEditChip(isEditMode);
  if (isEditMode) currentIframe.contentWindow.focus();
}

function getCurrentHtml() {
  if (currentIframe && currentIframe.contentDocument && currentIframe.contentDocument.documentElement) {
    return "<!DOCTYPE html>\n" + currentIframe.contentDocument.documentElement.outerHTML;
  }
  return originalGeneratedHtml;
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("senderInput").value = getOperatorName();

  document.querySelectorAll("#reportTypeTabs .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#reportTypeTabs .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      currentReportType = tab.dataset.type;
      document.getElementById("reportTypeHint").textContent = REPORT_TYPE_HINTS[currentReportType];
    });
  });

  // Pre-select the report type tab the operator set as default in Settings.
  Api.getAppSettings().then((s) => {
    const wanted = s.default_report_type || "daily";
    const tabs = document.querySelectorAll("#reportTypeTabs .pill-tab");
    const match = Array.from(tabs).find((t) => t.dataset.type === wanted);
    if (match && wanted !== "daily") {
      tabs.forEach((t) => t.classList.remove("is-active"));
      match.classList.add("is-active");
      currentReportType = wanted;
      document.getElementById("reportTypeHint").textContent = REPORT_TYPE_HINTS[currentReportType];
    }
  }).catch(() => {});

  document.querySelectorAll("#emailTabs .pill-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#emailTabs .pill-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      const which = tab.dataset.tab;
      document.getElementById("tabPreview").style.display = which === "preview" ? "block" : "none";
      document.getElementById("tabRecords").style.display = which === "records" ? "block" : "none";
      document.getElementById("tabAutomation").style.display = which === "automation" ? "block" : "none";
      if (which === "automation") loadAutomation();
      if (which === "records" && !allIncidentsForAttach.length) loadRecordsForAttach();
    });
  });

  document.getElementById("refreshPreviewBtn").addEventListener("click", generatePreview);
  document.getElementById("editToggleBtn").addEventListener("click", toggleEditMode);

  document.getElementById("copyHtmlBtn").addEventListener("click", async () => {
    const html = getCurrentHtml();
    if (!html) { showToast("Generate a preview first.", true); return; }
    try {
      await navigator.clipboard.writeText(html);
      showToast("HTML copied to clipboard.");
    } catch (e) {
      showToast("Could not copy. Select and copy manually.", true);
    }
  });

  document.getElementById("sendBtn").addEventListener("click", async () => {
    const recipient = document.getElementById("recipientInput").value.trim();
    const sender = document.getElementById("senderInput").value.trim() || getOperatorName();
    const subject = document.getElementById("subjectInput").value.trim();
    if (!recipient) { showToast("Enter a recipient email first.", true); return; }
    if (!currentIframe) { showToast("Generate a preview first, so there's something to send.", true); return; }

    const html = getCurrentHtml();
    const btn = document.getElementById("sendBtn");
    btn.disabled = true;
    try {
      await Api.sendEmail(recipient, sender, subject, html, null, Array.from(selectedIncidentIds), currentReportType);
      showToast(`Report sent to ${recipient}.`);
    } catch (err) {
      showToast(err.message || "Could not send email. Check SMTP Settings.", true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("automationForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const settings = {
      enabled: document.getElementById("automationEnabled").checked,
      recipient: document.getElementById("autoRecipient").value.trim(),
      sender: document.getElementById("autoSender").value.trim() || getOperatorName(),
      frequency: document.getElementById("autoFrequency").value,
      time: document.getElementById("autoTime").value || "09:00",
    };
    const btn = document.getElementById("saveAutomationBtn");
    btn.disabled = true;
    try {
      await Api.saveAutomation(settings);
      showToast("Automation settings saved.");
    } catch (err) {
      showToast(err.message || "Could not save automation settings.", true);
    } finally {
      btn.disabled = false;
    }
  });
});

async function loadAutomation() {
  try {
    const settings = await Api.getAutomation();
    document.getElementById("automationEnabled").checked = !!settings.enabled;
    document.getElementById("autoRecipient").value = settings.recipient || "";
    document.getElementById("autoSender").value = settings.sender || getOperatorName();
    document.getElementById("autoFrequency").value = settings.frequency || "daily";
    document.getElementById("autoTime").value = settings.time || "09:00";
  } catch (err) {
    showToast(err.message || "Could not load automation settings.", true);
  }
}

// ---------------------------------------------------------------- attach records tab

async function loadRecordsForAttach() {
  try {
    allIncidentsForAttach = await Api.getAllIncidents(300);
    renderRecordsList();
  } catch (err) {
    showToast(err.message || "Could not load incident records.", true);
  }
}

function updateAttachSummary() {
  const chip = document.getElementById("recordsSelectedChip");
  const summary = document.getElementById("attachSummary");
  chip.textContent = `${selectedIncidentIds.size} selected`;
  summary.innerHTML = selectedIncidentIds.size
    ? `<span class="material-symbols-outlined">attach_file</span><span><strong>${selectedIncidentIds.size} incident record(s)</strong> will be attached as a CSV on the next send.</span>`
    : '<span class="material-symbols-outlined">attach_file</span><span>No incident records selected to attach. Use the <strong>Attach Records</strong> tab to pick specific ones as a CSV attachment.</span>';
}

function renderRecordsList() {
  const body = document.getElementById("recordsBody");
  const q = (document.getElementById("recordsSearchInput").value || "").toLowerCase().trim();
  const rows = allIncidentsForAttach.filter((inc) => {
    if (!q) return true;
    return (
      (inc.project_name || "").toLowerCase().includes(q) ||
      (inc.category || "").toLowerCase().includes(q) ||
      (inc.reported_by || "").toLowerCase().includes(q)
    );
  });
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-state">No incidents match.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((inc) => `
    <tr>
      <td><input type="checkbox" class="record-checkbox" data-id="${inc.id}" ${selectedIncidentIds.has(inc.id) ? "checked" : ""} style="width:16px;height:16px;"></td>
      <td class="cell-primary">${escapeHtml(inc.project_name)}</td>
      <td>${healthBadge(inc.health)}</td>
      <td>${escapeHtml(inc.severity || "Not set")}</td>
      <td class="cell-muted">${escapeHtml((inc.timestamp || "").slice(0, 16).replace("T", " "))}</td>
      <td class="cell-muted">${escapeHtml(inc.reported_by || "Not set")}</td>
    </tr>
  `).join("");
  body.querySelectorAll(".record-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) selectedIncidentIds.add(cb.dataset.id);
      else selectedIncidentIds.delete(cb.dataset.id);
      updateAttachSummary();
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("recordsSearchInput").addEventListener("input", renderRecordsList);
  document.getElementById("clearSelectionBtn").addEventListener("click", () => {
    selectedIncidentIds.clear();
    renderRecordsList();
    updateAttachSummary();
  });
});
