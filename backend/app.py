"""
app.py

Run this file. It starts a local web server, serves the dashboard, and
exposes the JSON API the frontend calls. Nothing here talks to the internet
except, if you turn on automated email, to the mail server you configure.

    python app.py

Then open http://localhost:5000 in a browser.
"""

import csv
import io
import json
import os
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image

import backup as backup_module
import email_builder
import mailer
from excel_store import (
    ExcelStore, HEALTH_VALUES, SEVERITY_VALUES, INCIDENT_CATEGORIES, INCIDENT_STATUS_VALUES, STAGE_VALUES,
)
from scheduler import start_scheduler

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ATTACHMENTS_DIR = DATA_DIR / "attachments"
BACKUPS_DIR = DATA_DIR / "backups"
CONFIG_PATH = BASE_DIR / "config.json"
CONFIG_EXAMPLE_PATH = BASE_DIR / "config.example.json"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_SCREENSHOTS_PER_INCIDENT = 6
MAX_IMAGE_DIMENSION = 1600  # long edge, px, stays comfortably readable while cutting file size a lot

app = Flask(
    __name__,
    template_folder=str(PROJECT_DIR / "frontend" / "templates"),
    static_folder=str(PROJECT_DIR / "frontend" / "static"),
)
CORS(app)  # harmless locally, and means a separately hosted Stitch export can call this API too

store = ExcelStore(DATA_DIR / "platform_health.xlsx", DATA_DIR / "app_state.json")
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def _allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _save_screenshot(file_storage, dest_path):
    """Respects the compress_screenshots app setting, compress (resized +
    re-encoded, still clearly readable) or save the original bytes untouched."""
    if store.get_app_settings().get("compress_screenshots", True):
        _compress_and_save_image(file_storage, dest_path)
    else:
        file_storage.stream.seek(0)
        file_storage.save(dest_path)


def _compress_and_save_image(file_storage, dest_path):
    """Resizes to a max dimension and re-encodes with reasonable compression,
    while keeping the image clearly readable (screenshots are usually text
    or UI, not photography, so a fairly high quality setting is used)."""
    try:
        img = Image.open(file_storage.stream)
        img_format = (img.format or "PNG").upper()
        if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
        if img_format in ("JPEG", "JPG"):
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dest_path, format="JPEG", quality=85, optimize=True)
        elif img_format == "WEBP":
            img.save(dest_path, format="WEBP", quality=85, method=6)
        else:
            # PNG/GIF and anything else, keep lossless so text stays crisp.
            if img.mode not in ("RGB", "RGBA", "P"):
                img = img.convert("RGBA")
            img.save(dest_path, format="PNG", optimize=True)
        return True
    except Exception:
        # Not a readable image (or an unsupported format), fall back to
        # saving the original bytes untouched rather than losing the upload.
        file_storage.stream.seek(0)
        file_storage.save(dest_path)
        return False


def get_smtp_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "backend/config.json not found. Copy backend/config.example.json to backend/config.json "
            "and fill in your mail server details."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(PROJECT_DIR / "frontend" / "static", "favicon.ico")


# --------------------------------------------------------------------- pages

@app.route("/")
def page_overview():
    return render_template("overview.html", active="overview")


@app.route("/registry")
def page_registry():
    return render_template("registry.html", active="registry", edit_id=request.args.get("id", ""))


@app.route("/audit")
def page_audit():
    return render_template(
        "audit.html", active="audit",
        severities=SEVERITY_VALUES, categories=INCIDENT_CATEGORIES, statuses=INCIDENT_STATUS_VALUES,
    )


@app.route("/register")
def page_register():
    return render_template("register.html", active="register")


@app.route("/incident")
def page_incident():
    return render_template(
        "incident.html", active="incident",
        platform_id=request.args.get("platform", ""),
        severities=SEVERITY_VALUES, categories=INCIDENT_CATEGORIES,
    )


@app.route("/platform/<platform_id>")
def page_platform_detail(platform_id):
    return render_template("platform_detail.html", active="registry", platform_id=platform_id)


@app.route("/email")
def page_email():
    return render_template("email.html", active="email")


@app.route("/smtp-settings")
def page_smtp_settings():
    return render_template("smtp.html", active="smtp")


