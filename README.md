# Municipality Digital Operations: Platform Health Monitor

A locally hosted platform health dashboard with a real Flask backend and an
Excel workbook as the actual database. No cloud, no external API calls, no
live data connections to the monitored platforms. The reporter checks each
platform by hand and types the result in.

## What is in this folder

```
municipality-health-app/
  backend/                  Flask app and all server-side logic
    app.py                  Entry point. Run this.
    excel_store.py          Reads and writes data/platform_health.xlsx
    email_builder.py        Builds the status email (HTML and plain text)
    mailer.py                Sends mail over SMTP
    scheduler.py             Checks automation and backup settings once a minute
    backup.py                 Builds and lists the compressed backup archives
    seed_demo_data.py       Optional. Generates realistic demo data for testing
    requirements.txt
    config.example.json     Copy to config.json and fill in your mail server
                             (or use the in-app Settings page instead)
  data/
    platform_health.xlsx    Created automatically on first run
    app_state.json          Created automatically on first run
    attachments/             Incident screenshots
    backups/                 Backup archives created from the Backups page
  frontend/
    templates/               base.html (shared shell) plus one file per page
    static/
      css/design.css         The one shared design system every page uses
      css/fonts.css          Self-hosted font declarations
      js/                    shell.js (nav, identity, hints, toasts), api.js,
                              and one file per page
      vendor/                Chart.js, self-hosted fonts
  README.md                  This file
```

## The pages

| Page | Route | Purpose |
|---|---|---|
| Dashboard Overview | `/` | Live status counts, a daily health trend chart, incident counts for the selected range, the platform table, and recent incidents. Filterable by Today, Week, Month, Year, All Time, or a custom range |
| Platform Registry | `/registry` | Search and filter every platform. Hover the **History** chip on a row for a second to preview its recent incidents without leaving the page |
| Register Platform | `/register` | Onboard a new platform. Asks for confirmation if a platform with a matching name or URL already exists |
| Add Incident | `/incident` | Pick a platform, set its new status and notes, and optionally severity, category, affected component, ETA, resolution notes, a specific date and time (defaults to now), and up to 6 screenshots |
| Platform Details | `/platform/<id>` | Two tabs. **Overview**: live KPIs, the interactive incident history with one-click status changes, and the raw field-level audit trail. **Edit Details**: the editable profile form and platform removal, kept apart from the monitoring view on purpose |
| Email Center | `/email` | Build the executive report, edit it in place before sending, attach specific incident records as a CSV, and set up automated sending |
| Settings | `/smtp-settings` | Mail server configuration, screenshot compression preference, and the default reporter identity and email signature |
| Audit Log | `/audit` | **Incidents** tab: every incident, searchable, with one-click status changes and a "Correct this record" option for fixing a mistake. **Field Changes** tab: the raw platform-field history |
| Backups | `/backups` | Automatic backups on a schedule you set, plus a Backup Now button and download links for every backup made |

## Who's using it

There is no login. This runs on one office machine for one team, so a full
account system would be more friction than it is worth. Instead, the
top-right of every page has an identity control showing the current role
and name. Click it to change the role (Admin, Supervisor, or Operator) or
set a name. Whatever is set there gets recorded as the reporter on every
incident, platform edit, and registration, so the incident history and
audit trail show who did what.

The Settings page can set a default reporter name for the whole office. A
browser that has not set its own name yet will use that default instead of
showing a bare role with nobody attached to it.

## Incidents and the status workflow

Add Incident (`/incident`) captures more than a status flip:

- **Status and notes**. Notes are required whenever status is not Healthy.
- **Severity, category, affected component, ETA, resolution notes**. All
  optional context for whoever picks it up next.
- **When it happened**. Defaults to the moment you save it. Set an exact
  date and time if you are logging something that happened earlier.
- **Screenshots**. Drag up to 6 images on, or click to browse. They are
  resized and compressed on the way in by default (still clearly readable),
  or you can turn that off from Settings and keep the exact original file.

Every incident starts as **Open** and moves forward through **Acknowledged**,
**In Progress**, and **Resolved**. The next step shows up as a single button
right on the incident's card, both on the Platform Details page and in the
Audit Log's Incidents tab, so moving something forward never requires
opening a form. A resolved incident can be reopened the same way if it
turns out the issue was not actually fixed.

**Made a mistake logging one?** Find the record on the Audit Log's
Incidents tab and click **Correct this record**. You can fix any field,
change its date and time, add or remove screenshots, and change its
status. The record keeps a note of who last edited it and when.

Every incident, with its full detail and any screenshots, shows up on that
platform's **Platform Details** page under the Overview tab, newest first.
Click a screenshot thumbnail anywhere in the app to open it full size.

**Auto-linking in email:** when the Email Center builds a report, it looks
up each currently unhealthy platform's most recent incident. If that
incident has screenshots, thumbnails are linked straight into the "Issues
and follow up" section: clickable in the HTML version, plain URLs in the
plain-text version. This happens automatically for both a manual send and
the scheduled automated send.

**Editing the email before sending:** after Generate Preview, click **Edit
Content** to edit the actual rendered email in place. Sending uses exactly
what is in the editor at that point.

**Attaching specific records:** the Email Center's **Attach Records** tab
lets you tick specific incidents and attach them as a CSV alongside the
report, separate from the always-included full workbook export.

