"""
seed_demo_data.py

Not part of the running app. A standalone script for generating realistic
demo data (about 2 months of incidents, status changes, and snapshots)
against a fresh data/ folder, so the app can be exercised and reviewed
with something that looks like real usage instead of an empty database.

Run from the backend/ folder with the app NOT running:

    python seed_demo_data.py

Safe to re-run: it does not delete anything itself, but if you want a
clean slate first, delete data/platform_health.xlsx, data/app_state.json
and data/attachments/ before running it.

For seeding a running instance (e.g. on Render, with no shell access),
use the "Generate Demo Data" button on the Backups page instead, which
calls the same generator through /api/admin/seed-demo-data.
"""

from pathlib import Path

from excel_store import ExcelStore
import demo_seed

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
ATTACHMENTS_DIR = DATA_DIR / "attachments"


def main():
    store = ExcelStore(DATA_DIR / "platform_health.xlsx", DATA_DIR / "app_state.json")

    if not store.list_platforms():
        print("No platforms found. Start the app once first so the default platforms are seeded, then run this again.")
        return

    incident_count, zero_days = demo_seed.generate(store, ATTACHMENTS_DIR, days=60)
    print(f"Seeded {incident_count} incidents over 60 days ({zero_days} of those days had none).")
    print("Restart the app (or just refresh the browser) to see the demo data.")


if __name__ == "__main__":
    main()
