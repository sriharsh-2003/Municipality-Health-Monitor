/* smtp.js, SMTP Settings: load, test connection, save. */

function gatherConfig() {
  return {
    smtp_host: document.getElementById("smtpHost").value.trim(),
    smtp_port: Number(document.getElementById("smtpPort").value) || 587,
    smtp_username: document.getElementById("smtpUsername").value.trim(),
    smtp_password: document.getElementById("smtpPassword").value,
    from_address: document.getElementById("fromAddress").value.trim(),
    use_tls: document.getElementById("useTls").checked,
  };
}

async function loadSmtp() {
  try {
    const cfg = await Api.getSmtp();
    const pillWrap = document.getElementById("statusPillWrap");
    pillWrap.innerHTML = cfg.configured
      ? '<span class="chip"><span class="status-dot healthy"></span>Configured</span>'
      : '<span class="chip"><span class="status-dot down"></span>Not configured</span>';
    if (cfg.configured) {
      document.getElementById("smtpHost").value = cfg.smtp_host || "";
      document.getElementById("smtpPort").value = cfg.smtp_port || 587;
      document.getElementById("smtpUsername").value = cfg.smtp_username || "";
      document.getElementById("smtpPassword").value = cfg.smtp_password || "";
      document.getElementById("fromAddress").value = cfg.from_address || "";
      document.getElementById("useTls").checked = cfg.use_tls !== false;
    }
  } catch (err) {
    showToast(err.message || "Could not load SMTP settings.", true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadSmtp();

  document.getElementById("testBtn").addEventListener("click", async () => {
    const cfg = gatherConfig();
    if (!cfg.smtp_host || !cfg.smtp_username) { showToast("Fill in host and username first.", true); return; }
    const btn = document.getElementById("testBtn");
    btn.disabled = true;
    btn.querySelector("span:last-child") && (btn.lastChild.textContent = "Testing…");
    try {
      await Api.testSmtp(cfg);
      showToast("Connection succeeded.");
    } catch (err) {
      showToast(err.message || "Connection failed.", true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("smtpForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const cfg = gatherConfig();
    if (!cfg.smtp_host || !cfg.smtp_username) { showToast("Host and username are required.", true); return; }
    const btn = document.getElementById("saveBtn");
    btn.disabled = true;
    try {
      await Api.saveSmtp(cfg);
      showToast("SMTP settings saved.");
      loadSmtp();
    } catch (err) {
      showToast(err.message || "Could not save SMTP settings.", true);
    } finally {
      btn.disabled = false;
    }
  });
});

// ---------------------------------------------------------------- app settings

async function loadAppSettings() {
  try {
    const s = await Api.getAppSettings();
    document.getElementById("compressScreenshots").checked = s.compress_screenshots !== false;
    document.getElementById("defaultReporterName").value = s.default_reporter_name || "";
    document.getElementById("signatureTitle").value = s.email_signature_title || "";
    document.getElementById("signatureOrg").value = s.email_signature_org || "";
    document.getElementById("defaultReportType").value = s.default_report_type || "daily";
    document.getElementById("emailTagline").value = s.email_tagline || "";
  } catch (err) {
    showToast(err.message || "Could not load settings.", true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadAppSettings();

  document.getElementById("uploadPrefsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("saveUploadPrefsBtn");
    btn.disabled = true;
    try {
      await Api.saveAppSettings({ compress_screenshots: document.getElementById("compressScreenshots").checked });
      showToast("Upload preferences saved.");
    } catch (err) {
      showToast(err.message || "Could not save upload preferences.", true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("signatureForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("saveSignatureBtn");
    btn.disabled = true;
    try {
      await Api.saveAppSettings({
        default_reporter_name: document.getElementById("defaultReporterName").value.trim(),
        email_signature_title: document.getElementById("signatureTitle").value.trim(),
        email_signature_org: document.getElementById("signatureOrg").value.trim(),
      });
      showToast("Signature settings saved.");
    } catch (err) {
      showToast(err.message || "Could not save signature settings.", true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("reportDefaultsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("saveReportDefaultsBtn");
    btn.disabled = true;
    try {
      await Api.saveAppSettings({
        default_report_type: document.getElementById("defaultReportType").value,
        email_tagline: document.getElementById("emailTagline").value.trim(),
      });
      showToast("Report defaults saved.");
    } catch (err) {
      showToast(err.message || "Could not save report defaults.", true);
    } finally {
      btn.disabled = false;
    }
  });
});
