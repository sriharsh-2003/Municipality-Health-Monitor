"""
scheduler.py

A background thread (via APScheduler) that wakes up once a minute, checks
the automation settings saved from the "Automated email" panel, and sends
the report when the current time matches the configured schedule.

This only fires while this Flask process is running. That is a deliberate,
simple trade off: leave the app running (or set it to start with the
computer) and automation works on its own. If the team would rather not
keep a process running all the time, the README explains the alternative:
point the computer's own task scheduler at the /api/email/send endpoint
instead, which does not need this background job at all.
"""

from datetime import datetime
import os

from apscheduler.schedulers.background import BackgroundScheduler

import email_builder
import mailer
import backup as backup_module


def _weekday_matches(frequency, now):
    if frequency == "daily":
        return True
    if frequency == "weekdays":
        return now.weekday() < 5
    if frequency == "weekly":
        return now.weekday() == 6
    return False


def _base_url():
    # Render (and similar hosts) expose the service's public URL via this
    # env var. Falls back to localhost for a machine running the app locally.
    return os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000").rstrip("/")


def start_scheduler(store, get_smtp_config, xlsx_path=None, attachments_dir=None, backups_dir=None):
    scheduler = BackgroundScheduler()

    def tick():
        settings = store.get_automation_settings()
        if not settings or not settings.get("enabled"):
            return
        now = datetime.now()
        target_time = settings.get("time", "09:00")
        try:
            target_hh, target_mm = [int(x) for x in target_time.split(":")]
        except ValueError:
            return
        if now.hour != target_hh or now.minute != target_mm:
            return
        if not _weekday_matches(settings.get("frequency", "daily"), now):
            return

        last_sent = store.get_last_automated_send()
        today_key = now.strftime("%Y-%m-%d %H:%M")
        if last_sent == today_key:
            return

        recipient = settings.get("recipient")
        if not recipient:
            return

        try:
            app_settings = store.get_app_settings()
            platforms = store.list_platforms()
            incidents_by_platform = {}
            for inc in store.list_incidents(limit=500):
                if inc.get("screenshots") and inc["platform_id"] not in incidents_by_platform:
                    incidents_by_platform[inc["platform_id"]] = inc
            built = email_builder.build_email(
                platforms, sender_name=settings.get("sender", "Reporter"),
                incidents_by_platform=incidents_by_platform, base_url=_base_url(),
                sender_title=app_settings.get("email_signature_title", ""),
                sender_org=app_settings.get("email_signature_org", ""),
            )
            smtp_config = get_smtp_config()
            mailer.send_email(
                smtp_config, recipient,
                "Municipality Digital Operations Status Update",
                built["html"], built["text"],
            )
            store.set_last_automated_send(today_key)
            print(f"[{now.isoformat(timespec='seconds')}] Automated report sent to {recipient}.")
        except Exception as exc:
            print(f"[{now.isoformat(timespec='seconds')}] Automated send failed: {exc}")

    scheduler.add_job(tick, "interval", seconds=60, id="automation_tick")

    def backup_tick():
        if not (xlsx_path and attachments_dir and backups_dir):
            return
        settings = store.get_backup_settings()
        if not settings or not settings.get("enabled"):
            return
        interval_days = int(settings.get("interval_days") or 7)
        last = store.get_last_backup_at()
        now = datetime.now()
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if (now - last_dt).total_seconds() < interval_days * 86400:
                    return
            except ValueError:
                pass
        try:
            dest = backup_module.create_backup(xlsx_path, attachments_dir, backups_dir)
            backup_module.prune_old_backups(backups_dir, keep=30)
            store.set_last_backup_at(now.isoformat(timespec="seconds"))
            print(f"[{now.isoformat(timespec='seconds')}] Scheduled backup created: {dest.name}")
        except Exception as exc:
            print(f"[{now.isoformat(timespec='seconds')}] Scheduled backup failed: {exc}")

    # Checked hourly — interval_days is measured in whole days, so a minute-level check is unnecessary.
    scheduler.add_job(backup_tick, "interval", minutes=60, id="backup_tick")
    scheduler.start()
    return scheduler