@app.route("/backups")
def page_backups():
    return render_template("backups.html", active="backups")


# ---------------------------------------------------------------- platforms

@app.route("/api/platforms", methods=["GET"])
def api_list_platforms():
    return jsonify(store.list_platforms())


@app.route("/api/platforms/<platform_id>", methods=["GET"])
def api_get_platform(platform_id):
    platform = store.get_platform(platform_id)
    if not platform:
        return jsonify({"error": "not found"}), 404
    return jsonify(platform)


@app.route("/api/platforms", methods=["POST"])
def api_create_platform():
    body = request.get_json(force=True)
    changed_by = body.get("changed_by", "Reporter")
    record = body.get("platform", {})
    force = bool(body.get("force"))
    if not record.get("project_name"):
        return jsonify({"error": "project_name is required"}), 400
    if record.get("health") not in HEALTH_VALUES:
        record["health"] = "Healthy"
    if record.get("health") != "Healthy" and not record.get("notes"):
        return jsonify({"error": "notes are required when status is not Healthy"}), 400
    if record.get("stage") and record["stage"] not in STAGE_VALUES:
        return jsonify({"error": "invalid stage value"}), 400
    if not record.get("stage"):
        record["stage"] = "Running"

    if not force:
        dup = store.find_duplicate_platform(record.get("project_name"), record.get("url", ""))
        if dup:
            return jsonify({
                "duplicate": True,
                "existing": dup,
                "error": f"A platform matching \"{dup.get('project_name')}\" already exists.",
            }), 409

    summary = store.save_platforms([record], changed_by)
    return jsonify({"ok": True, "summary": summary})


@app.route("/api/platforms/<platform_id>", methods=["PUT"])
def api_update_platform(platform_id):
    body = request.get_json(force=True)
    changed_by = body.get("changed_by", "Reporter")
    record = body.get("platform", {})
    record["id"] = platform_id
    if record.get("health") and record.get("health") not in HEALTH_VALUES:
        return jsonify({"error": "invalid health value"}), 400
    if record.get("health") == "Degraded" or record.get("health") == "Down":
        if "notes" in record and not record.get("notes"):
            return jsonify({"error": "notes are required when status is not Healthy"}), 400
    if record.get("stage") and record["stage"] not in STAGE_VALUES:
        return jsonify({"error": "invalid stage value"}), 400
    summary = store.save_platforms([record], changed_by)
    return jsonify({"ok": True, "summary": summary})


@app.route("/api/platforms/bulk", methods=["PUT"])
def api_bulk_update_platforms():
    body = request.get_json(force=True)
    changed_by = body.get("changed_by", "Reporter")
    updates = body.get("updates", [])
    for record in updates:
        if record.get("health") in ("Degraded", "Down") and not record.get("notes"):
            return jsonify({"error": f"notes are required for {record.get('project_name', record.get('id'))} because status is not Healthy"}), 400
    summary = store.save_platforms(updates, changed_by)
    return jsonify({"ok": True, "summary": summary})


@app.route("/api/platforms/<platform_id>", methods=["DELETE"])
def api_delete_platform(platform_id):
    changed_by = request.args.get("changed_by", "Reporter")
    summary = store.delete_platform(platform_id, changed_by)
    return jsonify({"ok": True, "summary": summary})


# ------------------------------------------------------------- incidents

@app.route("/api/incident-options")
def api_incident_options():
    return jsonify({"severities": SEVERITY_VALUES, "categories": INCIDENT_CATEGORIES, "statuses": INCIDENT_STATUS_VALUES})


