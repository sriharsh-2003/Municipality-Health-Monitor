"""
seed_demo_data.py

Not part of the running app. A standalone script for generating realistic
demo data (about 15 days of incidents, status changes, and snapshots)
against a fresh data/ folder, so the app can be exercised and reviewed
with something that looks like real usage instead of an empty database.

Run from the backend/ folder with the app NOT running:

    python seed_demo_data.py

Safe to re-run: it does not delete anything itself, but if you want a
clean slate first, delete data/platform_health.xlsx, data/app_state.json
and data/attachments/ before running it.
"""

import io
import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from excel_store import ExcelStore, INCIDENT_STATUS_VALUES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
ATTACHMENTS_DIR = DATA_DIR / "attachments"

REPORTERS = ["Admin", "Supervisor", "Operator", "K. Al-Zahrani (Operator)", "Yousef (Supervisor)"]

CATEGORIES = [
    "Camera / Sensor Outage", "Network Connectivity", "Software / Application Error",
    "Hardware Failure", "Power Outage", "Data Quality Issue", "Scheduled Maintenance",
]

NOTES_BY_CATEGORY = {
    "Camera / Sensor Outage": "Camera feed dropped, no signal from the unit.",
    "Network Connectivity": "Lost connection to the platform, timing out on health checks.",
    "Software / Application Error": "Application threw repeated errors during ingest.",
    "Hardware Failure": "Onsite hardware reporting a fault code.",
    "Power Outage": "Site lost power, platform unreachable during the outage.",
    "Data Quality Issue": "Detections look inconsistent with expected volume for this time of day.",
    "Scheduled Maintenance": "Taken offline for planned maintenance.",
}


def make_placeholder_image(color):
    img = Image.new("RGB", (640, 400), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 620, 380], outline=(255, 255, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def main():
    store = ExcelStore(DATA_DIR / "platform_health.xlsx", DATA_DIR / "app_state.json")
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

    platforms = store.list_platforms()
    if not platforms:
        print("No platforms found. Start the app once first so the default platforms are seeded, then run this again.")
        return

    now = datetime.now()
    incident_count = 0

    for day_offset in range(15, -1, -1):
        day = now - timedelta(days=day_offset)

        # A handful of incidents on most days, busier some days than others.
        incidents_today = random.choice([0, 0, 1, 1, 2, 3])
        for _ in range(incidents_today):
            platform = random.choice(platforms)
            category = random.choice(CATEGORIES)
            severity = random.choice(["Low", "Medium", "High", "Critical"])
            health = random.choice(["Degraded", "Degraded", "Down"])
            hour = random.randint(7, 19)
            minute = random.randint(0, 59)
            occurred_at = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            reporter = random.choice(REPORTERS)

            incident = {
                "health": health,
                "notes": NOTES_BY_CATEGORY[category],
                "severity": severity,
                "category": category,
                "affected_component": f"Camera {random.randint(1, 8)}" if "Camera" in category else "",
                "eta": "Vendor dispatched" if severity in ("High", "Critical") else "",
                "resolution_notes": "",
                "status": "Open",
                "screenshots": [],
            }

            incident_id = f"inc_seed_{platform['id']}_{day_offset}_{incidents_today}_{random.randint(1000,9999)}"
            # A third of incidents get a screenshot, so the screenshot / email auto-link paths get exercised too.
            if random.random() < 0.35:
                folder = ATTACHMENTS_DIR / incident_id
                folder.mkdir(parents=True, exist_ok=True)
                color = {"Low": (16, 122, 90), "Medium": (180, 130, 20), "High": (180, 60, 20), "Critical": (150, 20, 20)}[severity]
                (folder / "0_screenshot.png").write_bytes(make_placeholder_image(color))
                incident["screenshots"] = ["0_screenshot.png"]

            result = store.create_incident(
                platform["id"], incident, reporter, forced_id=incident_id,
                timestamp=occurred_at.isoformat(timespec="seconds"),
            )
            incident_count += 1

            # Age the incident forward through a realistic status workflow,
            # further along the older it is, so today's incidents skew "Open"
            # and last week's skew "Resolved" the way a real queue would.
            age_days = day_offset
            if age_days >= 2:
                roll = random.random()
                if roll < 0.65:
                    final_status = "Resolved"
                    resolution = "Resolved after a site visit confirmed the fix held."
                elif roll < 0.85:
                    final_status = "In Progress"
                    resolution = "Vendor engaged, fix in progress."
                else:
                    final_status = "Acknowledged"
                    resolution = ""
                store.update_incident(
                    result["incident_id"],
                    {"status": final_status, "resolution_notes": resolution,
                     "health": "Healthy" if final_status == "Resolved" else health},
                    random.choice(REPORTERS),
                )
                if final_status == "Resolved":
                    store.save_platforms([{"id": platform["id"], "health": "Healthy",
                                            "notes": "Back to normal after resolution."}], "System")
            elif age_days == 1 and random.random() < 0.5:
                store.update_incident(result["incident_id"], {"status": "Acknowledged"}, random.choice(REPORTERS))

    print(f"Seeded {incident_count} incidents across {len(platforms)} platforms over 16 days.")
    print("Restart the app (or just refresh the browser) to see the demo data.")


if __name__ == "__main__":
    main()
