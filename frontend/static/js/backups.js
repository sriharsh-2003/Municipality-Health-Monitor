/* backups.js, Backups page: settings, backup now, history list. */

function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

async function loadBackupSettings() {
  try {
    const settings = await Api.getBackupSettings();
    document.getElementById("backupEnabled").checked = !!settings.enabled;
    document.getElementById("backupInterval").value = String(settings.interval_days || 7);
    const hint = document.getElementById("lastBackupHint");
    hint.textContent = settings.last_backup_at
      ? `Last backup: ${settings.last_backup_at.replace("T", " ")}`
      : "No backups yet.";
  } catch (err) {
    showToast(err.message || "Could not load backup settings.", true);
  }
}

async function loadBackupsList() {
  const body = document.getElementById("backupsBody");
  try {
    const backups = await Api.listBackups();
    if (!backups.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty-state"><span class="material-symbols-outlined">backup</span><div>No backups yet. Click "Backup Now" to make the first one.</div></td></tr>';
      return;
    }
    body.innerHTML = backups.map((b) => `
      <tr>
        <td class="cell-primary">${escapeHtml(b.filename)}</td>
        <td class="cell-muted">${escapeHtml(b.created_at.replace("T", " "))}</td>
        <td class="cell-muted">${formatBytes(b.size_bytes)}</td>
        <td><a class="btn btn-ghost btn-sm" href="/api/backups/${encodeURIComponent(b.filename)}"><span class="material-symbols-outlined">download</span>Download</a></td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(err.message || "Could not load backup history.", true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadBackupSettings();
  loadBackupsList();

  document.getElementById("backupSettingsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("saveBackupSettingsBtn");
    btn.disabled = true;
    try {
      await Api.saveBackupSettings({
        enabled: document.getElementById("backupEnabled").checked,
        interval_days: Number(document.getElementById("backupInterval").value),
      });
      showToast("Backup settings saved.");
    } catch (err) {
      showToast(err.message || "Could not save backup settings.", true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("backupNowBtn").addEventListener("click", async () => {
    const btn = document.getElementById("backupNowBtn");
    btn.disabled = true;
    try {
      const result = await Api.runBackupNow();
      showToast(`Backup created: ${result.filename}`);
      loadBackupsList();
      loadBackupSettings();
    } catch (err) {
      showToast(err.message || "Could not create a backup.", true);
    } finally {
      btn.disabled = false;
    }
  });
});