@app.route("/api/platforms/<platform_id>/incidents", methods=["POST"])
def api_create_incident(platform_id):
    """
    multipart/form-data: health, notes, last_detection, severity, category,
    affected_component, resolution_notes, eta, changed_by, occurred_at
    (optional 'YYYY-MM-DDTHH:MM', defaults to now when omitted), and 0+
    files under the field name "screenshots".
    """
    if not store.get_platform(platform_id):
        return jsonify({"error": "platform not found"}), 404

    form = request.form
    changed_by = form.get("changed_by") or "Reporter"
    health = form.get("health", "")
    notes = form.get("notes", "")

    if health and health not in HEALTH_VALUES:
        return jsonify({"error": "invalid health value"}), 400
    if health and health != "Healthy" and not notes:
        return jsonify({"error": "notes are required when status is not Healthy"}), 400

    occurred_at = form.get("occurred_at", "").strip()
    timestamp = None
    if occurred_at:
        try:
            timestamp = datetime.fromisoformat(occurred_at).isoformat(timespec="seconds")
        except ValueError:
            return jsonify({"error": "occurred_at must be a valid date/time"}), 400

    incident = {
        "health": health,
        "notes": notes,
        "last_detection": form.get("last_detection", ""),
        "severity": form.get("severity", ""),
        "category": form.get("category", ""),
        "affected_component": form.get("affected_component", ""),
        "resolution_notes": form.get("resolution_notes", ""),
        "eta": form.get("eta", ""),
        "status": form.get("status") or "Open",
        "screenshots": [],
    }

    # Files are saved under a folder keyed by a fresh incident id, minted
    # here and reused as the actual incident id passed into the store.
    incident_id = "inc_" + str(int(time.time() * 1000))[-10:]
    files = request.files.getlist("screenshots")[:MAX_SCREENSHOTS_PER_INCIDENT]
    saved_names = []
    if files:
        folder = ATTACHMENTS_DIR / incident_id
        folder.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(files):
            if not f or not f.filename:
                continue
            if not _allowed_image(f.filename):
                continue
            safe_name = secure_filename(f.filename) or f"screenshot_{i}.png"
            stored_name = f"{i}_{safe_name}"
            _save_screenshot(f, folder / stored_name)
            saved_names.append(stored_name)
    incident["screenshots"] = saved_names

    try:
        result = store.create_incident(platform_id, incident, changed_by, forced_id=incident_id, timestamp=timestamp)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True, **result})


@app.route("/api/incidents")
def api_list_incidents():
    platform_id = request.args.get("platform_id") or None
    limit = int(request.args.get("limit", 200))
    return jsonify(store.list_incidents(platform_id=platform_id, limit=limit))


@app.route("/api/incidents/<incident_id>")
def api_get_incident(incident_id):
    incident = store.get_incident(incident_id)
    if not incident:
        return jsonify({"error": "not found"}), 404
    return jsonify(incident)


@app.route("/api/incidents/<incident_id>", methods=["PUT"])
def api_update_incident(incident_id):
    """
    Corrects a past incident record, for example, fixing a typo or a wrong
    severity after the fact. multipart/form-data with any of: severity,
    category, affected_component, health, notes, resolution_notes, eta,
    status, occurred_at (renames the record's timestamp), changed_by,
    remove_screenshots (comma-separated filenames to delete), and 0+ new
    files under "screenshots" to add alongside what's already attached.
    """
    existing = store.get_incident(incident_id)
    if not existing:
        return jsonify({"error": "not found"}), 404

    form = request.form
    changed_by = form.get("changed_by") or "Reporter"
    updates = {}
    for field in ("severity", "category", "affected_component", "health", "notes", "resolution_notes", "eta", "status"):
        if field in form:
            updates[field] = form.get(field)

    if updates.get("health") and updates["health"] not in HEALTH_VALUES:
        return jsonify({"error": "invalid health value"}), 400
    if updates.get("status") and updates["status"] not in INCIDENT_STATUS_VALUES:
        return jsonify({"error": "invalid status value"}), 400

    occurred_at = form.get("occurred_at", "").strip()
    if occurred_at:
        try:
            updates["timestamp"] = datetime.fromisoformat(occurred_at).isoformat(timespec="seconds")
        except ValueError:
            return jsonify({"error": "occurred_at must be a valid date/time"}), 400

    screenshots = list(existing.get("screenshots") or [])
    remove_list = [s for s in form.get("remove_screenshots", "").split(",") if s]
    folder = ATTACHMENTS_DIR / incident_id
    for name in remove_list:
        if name in screenshots:
            screenshots.remove(name)
            try:
                (folder / secure_filename(name)).unlink(missing_ok=True)
            except Exception:
                pass

    new_files = request.files.getlist("screenshots")
    if new_files:
        room = MAX_SCREENSHOTS_PER_INCIDENT - len(screenshots)
        folder.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(new_files[:max(room, 0)]):
            if not f or not f.filename or not _allowed_image(f.filename):
                continue
            safe_name = secure_filename(f.filename) or f"screenshot_{i}.png"
            stored_name = f"e{int(time.time()*1000)}_{i}_{safe_name}"
            _save_screenshot(f, folder / stored_name)
            screenshots.append(stored_name)
    updates["screenshots"] = screenshots

    try:
        updated = store.update_incident(incident_id, updates, changed_by)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True, "incident": updated})


