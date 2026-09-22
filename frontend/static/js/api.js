/*
 * api.js
 * Thin fetch wrappers around the Flask API. Every page includes this file
 * before its own page script.
 */

const Api = (() => {
  async function request(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let body = null;
    try {
      body = await res.json();
    } catch (e) {
      body = null;
    }
    if (!res.ok) {
      const message = (body && body.error) || `Request to ${path} failed (${res.status}).`;
      const err = new Error(message);
      err.body = body;
      err.status = res.status;
      throw err;
    }
    return body;
  }

  // For multipart/form-data (file uploads), do NOT set Content-Type
  // manually, the browser needs to add its own multipart boundary.
  async function requestForm(path, formData, method = "POST") {
    const res = await fetch(path, { method, body: formData });
    let body = null;
    try {
      body = await res.json();
    } catch (e) {
      body = null;
    }
    if (!res.ok) {
      const message = (body && body.error) || `Request to ${path} failed (${res.status}).`;
      const err = new Error(message);
      err.body = body;
      err.status = res.status;
      throw err;
    }
    return body;
  }

  return {
    getPlatforms: () => request("/api/platforms"),
    getPlatform: (id) => request(`/api/platforms/${encodeURIComponent(id)}`),
    createPlatform: (platform, changedBy, force = false) =>
      request("/api/platforms", { method: "POST", body: JSON.stringify({ platform, changed_by: changedBy, force }) }),
    updatePlatform: (id, platform, changedBy) =>
      request(`/api/platforms/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ platform, changed_by: changedBy }) }),
    bulkUpdatePlatforms: (updates, changedBy) =>
      request("/api/platforms/bulk", { method: "PUT", body: JSON.stringify({ updates, changed_by: changedBy }) }),
    deletePlatform: (id, changedBy) =>
      request(`/api/platforms/${encodeURIComponent(id)}?changed_by=${encodeURIComponent(changedBy)}`, { method: "DELETE" }),

    getLogs: (limit = 200) => request(`/api/logs?limit=${limit}`),
    getSummary: () => request("/api/summary"),

    getHealthTrend: (limit = 20) => request(`/api/charts/health-trend?limit=${limit}`),
    getMetrics: () => request("/api/charts/metrics"),

    getEmailPreview: (sender, recipient) =>
      request(`/api/email/preview?sender=${encodeURIComponent(sender)}&recipient=${encodeURIComponent(recipient)}`),
    sendEmail: (recipient, sender, subject, html, text, attachIncidentIds) =>
      request("/api/email/send", { method: "POST", body: JSON.stringify({ recipient, sender, subject, html, text, attach_incident_ids: attachIncidentIds || [] }) }),

    getAutomation: () => request("/api/automation"),
    saveAutomation: (settings) => request("/api/automation", { method: "POST", body: JSON.stringify(settings) }),

    getSmtp: () => request("/api/smtp"),
    saveSmtp: (config) => request("/api/smtp", { method: "POST", body: JSON.stringify(config) }),
    testSmtp: (config) => request("/api/smtp/test", { method: "POST", body: JSON.stringify(config) }),

    getAppSettings: () => request("/api/app-settings"),
    saveAppSettings: (settings) => request("/api/app-settings", { method: "POST", body: JSON.stringify(settings) }),

    // ---- incidents (with optional screenshot attachments) ----
    createIncident: (platformId, formData) =>
      requestForm(`/api/platforms/${encodeURIComponent(platformId)}/incidents`, formData),
    updateIncident: (incidentId, formData) =>
      requestForm(`/api/incidents/${encodeURIComponent(incidentId)}`, formData, "PUT"),
    getIncidents: (platformId, limit = 200) =>
      request(`/api/incidents?platform_id=${encodeURIComponent(platformId)}&limit=${limit}`),
    getAllIncidents: (limit = 200) => request(`/api/incidents?limit=${limit}`),
    getIncidentOptions: () => request("/api/incident-options"),
    incidentsCsvUrl: (ids) => ids && ids.length ? `/api/incidents/export.csv?ids=${ids.join(",")}` : "/api/incidents/export.csv",

    // ---- backups ----
    getBackupSettings: () => request("/api/backup-settings"),
    saveBackupSettings: (settings) => request("/api/backup-settings", { method: "POST", body: JSON.stringify(settings) }),
    listBackups: () => request("/api/backups"),
    runBackupNow: () => request("/api/backups/run", { method: "POST" }),
  };
})();

function getOperatorRole() {
  return localStorage.getItem("operatorRole") || "Operator";
}

function setOperatorRole(role) {
  localStorage.setItem("operatorRole", role);
}

function getOperatorDisplayName() {
  return localStorage.getItem("operatorDisplayName") || "";
}

function getOperatorName() {
  const role = getOperatorRole();
  const name = getOperatorDisplayName();
  return name ? `${name} (${role})` : role;
}

function setOperatorName(name) {
  localStorage.setItem("operatorDisplayName", name);
}
