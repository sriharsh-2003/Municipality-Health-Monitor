"""
excel_store.py

The whole "database" for this app is one Excel workbook (data/platform_health.xlsx),
so the client can open it directly in Excel if they ever want to. Three sheets:

  Platforms   - current state of each monitored platform (one row each)
  Logs        - field-level audit trail: who changed what, from what, to what, when
  Snapshots   - one row per save cycle, with the healthy/warning/critical counts
                at that moment, which is what feeds the trend chart

There is no real database engine here on purpose. openpyxl reads and rewrites
the whole file on every save, which is plenty fast for a few dozen platforms
checked a few times a day, and it means the data is always in a format a
human can open without this app.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

PLATFORM_FIELDS = [
    "id", "project_name", "url", "assigned_operator", "last_visit", "health",
    "last_detection", "notes", "needs_confirmation",
    "detections_today", "frames_processed", "cameras_online", "cameras_total",
    "latency_ms", "buffer_queue_items", "updated_at",
]

INCIDENT_FIELDS = [
    "id", "platform_id", "project_name", "cycle", "timestamp", "reported_by",
    "severity", "category", "affected_component", "health", "notes",
    "resolution_notes", "eta", "screenshots", "status", "edited_at", "edited_by",
]

SEVERITY_VALUES = ["Low", "Medium", "High", "Critical"]
INCIDENT_CATEGORIES = [
    "Camera / Sensor Outage", "Network Connectivity", "Software / Application Error",
    "Hardware Failure", "Power Outage", "Data Quality Issue", "Scheduled Maintenance", "Other",
]
INCIDENT_STATUS_VALUES = ["Open", "Acknowledged", "In Progress", "Resolved"]

# Fields a normal daily check touches. Everything else in PLATFORM_FIELDS is
# still editable through the full platform form, just not through the quick
# inline table edit.
QUICK_EDIT_FIELDS = ["project_name", "url", "assigned_operator", "last_visit", "health", "last_detection", "notes"]

HEALTH_VALUES = ["Healthy", "Degraded", "Down"]

_lock = threading.Lock()


def _seed_platforms():
    now = datetime.now().strftime("%d %b %H:%M")
    return [
        {"id": "p_auto_detect", "project_name": "Auto Detection Platform", "url": "https://adp.municipality.gov.local",
         "assigned_operator": "A. Al-Mansoor", "last_visit": now, "health": "Healthy", "last_detection": now,
         "notes": "", "needs_confirmation": False,
         "detections_today": 14820, "frames_processed": 89400, "cameras_online": 36, "cameras_total": 48,
         "latency_ms": 18, "buffer_queue_items": 0, "updated_at": now},
        {"id": "p_smart_gate", "project_name": "Smart Gate Platform", "url": "https://gate-ops.municipality.gov.local",
         "assigned_operator": "K. Al-Zahrani", "last_visit": now, "health": "Healthy", "last_detection": now,
         "notes": "", "needs_confirmation": False,
         "detections_today": 6430, "frames_processed": 34120, "cameras_online": 12, "cameras_total": 12,
         "latency_ms": 22, "buffer_queue_items": 0, "updated_at": now},
        {"id": "p_rrm", "project_name": "RRM Portal", "url": "https://rrm.municipality.gov.local",
         "assigned_operator": "S. Al-Otaibi", "last_visit": now, "health": "Degraded", "last_detection": "Yesterday, 22:15",
         "notes": "No new images since last night.", "needs_confirmation": False,
         "detections_today": 1120, "frames_processed": 8940, "cameras_online": 9, "cameras_total": 12,
         "latency_ms": 64, "buffer_queue_items": 1420, "updated_at": now},
        {"id": "p_hmm", "project_name": "HMM Portal", "url": "https://hmm.municipality.gov.local",
         "assigned_operator": "M. Farhan", "last_visit": now, "health": "Healthy", "last_detection": now,
         "notes": "", "needs_confirmation": False,
         "detections_today": 3890, "frames_processed": 19200, "cameras_online": 8, "cameras_total": 8,
         "latency_ms": 26, "buffer_queue_items": 0, "updated_at": now},
        {"id": "p_urban_eye", "project_name": "Urban Eye Platform", "url": "https://urbaneye.municipality.gov.local",
         "assigned_operator": "T. Al-Harbi", "last_visit": now, "health": "Down", "last_detection": "N/A",
         "notes": "Page not loading, error 500. Flagged to the platform owner.", "needs_confirmation": False,
         "detections_today": 0, "frames_processed": 1420, "cameras_online": 0, "cameras_total": 12,
         "latency_ms": 0, "buffer_queue_items": 0, "updated_at": now},
        {"id": "p_urben_eye", "project_name": "Urben Eye Platform", "url": "https://urbeneye.municipality.gov.local",
         "assigned_operator": "T. Al-Harbi", "last_visit": now, "health": "Healthy", "last_detection": now,
         "notes": "", "needs_confirmation": True,
         "detections_today": 2210, "frames_processed": 11200, "cameras_online": 6, "cameras_total": 6,
         "latency_ms": 20, "buffer_queue_items": 0, "updated_at": now},
    ]


class ExcelStore:
    def __init__(self, xlsx_path, state_path):
        self.xlsx_path = Path(xlsx_path)
        self.state_path = Path(state_path)
        self.xlsx_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.xlsx_path.exists():
            self._create_workbook(_seed_platforms())
        else:
            self._migrate_schema()
        if not self.state_path.exists():
            self._write_state({"cycle": 0, "automation": {}, "last_automated_send": None})

    # ---------------------------------------------------------------- state
    def _read_state(self):
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_state(self, state):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def get_automation_settings(self):
        return self._read_state().get("automation", {})

    def save_automation_settings(self, settings):
        state = self._read_state()
        state["automation"] = settings
        self._write_state(state)

    def get_last_automated_send(self):
        return self._read_state().get("last_automated_send")

    def set_last_automated_send(self, iso_timestamp):
        state = self._read_state()
        state["last_automated_send"] = iso_timestamp
        self._write_state(state)

    def get_backup_settings(self):
        return self._read_state().get("backup", {"enabled": False, "interval_days": 7})

    def save_backup_settings(self, settings):
        state = self._read_state()
        state["backup"] = settings
        self._write_state(state)

    def get_last_backup_at(self):
        return self._read_state().get("last_backup_at")

    def set_last_backup_at(self, iso_timestamp):
        state = self._read_state()
        state["last_backup_at"] = iso_timestamp
        self._write_state(state)

    def get_app_settings(self):
        defaults = {
            "compress_screenshots": True,
            "default_reporter_name": "",
            "email_signature_name": "",
            "email_signature_title": "",
            "email_signature_org": "",
            "default_report_type": "daily",
            "email_tagline": "",
        }
        stored = self._read_state().get("app_settings", {})
        return {**defaults, **stored}

    def save_app_settings(self, settings):
        state = self._read_state()
        state["app_settings"] = {**self.get_app_settings(), **settings}
        self._write_state(state)

    # ------------------------------------------------------------ workbook
    def _create_workbook(self, platforms):
        wb = Workbook()
        ws = wb.active
        ws.title = "Platforms"
        ws.append(PLATFORM_FIELDS)
        for p in platforms:
            ws.append([p.get(f, "") for f in PLATFORM_FIELDS])

        logs = wb.create_sheet("Logs")
        logs.append(["timestamp", "cycle", "platform_id", "project_name", "field", "old_value", "new_value", "changed_by"])

        snaps = wb.create_sheet("Snapshots")
        snaps.append(["timestamp", "cycle", "healthy", "warning", "critical", "total"])

        incidents = wb.create_sheet("Incidents")
        incidents.append(INCIDENT_FIELDS)

        wb.save(self.xlsx_path)
        self._append_snapshot(wb, cycle=0, save_after=False)
        wb.save(self.xlsx_path)

    def _migrate_schema(self):
        """Adds sheets/columns introduced after a workbook was first created,
        so an existing data file keeps working after an app update without
        losing anything already in it."""
        wb = self._open()
        changed = False
        if "Incidents" not in wb.sheetnames:
            incidents = wb.create_sheet("Incidents")
            incidents.append(INCIDENT_FIELDS)
            changed = True
        else:
            incidents = wb["Incidents"]
            header = [c.value for c in incidents[1]] if incidents.max_row >= 1 else []
            if header != INCIDENT_FIELDS:
                for i, field in enumerate(INCIDENT_FIELDS, start=1):
                    if i > len(header) or header[i - 1] != field:
                        incidents.cell(row=1, column=i, value=field)
                changed = True
        if changed:
            wb.save(self.xlsx_path)

    def _open(self):
        return load_workbook(self.xlsx_path)

    # ---------------------------------------------------------- platforms
    def list_platforms(self):
        wb = self._open()
        ws = wb["Platforms"]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            rows.append(dict(zip(PLATFORM_FIELDS, row)))
        return rows

    def get_platform(self, platform_id):
        for p in self.list_platforms():
            if p["id"] == platform_id:
                return p
        return None

    def find_duplicate_platform(self, project_name, url="", exclude_id=None):
        """Case-insensitive match on name, or on URL when a URL is given.
        Used to warn before creating what looks like a repeat registration."""
        name_key = (project_name or "").strip().lower()
        url_key = (url or "").strip().lower()
        for p in self.list_platforms():
            if exclude_id and p["id"] == exclude_id:
                continue
            existing_name = (p.get("project_name") or "").strip().lower()
            existing_url = (p.get("url") or "").strip().lower()
            if name_key and existing_name == name_key:
                return p
            if url_key and existing_url and existing_url == url_key:
                return p
        return None

    def _next_cycle(self, state):
        state["cycle"] = int(state.get("cycle", 0)) + 1
        return state["cycle"]

    def _append_snapshot(self, wb, cycle, save_after=True, timestamp=None):
        ws = wb["Platforms"]
        healthy = warning = critical = total = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            total += 1
            health = row[PLATFORM_FIELDS.index("health")]
            if health == "Healthy":
                healthy += 1
            elif health == "Degraded":
                warning += 1
            elif health == "Down":
                critical += 1
        snaps = wb["Snapshots"]
        snap_time = timestamp or datetime.now().isoformat(timespec="seconds")
        snaps.append([snap_time, cycle, healthy, warning, critical, total])
        if save_after:
            wb.save(self.xlsx_path)
        return {"healthy": healthy, "warning": warning, "critical": critical, "total": total}

    def _append_logs(self, wb, cycle, entries):
        logs = wb["Logs"]
        ts = datetime.now().isoformat(timespec="seconds")
        for e in entries:
            logs.append([ts, cycle, e["platform_id"], e["project_name"], e["field"], e["old_value"], e["new_value"], e["changed_by"]])

    def save_platforms(self, updates, changed_by):
        """
        updates: list of dicts, each a full or partial platform record with an 'id'.
        Existing platforms are updated field by field (diffed for the log).
        A dict with a new id not already present is inserted as a new platform.
        Returns the fresh full platform list plus the new summary counts.
        """
        with _lock:
            wb = self._open()
            ws = wb["Platforms"]
            state = self._read_state()
            cycle = self._next_cycle(state)

            existing_by_id = {}
            row_index_by_id = {}
            for idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                pid = row[0].value
                if pid is None:
                    continue
                existing_by_id[pid] = {f: row[i].value for i, f in enumerate(PLATFORM_FIELDS)}
                row_index_by_id[pid] = idx

            log_entries = []
            now_str = datetime.now().strftime("%d %b %H:%M")

            for update in updates:
                pid = update.get("id")
                if pid and pid in existing_by_id:
                    row_idx = row_index_by_id[pid]
                    current = existing_by_id[pid]
                    for field in PLATFORM_FIELDS:
                        if field in ("id", "updated_at"):
                            continue
                        if field not in update:
                            continue
                        new_val = update[field]
                        old_val = current.get(field, "")
                        if str(new_val) != str(old_val):
                            log_entries.append({
                                "platform_id": pid, "project_name": update.get("project_name", current.get("project_name")),
                                "field": field, "old_value": old_val, "new_value": new_val, "changed_by": changed_by,
                            })
                            col = PLATFORM_FIELDS.index(field) + 1
                            ws.cell(row=row_idx, column=col, value=new_val)
                    if log_entries and any(e["platform_id"] == pid for e in log_entries):
                        ws.cell(row=row_idx, column=PLATFORM_FIELDS.index("updated_at") + 1, value=now_str)
                else:
                    new_id = pid or ("p_" + str(int(datetime.now().timestamp()))[-8:])
                    record = {f: update.get(f, "") for f in PLATFORM_FIELDS}
                    record["id"] = new_id
                    record["updated_at"] = now_str
                    ws.append([record.get(f, "") for f in PLATFORM_FIELDS])
                    log_entries.append({
                        "platform_id": new_id, "project_name": record.get("project_name", ""),
                        "field": "created", "old_value": "", "new_value": "new platform added", "changed_by": changed_by,
                    })

            self._append_logs(wb, cycle, log_entries)
            summary = self._append_snapshot(wb, cycle, save_after=False)
            wb.save(self.xlsx_path)
            self._write_state(state)
            return summary

    def delete_platform(self, platform_id, changed_by):
        with _lock:
            wb = self._open()
            ws = wb["Platforms"]
            state = self._read_state()
            cycle = self._next_cycle(state)
            target_row = None
            project_name = platform_id
            for row in ws.iter_rows(min_row=2):
                if row[0].value == platform_id:
                    target_row = row[0].row
                    project_name = row[PLATFORM_FIELDS.index("project_name")].value
                    break
            if target_row:
                ws.delete_rows(target_row, 1)
                self._append_logs(wb, cycle, [{
                    "platform_id": platform_id, "project_name": project_name, "field": "deleted",
                    "old_value": "present", "new_value": "removed", "changed_by": changed_by,
                }])
            summary = self._append_snapshot(wb, cycle, save_after=False)
            wb.save(self.xlsx_path)
            self._write_state(state)
            return summary

    # ------------------------------------------------------------ incidents
    def create_incident(self, platform_id, incident, changed_by, forced_id=None, timestamp=None):
        """
        incident may include: health, notes, last_detection (applied to the
        platform, same as a normal update), plus severity, category,
        affected_component, resolution_notes, eta, screenshots (list of
        stored filenames) which are recorded only on the Incidents sheet.
        Returns {"summary", "incident_id", "cycle"}.
        """
        with _lock:
            wb = self._open()
            ws = wb["Platforms"]
            state = self._read_state()
            cycle = self._next_cycle(state)

            row_idx = None
            current = None
            for idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                if row[0].value == platform_id:
                    row_idx = idx
                    current = {f: row[i].value for i, f in enumerate(PLATFORM_FIELDS)}
                    break
            if row_idx is None:
                raise ValueError("platform not found")

            now_str = datetime.now().strftime("%d %b %H:%M")
            log_entries = []
            for field in ("health", "notes", "last_detection"):
                if field in incident and incident[field] not in (None, ""):
                    new_val = incident[field]
                    old_val = current.get(field, "")
                    if str(new_val) != str(old_val):
                        log_entries.append({
                            "platform_id": platform_id, "project_name": current.get("project_name"),
                            "field": field, "old_value": old_val, "new_value": new_val, "changed_by": changed_by,
                        })
                        col = PLATFORM_FIELDS.index(field) + 1
                        ws.cell(row=row_idx, column=col, value=new_val)
            if log_entries:
                ws.cell(row=row_idx, column=PLATFORM_FIELDS.index("updated_at") + 1, value=now_str)

            incident_id = forced_id or ("inc_" + str(int(datetime.now().timestamp() * 1000))[-10:])
            ts = timestamp or datetime.now().isoformat(timespec="seconds")
            incidents_ws = wb["Incidents"]
            incident_health = incident.get("health", current.get("health"))
            # A "Healthy" entry is not an active problem, so it does not go
            # through Acknowledged / In Progress / Resolved. It is recorded
            # as already Resolved (nothing to work through), matching how
            # incident management treats a recovery note versus a fault.
            resolved_status = "Resolved" if incident_health == "Healthy" else (incident.get("status") or "Open")
            record = {
                "id": incident_id, "platform_id": platform_id, "project_name": current.get("project_name"),
                "cycle": cycle, "timestamp": ts, "reported_by": changed_by,
                "severity": incident.get("severity", ""), "category": incident.get("category", ""),
                "affected_component": incident.get("affected_component", ""),
                "health": incident_health,
                "notes": incident.get("notes", ""), "resolution_notes": incident.get("resolution_notes", ""),
                "eta": incident.get("eta", ""),
                "screenshots": json.dumps(incident.get("screenshots") or []),
                "status": resolved_status,
                "edited_at": "", "edited_by": "",
            }
            incidents_ws.append([record.get(f, "") for f in INCIDENT_FIELDS])

            self._append_logs(wb, cycle, log_entries)
            summary = self._append_snapshot(wb, cycle, save_after=False, timestamp=ts)
            wb.save(self.xlsx_path)
            self._write_state(state)
            return {"summary": summary, "incident_id": incident_id, "cycle": cycle}

    def list_incidents(self, platform_id=None, limit=200):
        wb = self._open()
        if "Incidents" not in wb.sheetnames:
            return []
        ws = wb["Incidents"]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            rec = dict(zip(INCIDENT_FIELDS, row))
            try:
                rec["screenshots"] = json.loads(rec.get("screenshots") or "[]")
            except (TypeError, ValueError):
                rec["screenshots"] = []
            rows.append(rec)
        if platform_id:
            rows = [r for r in rows if r["platform_id"] == platform_id]
        rows.sort(key=lambda r: r["timestamp"], reverse=True)
        return rows[:limit]

    def get_incident(self, incident_id):
        for r in self.list_incidents(limit=100000):
            if r["id"] == incident_id:
                return r
        return None

    def update_incident(self, incident_id, updates, changed_by):
        """Corrects a past incident record in place. Status and health
        changes are also written to the Logs sheet, same as any other
        field change, so moving an incident through its workflow shows up
        in the field-level audit trail instead of only on the incident
        record itself."""
        with _lock:
            wb = self._open()
            if "Incidents" not in wb.sheetnames:
                raise ValueError("incident not found")
            ws = wb["Incidents"]
            row_idx = None
            current = None
            for idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                if row[0].value == incident_id:
                    row_idx = idx
                    current = {f: row[i].value for i, f in enumerate(INCIDENT_FIELDS)}
                    break
            if row_idx is None:
                raise ValueError("incident not found")

            editable = ("severity", "category", "affected_component", "health", "notes",
                        "resolution_notes", "eta", "status", "screenshots", "timestamp")
            log_entries = []
            for field in editable:
                if field in updates:
                    value = updates[field]
                    if field == "screenshots":
                        value = json.dumps(value or [])
                    if field in ("status", "health") and str(value) != str(current.get(field, "")):
                        log_entries.append({
                            "platform_id": current.get("platform_id"), "project_name": current.get("project_name"),
                            "field": field, "old_value": current.get(field, ""), "new_value": value,
                            "changed_by": changed_by,
                        })
                    col = INCIDENT_FIELDS.index(field) + 1
                    ws.cell(row=row_idx, column=col, value=value)

            ws.cell(row=row_idx, column=INCIDENT_FIELDS.index("edited_at") + 1,
                    value=datetime.now().isoformat(timespec="seconds"))
            ws.cell(row=row_idx, column=INCIDENT_FIELDS.index("edited_by") + 1, value=changed_by)

            if log_entries:
                state = self._read_state()
                cycle = self._next_cycle(state)
                self._append_logs(wb, cycle, log_entries)
                self._write_state(state)

            wb.save(self.xlsx_path)
        return self.get_incident(incident_id)

    # ---------------------------------------------------------------- logs
    def list_logs(self, limit=200):
        wb = self._open()
        ws = wb["Logs"]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            rows.append({
                "timestamp": row[0], "cycle": row[1], "platform_id": row[2], "project_name": row[3],
                "field": row[4], "old_value": row[5], "new_value": row[6], "changed_by": row[7],
            })
        rows.sort(key=lambda r: r["timestamp"], reverse=True)
        return rows[:limit]

    def list_snapshots(self, limit=30):
        wb = self._open()
        ws = wb["Snapshots"]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            rows.append({"timestamp": row[0], "cycle": row[1], "healthy": row[2], "warning": row[3], "critical": row[4], "total": row[5]})
        return rows[-limit:]

    # ------------------------------------------------------------- summary
    def summary(self):
        platforms = self.list_platforms()
        healthy = sum(1 for p in platforms if p["health"] == "Healthy")
        warning = sum(1 for p in platforms if p["health"] == "Degraded")
        critical = sum(1 for p in platforms if p["health"] == "Down")
        state = self._read_state()
        return {
            "total": len(platforms), "healthy": healthy, "warning": warning, "critical": critical,
            "cycle": state.get("cycle", 0),
        }