## Backups

The **Backups** page turns on automatic backups on an interval you choose
(every day, 3 days, week, 2 weeks, or month), and also has a **Backup Now**
button for whenever you want one on demand. Each backup is a single
compressed `.zip` containing the Excel workbook and every incident
screenshot, named with its own timestamp, for example
`platform-health-backup_2026-09-21_143000.zip`. The 30 most recent backups
are kept; older ones are pruned automatically so they do not quietly fill
up the laptop's disk over months of use. To restore one: unzip it, close
the app, and copy `data/platform_health.xlsx` and the `data/attachments`
folder from inside it back into this app's `data/` folder.

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

## Trying it with realistic data

`backend/seed_demo_data.py` is a standalone script, not part of the running
app, that fills in about 15 days of realistic incidents across whatever
platforms already exist, with a mix of severities, categories, statuses,
and some screenshots. Handy for reviewing the app with something that looks
like real usage instead of an empty database.

```
cd backend
python seed_demo_data.py
```

It only adds data; it does not delete anything. To start over with a clean
slate, close the app, delete `data/platform_health.xlsx`,
`data/app_state.json`, and everything under `data/attachments/`, then start
the app again before re-running the seed script (it needs the default
platforms to already exist).

## Where the data actually lives

There is no database engine here. `data/platform_health.xlsx` is a real
Excel workbook with four sheets:

- **Platforms**: the current state of every monitored platform.
- **Logs**: one row per field changed: timestamp, cycle number, platform,
  field, old value, new value, who changed it.
- **Snapshots**: one row per action, with the healthy, warning, and
  critical counts at that moment. The dashboard's trend chart rolls these
  up to one point per day.
- **Incidents**: the full structured record of every incident, including
  severity, category, status, resolution notes, and which screenshot files
  belong to it.

You can open this file directly in Excel at any time (close it in Excel
before saving again from the app, since a workbook open in two places at
once will fight over the write). The **Export Workbook (.xlsx)** buttons on
the Dashboard and Audit Log pages just download this same file.

## Email Center (`/email`)

- **Executive Preview** tab: type a recipient and sender, click **Generate
  Preview** to build a live preview from whatever is currently in the
  table. It is real, email-client-safe HTML (table layout, inline styles)
  so it renders correctly in Outlook, Gmail, and Apple Mail, not just in a
  browser. Click **Edit Content** to change the wording directly in the
  preview before sending.
- **Attach Records** tab: tick specific incidents to attach as a CSV.
- **Automated Send** tab: recipient, frequency, time, sender name. Once
  saved, the backend checks these settings once a minute and sends the
  report on its own when the time matches, for as long as `python app.py`
  is running.

Either path needs SMTP configured first. Use the **Settings** page
(`/smtp-settings`) to fill in your mail server and test the connection
before sending anything.

## Manual entry only

There is no polling, no webhook, no API connection to Auto Detection,
Smart Gate, RRM, HMM, or Urban Eye anywhere in this codebase. The reporter
checks each platform and types the result into the Add Incident form or
the Platform Details page. Export exists for moving your own typed data
around, not for pulling live data from anywhere.

## Colors and fonts

The plum and teal palette (`#400938` and `#5A214F` for the plum, `#5CF9F1`
and `#00B3A4` for the teal) is used consistently throughout, in a single
shared stylesheet at `frontend/static/css/design.css`.

Fonts (IBM Plex Sans, JetBrains Mono, Material Symbols Outlined) are
self-hosted under `frontend/static/vendor/fonts/`, not pulled from Google
Fonts or a CDN. The app runs correctly with outbound network access
blocked entirely, so it works on a machine with no internet connection.

## English only

Every page and the email are English only.

## If you want to change the frontend again later

The backend does not care what frontend calls it. Every page talks to the
same JSON API:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/platforms` | GET, POST | List all platforms, or add one |
| `/api/platforms/<id>` | GET, PUT, DELETE | Read, update, or remove one platform |
| `/api/platforms/<id>/incidents` | POST | Create an incident for a platform |
| `/api/incidents` | GET | List incidents, optionally filtered by platform |
| `/api/incidents/<id>` | GET, PUT | Read or correct one incident |
| `/api/incidents/export.csv` | GET | CSV export, optionally a specific set of ids |
| `/api/logs` | GET | Field-level audit log entries |
| `/api/summary` | GET | Total, healthy, warning, critical counts, current cycle |
| `/api/dashboard` | GET | Everything the Dashboard Overview page needs for a given range |
| `/api/charts/metrics` | GET | Per-platform detections, frames, latency, cameras |
| `/api/email/preview` | GET | Returns `{html, text}` for the current data |
| `/api/email/send` | POST | Sends the report, optionally with edited content and attached records |
| `/api/automation` | GET, POST | Read or save the automated-send settings |
| `/api/smtp` | GET, POST | Read (masked) or save SMTP configuration |
| `/api/app-settings` | GET, POST | Screenshot compression, default identity, email signature |
| `/api/backups` | GET | List existing backups |
| `/api/backups/run` | POST | Create a backup now |
| `/api/backup-settings` | GET, POST | Read or save the automatic backup schedule |
| `/api/export` | GET | Downloads the live `.xlsx` workbook |

CORS is already enabled, so a different frontend running on a different
local port could call this same API directly.
