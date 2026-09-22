/* register.js — Register Platform: submit new platform onboarding form. */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("registerForm");
  const notesField = form.querySelector('[name="notes"]').closest(".field");
  const healthSelect = form.querySelector('[name="health"]');
  const notesInput = form.querySelector('[name="notes"]');

  function validateNotes() {
    const needsNotes = healthSelect.value !== "Healthy";
    if (needsNotes && !notesInput.value.trim()) {
      notesField.classList.add("has-error");
      return false;
    }
    notesField.classList.remove("has-error");
    return true;
  }
  healthSelect.addEventListener("change", validateNotes);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validateNotes()) return;
    const fd = new FormData(form);
    const platform = {};
    for (const [key, value] of fd.entries()) {
      if (["cameras_online", "cameras_total", "detections_today", "frames_processed", "latency_ms", "buffer_queue_items"].includes(key)) {
        platform[key] = Number(value) || 0;
      } else {
        platform[key] = value;
      }
    }
    const btn = document.getElementById("submitBtn");
    btn.disabled = true;
    try {
      await Api.createPlatform(platform, getOperatorName());
      showToast(`${platform.project_name} registered.`);
      setTimeout(() => { window.location.href = "/registry"; }, 500);
    } catch (err) {
      if (err.status === 409 && err.body && err.body.duplicate) {
        const existing = err.body.existing;
        const proceed = confirm(
          `A platform matching "${existing.project_name}" already exists (status: ${existing.health}).\n\n` +
          `Register this as a separate entry anyway?`
        );
        if (proceed) {
          try {
            await Api.createPlatform(platform, getOperatorName(), true);
            showToast(`${platform.project_name} registered.`);
            setTimeout(() => { window.location.href = "/registry"; }, 500);
            return;
          } catch (err2) {
            showToast(err2.message || "Could not register platform.", true);
          }
        }
        btn.disabled = false;
        return;
      }
      showToast(err.message || "Could not register platform.", true);
      btn.disabled = false;
    }
  });
});