@app.route("/attachments/<incident_id>/<path:filename>")
def serve_attachment(incident_id, filename):
    folder = ATTACHMENTS_DIR / secure_filename(incident_id)
    if not folder.exists():
        abort(404)
    return send_from_directory(folder, filename)


# ------------------------------------------------------------- csv export

INCIDENT_CSV_COLUMNS = [
    "id", "platform_id", "project_name", "timestamp", "reported_by", "status",
    "severity", "category", "affected_component", "health", "notes",
    "resolution_notes", "eta", "screenshot_count",
]


def _incidents_to_csv(incidents):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=INCIDENT_CSV_COLUMNS)
    writer.writeheader()
    for inc in incidents:
        row = {k: inc.get(k, "") for k in INCIDENT_CSV_COLUMNS}
        row["screenshot_count"] = len(inc.get("screenshots") or [])
        writer.writerow(row)
    return buf.getvalue()


@app.route("/api/incidents/export.csv")
def api_export_incidents_csv():
    ids_param = request.args.get("ids", "")
    platform_id = request.args.get("platform_id") or None
    if ids_param:
        wanted = set(ids_param.split(","))
        incidents = [i for i in store.list_incidents(limit=100000) if i["id"] in wanted]
    else:
        incidents = store.list_incidents(platform_id=platform_id, limit=100000)
    csv_text = _incidents_to_csv(incidents)
    return app.response_class(
        csv_text, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidents-export.csv"},
    )


# --------------------------------------------------------------------- logs

@app.route("/api/logs")
def api_logs():
    limit = int(request.args.get("limit", 200))
    return jsonify(store.list_logs(limit=limit))


@app.route("/api/summary")
def api_summary():
    return jsonify(store.summary())


# ------------------------------------------------------------------ charts

@app.route("/api/charts/health-trend")
def api_health_trend():
    limit = int(request.args.get("limit", 20))
    return jsonify(store.list_snapshots(limit=limit))


@app.route("/api/charts/metrics")
def api_metrics():
    platforms = store.list_platforms()
    return jsonify([
        {
            "project_name": p["project_name"],
            "detections_today": p.get("detections_today") or 0,
            "frames_processed": p.get("frames_processed") or 0,
            "latency_ms": p.get("latency_ms") or 0,
            "cameras_online": p.get("cameras_online") or 0,
            "cameras_total": p.get("cameras_total") or 0,
            "health": p.get("health"),
        }
        for p in platforms
    ])


RANGE_PRESETS = {
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "12m": timedelta(days=365),
}


def _resolve_range(range_key, start_param, end_param):
    now = datetime.now()
    if range_key == "all":
        return None, now
    if range_key == "custom":
        try:
            start = datetime.fromisoformat(start_param) if start_param else None
            end = datetime.fromisoformat(end_param) if end_param else now
        except ValueError:
            start, end = None, now
        return start, end
    if range_key == "today":
        # Calendar-day start (midnight), not "24 hours ago". A rolling
        # 24-hour window drifts across the day boundary, e.g. checking at
        # 11pm would show mostly yesterday and miss most of today.
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    delta = RANGE_PRESETS.get(range_key, RANGE_PRESETS["7d"])
    return now - delta, now


