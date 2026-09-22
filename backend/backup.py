"""
backup.py

Makes a single compressed .zip snapshot of everything that matters:
the Excel workbook plus every screenshot under data/attachments/.
Backups are named with the platform-health data's own timestamp so
they sort naturally and are easy to tell apart at a glance.
"""

import zipfile
from datetime import datetime
from pathlib import Path


def make_backup_filename():
    return f"platform-health-backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.zip"


def create_backup(xlsx_path: Path, attachments_dir: Path, backups_dir: Path):
    backups_dir.mkdir(parents=True, exist_ok=True)
    filename = make_backup_filename()
    dest = backups_dir / filename

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        if xlsx_path.exists():
            zf.write(xlsx_path, arcname=f"data/{xlsx_path.name}")
        if attachments_dir.exists():
            for f in attachments_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, arcname=f"data/attachments/{f.relative_to(attachments_dir)}")

    return dest


def list_backups(backups_dir: Path):
    if not backups_dir.exists():
        return []
    items = []
    for f in sorted(backups_dir.glob("*.zip"), reverse=True):
        stat = f.stat()
        items.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return items


def prune_old_backups(backups_dir: Path, keep=30):
    """Keeps the most recent `keep` backups, deletes the rest, so backups
    don't silently fill the disk on a laptop that's left running for months."""
    files = sorted(backups_dir.glob("*.zip"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[keep:]:
        try:
            f.unlink()
        except OSError:
            pass
