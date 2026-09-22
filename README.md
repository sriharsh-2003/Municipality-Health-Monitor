# Municipality Digital Operations: Platform Health Monitor

A locally hosted platform health dashboard with a real Flask backend and an
Excel workbook as the actual database. No cloud, no external API calls, no
live data connections to the monitored platforms. The reporter checks each
platform by hand and types the result in.

This is v2.0 of the app: the eight Stitch screens have been consolidated into
one consistent application with a single shared design system (plum/purple
base, teal accent, restrained glassmorphism), a collapsible sidebar, and a
clear split between **viewing** (Dashboard, Registry, Platform Details, Audit
Log) and **doing** (Register Platform, Add Incident, Email Center, SMTP
Settings). The telemetry, SOC, and security-placeholder screens from the
original Stitch export are gone — they weren't part of the working app.

## What is in this folder

```
municipality-health-app/
  backend/                  Flask app and all server-side logic
    app.py                  Entry point. Run this.
    excel_store.py          Reads and writes data/platform_health.xlsx
    email_builder.py        Builds the status email (HTML and plain text)
    mailer.py                Sends mail over SMTP
    scheduler.py             Checks the automation settings once a minute
    requirements.txt
    config.example.json     Copy to config.json and fill in your mail server
                             (or use the in-app SMTP Settings page instead)
  data/
    platform_health.xlsx    Created automatically on first run
    app_state.json          Created automatically on first run
  frontend/
    templates/               base.html (shared shell) + 8 pages
    static/
      css/design.css         The one shared design system every page uses
      css/fonts.css          Self-hosted font declarations
      js/                    shell.js (nav/toast) + api.js + one file per page
      vendor/                Chart.js, self-hosted fonts
  README.md                  This file
```

## The eight pages

| Page | Route | Purpose |
|---|---|---|
| Dashboard Overview | `/` | KPIs (live status, plus range-filtered incident counts, avg latency, cameras online %), health trend, recent incidents, quick actions — filterable by Today / Week / Month / Year / All Time / Custom Range, and the KPI row scrolls horizontally |
| Platform Registry | `/registry` | Search and filter every platform; hover the **History** chip on a row (1 second) for a quick incident preview popup without leaving the page |
| Register Platform | `/register` | Onboard a new platform — warns and asks for confirmation if a platform with a matching name or URL already exists |
| Add Incident | `/incident` | Pick a platform, set its new status + notes, optionally severity, category, affected component, ETA, resolution notes, a specific date/time (defaults to now), and up to 6 screenshots |
| Platform Details | `/platform/<id>` | Full profile (editable), a rich incident history with any attached screenshots, and the raw field-level audit trail |
| Email Center | `/email` | Executive preview (editable in place before sending), select specific incident records to attach as a CSV, plus automated-send scheduling |
| SMTP Settings | `/smtp-settings` | Host/port/credentials, Test Connection, Save |
| Audit Log | `/audit` | **Incidents tab**: every incident, searchable, with a "Correct this record" button to fix a mistake after the fact. **Field Changes tab**: the raw platform-field history, as before |
| Backups | `/backups` | Automatic backups on a schedule you set, a Backup Now button, and download links for every backup made |

## Who's using it

There's no login — this runs on one office machine for one team, so a
full account system would be more friction than it's worth. Instead, the
top-right of every page has a **role selector** (Admin / Supervisor /
Operator) plus an optional name field. Whatever is selected there is what
gets stamped as the reporter on every incident, platform edit, and
registration — so the audit trail and incident history show who did what,
without anyone having to remember a password.

## Incidents and screenshots

Add Incident (`/incident`) captures more than just a status flip:

- **Status + notes** — required whenever status isn't Healthy.
- **Severity, category, affected component, ETA, resolution notes** — all
  optional context for whoever picks it up next.
- **When it happened** — defaults to the moment you save it; set an exact
  date/time if you're logging something that happened earlier.