def _rollup_daily(snapshots):
    """Collapses every action-level snapshot down to one point per calendar
    day, using the last snapshot of that day (its end-of-day state), sorted
    oldest to newest. A trend chart with one action per data point looks
    noisy and jagged the moment more than a few actions happen in a day;
    a daily line reads the way "trend" actually implies."""
    by_day = {}
    for s in snapshots:
        ts = s.get("timestamp", "")
        day_key = ts[:10] if ts else ""
        if not day_key:
            continue
        # Snapshots already come out oldest-first from list_snapshots, so
        # the last one seen per day is naturally that day's final state.
        by_day[day_key] = s
    days = sorted(by_day.keys())
    rolled = []
    for day in days[-90:]:  # a 90-day cap keeps "All Time" legible on very old datasets
        s = dict(by_day[day])
        s["timestamp"] = day
        rolled.append(s)
    return rolled


@app.route("/api/dashboard")
def api_dashboard():
    """
    Everything the Dashboard Overview page needs for a given time window, in
    one call. Current-status counts (healthy/warning/critical/total) are
    live for every preset range, since every preset (Today, Week, Month,
    Year, All Time) runs up to right now, so "status as of the end of the
    range" and "status right now" are the same thing, a platform only has
    one status at a time. The one case where that's not true is a Custom
    range with an end date in the past: there, the KPI tiles and the
    Status Split donut instead use the last recorded snapshot at or before
    that end date, so picking a historical window shows what was actually
    true then rather than silently showing today's live numbers.
    """
    range_key = request.args.get("range", "7d")
    start, end = _resolve_range(range_key, request.args.get("start"), request.args.get("end"))
    now = datetime.now()

    all_snapshots = store.list_snapshots(limit=100000)
    snapshots = all_snapshots
    if start:
        snapshots = [s for s in snapshots if s.get("timestamp", "") >= start.isoformat()]
    if end:
        snapshots = [s for s in snapshots if s.get("timestamp", "") <= end.isoformat()]
    trend = _rollup_daily(snapshots)

    is_historical_end = end is not None and (now - end).total_seconds() > 60
    if is_historical_end:
        as_of = [s for s in all_snapshots if s.get("timestamp", "") <= end.isoformat()]
        current = (
            {"total": as_of[-1]["total"], "healthy": as_of[-1]["healthy"], "warning": as_of[-1]["warning"], "critical": as_of[-1]["critical"], "cycle": as_of[-1].get("cycle")}
            if as_of else store.summary()
        )
    else:
        current = store.summary()

    incidents = store.list_incidents(limit=100000)
    if start:
        incidents = [i for i in incidents if i.get("timestamp", "") >= start.isoformat()]
    if end:
        incidents = [i for i in incidents if i.get("timestamp", "") <= end.isoformat()]
    incidents.sort(key=lambda i: i.get("timestamp", ""), reverse=True)

    critical_in_range = sum(1 for i in incidents if i.get("severity") == "Critical" or i.get("health") == "Down")

    # "Still open" is a live operational backlog count, independent of the
    # selected range, since an old unresolved incident should not vanish
    # from the count just because the person is looking at "This Week".
    all_incidents = store.list_incidents(limit=100000)
    open_incidents_total = sum(1 for i in all_incidents if (i.get("status") or "Open") in ("Open", "Acknowledged", "In Progress"))

    return jsonify({
        "range": {
            "key": range_key,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
        "current": current,
        "trend": trend,
        "incidents_in_range": len(incidents),
        "critical_incidents_in_range": critical_in_range,
        "open_incidents_total": open_incidents_total,
        "recent_incidents": incidents[:8],
    })


# ------------------------------------------------------------------- email

def _report_range_and_label(report_type, now=None):
    """Returns (start_iso, period_label) for a report type. end is always
    now, since a report always covers up to the moment it's built."""
    now = now or datetime.now()
    if report_type == "weekly":
        start = now - timedelta(days=7)
        label = f"{start.strftime('%d %b')} to {now.strftime('%d %b %Y')}"
    elif report_type == "monthly":
        start = now - timedelta(days=30)
        label = now.strftime("%B %Y")
    else:
        report_type = "daily"
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = now.strftime("%A, %d %b %Y")
    return start, label


def _incidents_for_report(report_type):
    start, period_label = _report_range_and_label(report_type)
    incidents = [i for i in store.list_incidents(limit=100000) if i.get("timestamp", "") >= start.isoformat()]
    incidents.sort(key=lambda i: i.get("timestamp", ""), reverse=True)
    return incidents, period_label


@app.route("/api/email/preview")
def api_email_preview():
    sender = request.args.get("sender", "Reporter")
    recipient = request.args.get("recipient", "Manager")
    report_type = request.args.get("report_type", "daily")
    settings = store.get_app_settings()
    # Under Development platforms aren't live yet, so they're left out of
    # the client-facing report entirely rather than shown as an extra
    # status row that isn't meaningful yet.
    platforms = [p for p in store.list_platforms() if p.get("stage", "Running") == "Running"]
    incidents, period_label = _incidents_for_report(report_type)
    built = email_builder.build_email(
        platforms, incidents=incidents, report_type=report_type, period_label=period_label,
        sender_name=sender, recipient_name=recipient, base_url=request.host_url.rstrip("/"),
        sender_title=settings.get("email_signature_title", ""), sender_org=settings.get("email_signature_org", ""),
        tagline=settings.get("email_tagline", ""),
    )
    return jsonify(built)


@app.route("/api/email/send", methods=["POST"])
def api_email_send():
    body = request.get_json(force=True)
    recipient = body.get("recipient")
    sender = body.get("sender", "Reporter")
    report_type = body.get("report_type", "daily")
    subject = (body.get("subject") or "").strip() or f"Municipality Digital Operations, {email_builder.REPORT_TITLES.get(report_type, 'Status Update')}"
    custom_html = body.get("html")
    attach_incident_ids = body.get("attach_incident_ids") or []
    if not recipient:
        return jsonify({"error": "recipient is required"}), 400

    if custom_html:
        # The reporter edited the generated preview by hand, send exactly
        # what they left in the editor, rather than rebuilding from live data.
        html = custom_html
        text = body.get("text") or email_builder.html_to_text(custom_html)
    else:
        settings = store.get_app_settings()
        platforms = [p for p in store.list_platforms() if p.get("stage", "Running") == "Running"]
        incidents, period_label = _incidents_for_report(report_type)
        built = email_builder.build_email(
            platforms, incidents=incidents, report_type=report_type, period_label=period_label,
            sender_name=sender, recipient_name=recipient, base_url=request.host_url.rstrip("/"),
            sender_title=settings.get("email_signature_title", ""), sender_org=settings.get("email_signature_org", ""),
            tagline=settings.get("email_tagline", ""),
        )
        html, text = built["html"], built["text"]

    extra_attachments = []
    if attach_incident_ids:
        wanted = set(attach_incident_ids)
        selected = [i for i in store.list_incidents(limit=100000) if i["id"] in wanted]
        if selected:
            csv_text = _incidents_to_csv(selected)
            extra_attachments.append(("selected-incidents.csv", csv_text.encode("utf-8"), "csv"))

    try:
        smtp_config = get_smtp_config()
        with open(store.xlsx_path, "rb") as f:
            attachment = f.read()
        mailer.send_email(
            smtp_config, recipient, subject,
            html, text, attachment_bytes=attachment, attachment_name="platform-health-export.xlsx",
            extra_attachments=extra_attachments,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True})


