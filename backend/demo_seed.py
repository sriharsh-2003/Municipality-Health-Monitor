"""
demo_seed.py

The actual demo-data generator, factored out so it can be run two ways:
the standalone seed_demo_data.py script (for a fresh local data/ folder),
and the in-app "Generate Demo Data" button on the Backups page (for
seeding a running instance, e.g. on Render, without shell access).

Not part of any real reporting path. Purely for having something to look
at while reviewing the app.
"""

import io
import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

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

# Weighted so the average lands around 3 incidents/day, but zero-incident
# days genuinely happen too, real incident logs are not a smooth curve.
DAILY_COUNT_CHOICES = [0, 1, 2, 3, 4, 5, 6, 7]
DAILY_COUNT_WEIGHTS = [0.12, 0.15, 0.18, 0.20, 0.15, 0.10, 0.07, 0.03]


def make_placeholder_image(color):
    img = Image.new("RGB", (640, 400), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 620, 380], outline=(255, 255, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def generate(store, attachments_dir, days=60, screenshot_rate=0.35, seed_suffix=None):
    """
    Generates `days` days of incidents (today back through `days - 1` days
    ago) against whatever platforms already exist in `store`, following a
    realistic status-aging workflow. Additive: does not touch or clear any
    existing data, safe to call more than once.

    Returns (incident_count, zero_incident_day_count).
    """
    platforms = store.list_platforms()
    if not platforms:
        raise ValueError("No platforms found. Start the app once first so the default platforms are seeded.")

    Path(attachments_dir).mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    incident_count = 0
    zero_days = 0
    run_tag = seed_suffix or random.randint(100000, 999999)

    for day_offset in range(days - 1, -1, -1):
        day = now - timedelta(days=day_offset)
        incidents_today = random.choices(DAILY_COUNT_CHOICES, weights=DAILY_COUNT_WEIGHTS, k=1)[0]
        if incidents_today == 0:
            zero_days += 1

        used_minutes = set()
        for slot in range(incidents_today):
            platform = random.choice(platforms)
            category = random.choice(CATEGORIES)
            severity = random.choice(["Low", "Medium", "High", "Critical"])
            health = random.choice(["Degraded", "Degraded", "Down"])
            hour = random.randint(6, 21)
            minute = random.randint(0, 59)
            while (hour, minute) in used_minutes:
                minute = random.randint(0, 59)
            used_minutes.add((hour, minute))
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

            incident_id = f"inc_demo_{run_tag}_{platform['id']}_{day_offset}_{slot}"
            if random.random() < screenshot_rate:
                folder = Path(attachments_dir) / incident_id
                folder.mkdir(parents=True, exist_ok=True)
                color = {"Low": (16, 122, 90), "Medium": (180, 130, 20), "High": (180, 60, 20), "Critical": (150, 20, 20)}[severity]
                (folder / "0_screenshot.png").write_bytes(make_placeholder_image(color))
                incident["screenshots"] = ["0_screenshot.png"]

            result = store.create_incident(
                platform["id"], incident, reporter, forced_id=incident_id,
                timestamp=occurred_at.isoformat(timespec="seconds"),
            )
            incident_count += 1

            # Older incidents skew resolved, recent ones skew open, the way
            # a real queue actually looks.
            age_days = day_offset
            if age_days >= 2:
                roll = random.random()
                if roll < 0.65:
                    final_status, resolution = "Resolved", "Resolved after a site visit confirmed the fix held."
                elif roll < 0.85:
                    final_status, resolution = "In Progress", "Vendor engaged, fix in progress."
                else:
                    final_status, resolution = "Acknowledged", ""
                store.update_incident(
                    result["incident_id"],
                    {"status": final_status, "resolution_notes": resolution,
                     "health": "Healthy" if final_status == "Resolved" else health},
                    random.choice(REPORTERS),
                )
            elif age_days == 1 and random.random() < 0.5:
                store.update_incident(result["incident_id"], {"status": "Acknowledged"}, random.choice(REPORTERS))

    return incident_count, zero_days