- **Screenshots** — drag up to 6 images on, or click to browse. They're
  automatically resized (max 1600px) and compressed on the way in, so a
  full-resolution phone photo doesn't bloat storage, while staying clearly
  readable.
- **Status workflow** — every incident starts as **Open** and can be moved
  through **Acknowledged → In Progress → Resolved** from the Audit Log's
  edit screen, so it's easy to see what's still outstanding at a glance
  (the dashboard's "Still Open" KPI counts these).

**Made a mistake logging one?** Go to **Audit Log → Incidents tab**, find
the record, click **Correct this record**. You can fix any field,
change its date/time, add or remove screenshots, and change its status —
the record keeps a note of who last edited it and when.

Every incident (with its full detail and any screenshots) shows up on that
platform's **Platform Details** page, newest first — plus, on the
**Platform Registry**, hovering a row's History chip for a second shows a
quick preview popup of its most recent incidents, so you can scan status
across many platforms without opening each one.

**Auto-linking in email:** when the Email Center builds a report, it looks
up each currently-unhealthy platform's most recent incident. If that
incident has screenshots, thumbnails are linked straight into the "Issues
and follow up" section — clickable in the HTML version, plain URLs in the
plain-text version. This works automatically for both a manual send and
the scheduled automated send.

**Editing the email before sending:** after Generate Preview, click **Edit
Content** to edit the actual rendered email in place — change wording, add
a line, whatever's needed — before sending. Sending uses exactly what's in
the editor.

**Attaching specific records:** the Email Center's **Attach Records** tab
lets you tick specific incidents and attach them as a CSV alongside the
report — separate from the always-included full workbook export.

## Backups

The **Backups** page lets you turn on automatic backups (every day, 3
days, week, 2 weeks, or month) and also has a **Backup Now** button for
whenever you want one on demand. Each backup is a single compressed
`.zip` containing the Excel workbook and every incident screenshot, named
with its own timestamp, e.g. `platform-health-backup_2026-09-21_143000.zip`.
The 30 most recent backups are kept; older ones are pruned automatically
so they don't quietly fill up the laptop's disk over months of use. To
restore one: unzip it, close the app, and copy `data/platform_health.xlsx`
and the `data/attachments` folder from inside it back into this app's
`data/` folder.

## How to run it

You need Python 3.9 or newer. Nothing else has to be installed system wide.

1. Open a terminal in this folder.
2. Install the backend's dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```
   (If `pip` points to Python 2 on your machine, use `pip3` instead.)
3. Start the app:
   ```
   python app.py
   ```
   (or `python3 app.py`)
4. It opens `http://localhost:5000` in your browser automatically. If it
   does not, open that address yourself.

That is the whole setup. Closing the terminal window stops the app. Running
`python app.py` again picks up right where you left off, since all the data
lives in `data/platform_health.xlsx` on disk, not in memory.

## Editing

- **Register Platform** (`/register`) creates a new one.
- **Add Incident** (`/incident`) is the fast path for a status change: pick
  the platform, set the new status, write the notes. This is the one
  workflow that matters most day to day, so it gets its own page instead of
  being buried in a table row.
- **Platform Details** (`/platform/<id>`) has the full editable profile —
  every metric, not just status and notes — plus that platform's own
  history.

Notes are required whenever status is not Healthy, exactly like the
original rule. Both the Add Incident and Register Platform forms show this
live as you type, rather than only rejecting it after you try to save.

## Where the data actually lives

There is no database engine here. `data/platform_health.xlsx` is a real
Excel workbook with three sheets:

- **Platforms**: the current state of every monitored platform.
- **Logs**: one row per field changed: timestamp, cycle number, platform,
  field, old value, new value, who changed it.
- **Snapshots**: one row per save, with the healthy and warning and
  critical counts at that moment. This is what the trend chart reads.

You can open this file directly in Excel at any time (close it in Excel
before saving again from the app, since a workbook open in two places at
once will fight over the write). The **Export Workbook (.xlsx)** buttons on
the Dashboard and Audit Log pages just download this same file.

This is also why "connect to Excel for metrics" and "have logs and entry
timings" turned into the same feature: the log **is** the timing history,
and it already lives in a spreadsheet you can pivot or chart yourself if
you ever want to go beyond what is built in here.

## Email Center (`/email`)

- **Executive Preview** tab: type a recipient and sender, click **Generate
  Preview** to build a live preview from whatever is currently in the
  table. It is real, email-client-safe HTML (table layout, inline styles)
  so it renders correctly in Outlook, Gmail, and Apple Mail, not just in a
  browser. From there you can copy the HTML or send it immediately.
- **Automated Send** tab: recipient, frequency, time, sender name. Once
  saved, the backend checks these settings once a minute and sends the
  report on its own when the time matches, for as long as `python app.py`
  is running. Leave it running (or set it to start when your computer
  starts) and it works unattended.

Either path needs SMTP configured first — use the **SMTP Settings** page
(`/smtp-settings`) to fill in your mail server and test the connection
before sending anything. Nothing is sent anywhere until that's saved.

## Manual entry only

There is no polling, no webhook, no API connection to Auto Detection,
Smart Gate, RRM, HMM, or Urban Eye anywhere in this codebase. The reporter
checks each platform and types the result into the Add Incident form or
the Platform Details page. Export exists for moving your own typed data
around (backup, handing off to another reporter), not for pulling live
data from anywhere.

## Colors and fonts

These are the real Tahakom colors now, not a placeholder. They were pixel
sampled directly from tahakom.com and cross checked against the color
tokens your Stitch export already used on its own (`#400938` and `#5A214F`
for the plum, `#5CF9F1` and `#00B3A4` for the teal). Both matched
independently, so this palette is on solid ground.

Fonts (IBM Plex Sans, JetBrains Mono, Material Symbols Outlined) are
self-hosted under `frontend/static/vendor/fonts/`, not pulled from Google
Fonts or a CDN. The whole interface — every page's layout, cards, forms,
and tables — is one hand-written stylesheet, `frontend/static/css/design.css`,
so there's a single place to adjust the look. The app was tested with
outbound network access blocked entirely and rendered correctly, so it will
work on a machine with no internet connection at all.

## English only

Every page and the email are English only.

## What was removed from the original Stitch export

The Stitch export included several sections beyond this app's scope:
Telemetry Nodes, Security Protocols, Security SOC, and a Broadcast Alert
button, spread across screens that didn't fit the actual daily workflow.
Rather than keep them as disabled placeholders, they were left out of this
build entirely — the navigation only lists pages that do something. Building
real functionality behind any of them, if you want it, is a separate
scoping conversation since it goes beyond manual daily health checks into
incident management and security operations.

Any hand-drawn placeholder numbers from the original mockups (fabricated
latency thresholds, a fake schema-validation badge, invented percentages)
were replaced with real computed values pulled from the workbook, rather
than left in place looking live when they were not.

## If you want to change the frontend again later

The backend does not care what frontend calls it. Every page talks to the
same small JSON API:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/platforms` | GET, POST | List all platforms, or add one |
| `/api/platforms/<id>` | GET, PUT, DELETE | Read, update, or remove one platform |
| `/api/platforms/bulk` | PUT | Update many platforms in one save |
| `/api/logs` | GET | Audit log entries |
| `/api/summary` | GET | Total, healthy, warning, critical counts, current cycle |
| `/api/charts/health-trend` | GET | Snapshot history for the trend chart |
| `/api/charts/metrics` | GET | Per-platform detections, frames, latency, cameras |
| `/api/email/preview` | GET | Returns `{html, text}` for the current data |
| `/api/email/send` | POST | Sends the report now |
| `/api/automation` | GET, POST | Read or save the automated-send settings |
| `/api/export` | GET | Downloads the live `.xlsx` workbook |

CORS is already enabled, so a new Stitch export running on a different
local port could call this same API directly. Point its fetch calls at
these routes and it will work the same way `overview.html` does now.