# -------------------------------------------------------------- automation

@app.route("/api/automation", methods=["GET"])
def api_get_automation():
    return jsonify(store.get_automation_settings())


@app.route("/api/automation", methods=["POST"])
def api_save_automation():
    body = request.get_json(force=True)
    store.save_automation_settings(body)
    return jsonify({"ok": True})


# --------------------------------------------------------------- backups

@app.route("/api/backup-settings", methods=["GET"])
def api_get_backup_settings():
    settings = store.get_backup_settings()
    settings["last_backup_at"] = store.get_last_backup_at()
    return jsonify(settings)


@app.route("/api/backup-settings", methods=["POST"])
def api_save_backup_settings():
    body = request.get_json(force=True)
    store.save_backup_settings({
        "enabled": bool(body.get("enabled")),
        "interval_days": int(body.get("interval_days") or 7),
    })
    return jsonify({"ok": True})


@app.route("/api/backups", methods=["GET"])
def api_list_backups():
    return jsonify(backup_module.list_backups(BACKUPS_DIR))


@app.route("/api/backups/run", methods=["POST"])
def api_run_backup():
    dest = backup_module.create_backup(store.xlsx_path, ATTACHMENTS_DIR, BACKUPS_DIR)
    backup_module.prune_old_backups(BACKUPS_DIR, keep=30)
    store.set_last_backup_at(datetime.now().isoformat(timespec="seconds"))
    return jsonify({"ok": True, "filename": dest.name})


@app.route("/api/backups/<filename>")
def api_download_backup(filename):
    safe_name = secure_filename(filename)
    path = BACKUPS_DIR / safe_name
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=safe_name)


# ------------------------------------------------------------------ export

@app.route("/api/export")
def api_export():
    if not store.xlsx_path.exists():
        abort(404)
    return send_file(store.xlsx_path, as_attachment=True, download_name="platform-health-export.xlsx")


# -------------------------------------------------------------------- misc

@app.route("/api/config-status")
def api_config_status():
    return jsonify({"smtp_configured": CONFIG_PATH.exists()})


@app.route("/api/app-settings", methods=["GET"])
def api_get_app_settings():
    return jsonify(store.get_app_settings())


@app.route("/api/app-settings", methods=["POST"])
def api_save_app_settings():
    body = request.get_json(force=True)
    allowed = {"compress_screenshots", "default_reporter_name", "email_signature_name",
               "email_signature_title", "email_signature_org", "default_report_type", "email_tagline"}
    settings = {k: v for k, v in body.items() if k in allowed}
    store.save_app_settings(settings)
    return jsonify({"ok": True})


# --------------------------------------------------------------------- smtp

@app.route("/api/smtp", methods=["GET"])
def api_get_smtp():
    if not CONFIG_PATH.exists():
        return jsonify({"configured": False})
    cfg = get_smtp_config()
    return jsonify({
        "configured": True,
        "smtp_host": cfg.get("smtp_host", ""),
        "smtp_port": cfg.get("smtp_port", 587),
        "smtp_username": cfg.get("smtp_username", ""),
        "smtp_password": "" if not cfg.get("smtp_password") else "••••••••",
        "use_tls": cfg.get("use_tls", True),
        "from_address": cfg.get("from_address", ""),
    })


@app.route("/api/smtp", methods=["POST"])
def api_save_smtp():
    body = request.get_json(force=True)
    existing = {}
    if CONFIG_PATH.exists():
        existing = get_smtp_config()
    password = body.get("smtp_password", "")
    if password == "••••••••" or password == "":
        password = existing.get("smtp_password", "")
    cfg = {
        "smtp_host": body.get("smtp_host", ""),
        "smtp_port": int(body.get("smtp_port") or 587),
        "smtp_username": body.get("smtp_username", ""),
        "smtp_password": password,
        "use_tls": bool(body.get("use_tls", True)),
        "from_address": body.get("from_address") or body.get("smtp_username", ""),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return jsonify({"ok": True})


@app.route("/api/smtp/test", methods=["POST"])
def api_test_smtp():
    body = request.get_json(force=True)
    existing = {}
    if CONFIG_PATH.exists():
        existing = get_smtp_config()
    password = body.get("smtp_password", "")
    if password == "••••••••" or password == "":
        password = existing.get("smtp_password", "")
    cfg = {
        "smtp_host": body.get("smtp_host", ""),
        "smtp_port": int(body.get("smtp_port") or 587),
        "smtp_username": body.get("smtp_username", ""),
        "smtp_password": password,
        "use_tls": bool(body.get("use_tls", True)),
    }
    if not cfg["smtp_host"] or not cfg["smtp_username"] or not cfg["smtp_password"]:
        return jsonify({"ok": False, "error": "Host, username, and password are all required to test the connection."}), 400
    try:
        import smtplib
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
            if cfg["use_tls"]:
                server.starttls()
            server.login(cfg["smtp_username"], cfg["smtp_password"])
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def _open_browser():
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    if not CONFIG_PATH.exists() and CONFIG_EXAMPLE_PATH.exists():
        print("Note: backend/config.json does not exist yet. Copy backend/config.example.json to "
              "backend/config.json and fill in your mail server details before using automated email.")
    start_scheduler(store, get_smtp_config, xlsx_path=store.xlsx_path, attachments_dir=ATTACHMENTS_DIR, backups_dir=BACKUPS_DIR)
    Timer(1.0, _open_browser).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
