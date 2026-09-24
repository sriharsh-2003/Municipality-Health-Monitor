"""
email_builder.py

Builds the status email. Used by the /api/email/preview and
/api/email/send routes, and by the scheduler for automated sends, so the
preview the reporter checks is exactly what goes out.

Three report types share the same visual language (header, colors,
signature) but have genuinely different content and table structure,
not just a different date range on the same layout:

- daily: a flat table of every incident logged today, newest first.
- weekly: severity/status totals for the week, plus the week's incident
  table.
- monthly: an executive rollup, incidents grouped per platform (a raw
  30-day incident list would be too long to be useful), plus which
  platforms saw the most activity.

The HTML is table based with inline styles on purpose. That is what
actually renders correctly in Outlook, Gmail, and Apple Mail. It is not
the same markup as the in-app dashboard, which is normal for email.
"""

STATUS_LABEL = {"Healthy": "Healthy", "Degraded": "Warning", "Down": "Critical"}
STATUS_COLOR = {"Healthy": "#2E7D32", "Degraded": "#F9A825", "Down": "#C62828"}
STATUS_BG = {"Healthy": "#E8F5E9", "Degraded": "#FFF8E1", "Down": "#FFEBEE"}

INCIDENT_STATUS_COLOR = {"Open": "#C62828", "Acknowledged": "#8E5B00", "In Progress": "#B45309", "Resolved": "#2E7D32"}
INCIDENT_STATUS_BG = {"Open": "#FFEBEE", "Acknowledged": "#FFF3E0", "In Progress": "#FFF8E1", "Resolved": "#E8F5E9"}

REPORT_TITLES = {"daily": "Daily Status Report", "weekly": "Weekly Status Report", "monthly": "Monthly Status Report"}

DEFAULT_TAGLINE = "Municipality platform health, operational status"


def escape_html(value):
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html_to_text(html):
    """Rough plain-text fallback for a hand-edited HTML email body."""
    import re
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|table|td|th|li|h1|h2|h3|h4|h5|h6)>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _screenshot_urls(incident, base_url):
    if not incident or not incident.get("screenshots"):
        return []
    return [f"{base_url}/attachments/{incident['id']}/{name}" for name in incident["screenshots"]]


def _screenshot_link_html(inc, base_url):
    urls = _screenshot_urls(inc, base_url)
    if not urls:
        return ""
    first = urls[0]
    more = f" (+{len(urls) - 1} more)" if len(urls) > 1 else ""
    return f'<div style="margin-top:3px;"><a href="{first}" style="font:11.5px Arial,sans-serif;color:#00897B;" target="_blank">View screenshot{more}</a></div>'


def _section_label_html(text):
    return f'<div style="font:700 11px Arial,sans-serif;letter-spacing:1px;color:#667085;text-transform:uppercase;margin-bottom:10px;">{escape_html(text)}</div>'


def _incident_status_pill_html(status):
    status = status or "Open"
    color = INCIDENT_STATUS_COLOR.get(status, "#667085")
    bg = INCIDENT_STATUS_BG.get(status, "#F6F8FA")
    return f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;font:700 11px Arial,sans-serif;color:{color};background:{bg};">{escape_html(status)}</span>'


def _health_pill_html(health):
    color = STATUS_COLOR.get(health, "#667085")
    bg = STATUS_BG.get(health, "#F6F8FA")
    return f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;font:700 11px Arial,sans-serif;color:{color};background:{bg};">{escape_html(STATUS_LABEL.get(health, health or ""))}</span>'


def build_email(platforms, incidents=None, report_type="daily", period_label="",
                 sender_name="Reporter", recipient_name="Manager", base_url="",
                 sender_title="", sender_org="", tagline=""):
    """
    incidents: the incidents that fall inside the report's period (already
    filtered by the caller), newest first.
    period_label: a human string for the header, e.g. "Wed, 24 Sep 2026" or
    "15 to 21 Sep 2026" or "September 2026". Caller computes this since it
    depends on wall-clock date, which the builder should not need to know.
    """
    incidents = incidents or []
    healthy = [p for p in platforms if p.get("health") == "Healthy"]
    warning = [p for p in platforms if p.get("health") == "Degraded"]
    critical = [p for p in platforms if p.get("health") == "Down"]

    builders = {"daily": _build_daily, "weekly": _build_weekly, "monthly": _build_monthly}
    builder = builders.get(report_type, _build_daily)
    html, text = builder(
        platforms, healthy, warning, critical, incidents, period_label,
        sender_name, recipient_name, base_url, sender_title, sender_org, tagline or DEFAULT_TAGLINE,
    )
    return {
        "html": html, "text": text,
        "summary": {"healthy": len(healthy), "warning": len(warning), "critical": len(critical), "incident_count": len(incidents)},
    }


def _shell_html(report_type, period_label, recipient_name, sender_name, tagline, body_html, sender_title="", sender_org=""):
    signature_block = f"Thanks,<br>{escape_html(sender_name)}"
    if sender_title:
        signature_block += f'<br><span style="color:#667085;">{escape_html(sender_title)}</span>'
    if sender_org:
        signature_block += f'<br><span style="color:#667085;">{escape_html(sender_org)}</span>'

    title = REPORT_TITLES.get(report_type, "Status Report")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{escape_html(title)}</title></head>
<body style="margin:0;padding:0;background:#F6F8FA;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F8FA;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:4px;overflow:hidden;border:1px solid #D9E0E6;">

<tr><td style="background:#5A214F;padding:22px 28px;">
  <div style="font:700 11px/1 Arial,sans-serif;letter-spacing:1.5px;color:#27D7D0;text-transform:uppercase;margin-bottom:6px;">{escape_html(title)}</div>
  <div style="font:700 19px/1.3 Arial,sans-serif;color:#ffffff;">{escape_html(tagline)}</div>
  <div style="font:13px Arial,sans-serif;color:#E9D5E3;margin-top:6px;">{escape_html(period_label)}</div>
</td></tr>

<tr><td style="padding:20px 28px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font:13px/1.6 Arial,sans-serif;color:#667085;">
    <tr><td style="width:70px;color:#667085;">To</td><td style="color:#1D2939;font-weight:600;">{escape_html(recipient_name)}</td></tr>
    <tr><td style="color:#667085;">From</td><td style="color:#1D2939;font-weight:600;">{escape_html(sender_name)}</td></tr>
  </table>
</td></tr>

{body_html}

<tr><td style="padding:14px 28px 22px;">
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0;">Full field level detail is attached as the export.</p>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:14px 0 0;">{signature_block}</p>
</td></tr>

<tr><td style="padding:16px 28px;border-top:1px solid #D9E0E6;background:#F6F8FA;">
  <p style="font:12px Arial,sans-serif;color:#667085;margin:0;">Municipality Digital Operations, Platform Health Monitoring</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _platform_status_table_html(platforms):
    rows = "".join(f"""
    <tr>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:13px/1.4 Arial,sans-serif;color:#1D2939;">{escape_html(p.get('project_name'))}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;text-align:center;">{_health_pill_html(p.get('health'))}</td>
    </tr>""" for p in platforms)
    return f"""
<tr><td style="padding:20px 28px 8px;">
  {_section_label_html("Platform status")}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #D9E0E6;">
    {rows}
  </table>
</td></tr>"""


def _summary_counts_html(healthy, warning, critical):
    return f"""
<tr><td style="padding:0 28px 18px;">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr>
    <td style="padding-right:22px;font:700 13px Arial,sans-serif;color:#2E7D32;">&#9679; {len(healthy)} healthy</td>
    <td style="padding-right:22px;font:700 13px Arial,sans-serif;color:#F9A825;">&#9679; {len(warning)} warning</td>
    <td style="font:700 13px Arial,sans-serif;color:#C62828;">&#9679; {len(critical)} critical</td>
  </tr></table>
</td></tr>"""


# ------------------------------------------------------------------ daily

def _build_daily(platforms, healthy, warning, critical, incidents, period_label, sender_name, recipient_name, base_url, sender_title, sender_org, tagline):
    greeting = f"""
<tr><td style="padding:20px 28px 4px;">
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 6px;">Hi,</p>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 18px;">{"Here is a summary of today's activity across the monitored platform portfolio." if incidents else "No incidents were logged today. The portfolio has been quiet."}</p>
</td></tr>"""

    incident_rows = "".join(f"""
    <tr>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:12.5px Arial,sans-serif;color:#667085;white-space:nowrap;">{escape_html((inc.get('timestamp') or '')[11:16])}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:13px Arial,sans-serif;color:#1D2939;font-weight:600;">{escape_html(inc.get('project_name'))}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;text-align:center;">{_incident_status_pill_html(inc.get('status'))}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:12.5px Arial,sans-serif;color:#667085;">{escape_html(inc.get('severity') or 'Not set')}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:12.5px/1.5 Arial,sans-serif;color:#1D2939;">{escape_html((inc.get('notes') or 'No details provided.')[:140])}{_screenshot_link_html(inc, base_url)}</td>
    </tr>""" for inc in incidents)

    if incidents:
        incident_table = f"""
<tr><td style="padding:22px 28px 8px;">
  {_section_label_html("Today's incidents")}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #D9E0E6;">
    <tr>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">TIME</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">PLATFORM</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;text-align:center;">STATUS</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">SEVERITY</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">NOTES</td>
    </tr>
    {incident_rows}
  </table>
</td></tr>"""
    else:
        incident_table = f"""
<tr><td style="padding:22px 28px 8px;">
  {_section_label_html("Today's incidents")}
  <p style="font:14px Arial,sans-serif;color:#667085;margin:0;">Nothing logged today.</p>
</td></tr>"""

    body = greeting + _summary_counts_html(healthy, warning, critical) + incident_table + _platform_status_table_html(platforms)
    html = _shell_html("daily", period_label, recipient_name, sender_name, tagline, body, sender_title, sender_org)

    lines = [
        "Hi,", "",
        "Here is a summary of today's activity across the monitored platform portfolio." if incidents else "No incidents were logged today. The portfolio has been quiet.", "",
        f"Summary: {len(healthy)} healthy, {len(warning)} warning, {len(critical)} critical", "",
        "TODAY'S INCIDENTS",
    ]
    if incidents:
        for inc in incidents:
            line = f"- {(inc.get('timestamp') or '')[11:16]} {inc.get('project_name')}, {inc.get('status') or 'Open'}, {inc.get('severity') or 'Not set'}: {inc.get('notes') or 'No details provided.'}"
            shots = _screenshot_urls(inc, base_url)
            if shots:
                line += "\n  Screenshots: " + ", ".join(shots)
            lines.append(line)
    else:
        lines.append("Nothing logged today.")
    lines += ["", "PLATFORM STATUS", *[f"- {p.get('project_name')}: {STATUS_LABEL[p.get('health')]}" for p in platforms]]
    text = _finish_text(lines, sender_name, sender_title, sender_org)
    return html, text


# ----------------------------------------------------------------- weekly

def _build_weekly(platforms, healthy, warning, critical, incidents, period_label, sender_name, recipient_name, base_url, sender_title, sender_org, tagline):
    by_severity = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Not set": 0}
    resolved_count = 0
    for inc in incidents:
        by_severity[inc.get("severity") or "Not set"] = by_severity.get(inc.get("severity") or "Not set", 0) + 1
        if (inc.get("status") or "Open") == "Resolved":
            resolved_count += 1
    still_open = len(incidents) - resolved_count

    greeting = f"""
<tr><td style="padding:20px 28px 4px;">
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 6px;">Hi,</p>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 18px;">Sharing the week's activity across the monitored platform portfolio.</p>
</td></tr>"""

    stats_html = f"""
<tr><td style="padding:0 28px 18px;">
  {_section_label_html("This week at a glance")}
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#1D2939;">{len(incidents)}</div><div style="font:11px Arial,sans-serif;color:#667085;">incidents logged</div></td>
    <td style="width:10px;"></td>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#2E7D32;">{resolved_count}</div><div style="font:11px Arial,sans-serif;color:#667085;">resolved</div></td>
    <td style="width:10px;"></td>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#B45309;">{still_open}</div><div style="font:11px Arial,sans-serif;color:#667085;">still open</div></td>
    <td style="width:10px;"></td>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#C62828;">{by_severity.get('Critical', 0)}</div><div style="font:11px Arial,sans-serif;color:#667085;">critical severity</div></td>
  </tr></table>
</td></tr>"""

    incident_rows = "".join(f"""
    <tr>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:12.5px Arial,sans-serif;color:#667085;white-space:nowrap;">{escape_html((inc.get('timestamp') or '')[:10])}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:13px Arial,sans-serif;color:#1D2939;font-weight:600;">{escape_html(inc.get('project_name'))}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:12.5px Arial,sans-serif;color:#667085;">{escape_html(inc.get('category') or 'Not set')}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;text-align:center;">{_incident_status_pill_html(inc.get('status'))}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:12.5px Arial,sans-serif;color:#667085;">{escape_html(inc.get('severity') or 'Not set')}{_screenshot_link_html(inc, base_url)}</td>
    </tr>""" for inc in incidents)

    if incidents:
        incident_table = f"""
<tr><td style="padding:6px 28px 8px;">
  {_section_label_html("This week's incidents")}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #D9E0E6;">
    <tr>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">DATE</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">PLATFORM</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">CATEGORY</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;text-align:center;">STATUS</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">SEVERITY</td>
    </tr>
    {incident_rows}
  </table>
</td></tr>"""
    else:
        incident_table = f"""
<tr><td style="padding:6px 28px 8px;">
  {_section_label_html("This week's incidents")}
  <p style="font:14px Arial,sans-serif;color:#667085;margin:0;">Nothing logged this week.</p>
</td></tr>"""

    body = greeting + stats_html + incident_table + _platform_status_table_html(platforms)
    html = _shell_html("weekly", period_label, recipient_name, sender_name, tagline, body, sender_title, sender_org)

    lines = [
        "Hi,", "",
        "Sharing the week's activity across the monitored platform portfolio.", "",
        f"This week: {len(incidents)} incidents logged, {resolved_count} resolved, {still_open} still open, {by_severity.get('Critical', 0)} critical severity", "",
        "THIS WEEK'S INCIDENTS",
    ]
    if incidents:
        for inc in incidents:
            line = f"- {(inc.get('timestamp') or '')[:10]} {inc.get('project_name')}, {inc.get('category') or 'Not set'}, {inc.get('status') or 'Open'}, {inc.get('severity') or 'Not set'}"
            shots = _screenshot_urls(inc, base_url)
            if shots:
                line += "\n  Screenshots: " + ", ".join(shots)
            lines.append(line)
    else:
        lines.append("Nothing logged this week.")
    lines += ["", "PLATFORM STATUS", *[f"- {p.get('project_name')}: {STATUS_LABEL[p.get('health')]}" for p in platforms]]
    text = _finish_text(lines, sender_name, sender_title, sender_org)
    return html, text


# ---------------------------------------------------------------- monthly

def _build_monthly(platforms, healthy, warning, critical, incidents, period_label, sender_name, recipient_name, base_url, sender_title, sender_org, tagline):
    resolved_count = sum(1 for inc in incidents if (inc.get("status") or "Open") == "Resolved")
    critical_count = sum(1 for inc in incidents if inc.get("severity") == "Critical")
    resolution_rate = round((resolved_count / len(incidents)) * 100) if incidents else 100

    per_platform = {}
    for inc in incidents:
        name = inc.get("project_name") or inc.get("platform_id")
        entry = per_platform.setdefault(name, {"count": 0, "critical": 0, "open": 0})
        entry["count"] += 1
        if inc.get("severity") == "Critical":
            entry["critical"] += 1
        if (inc.get("status") or "Open") != "Resolved":
            entry["open"] += 1
    ranked = sorted(per_platform.items(), key=lambda kv: kv[1]["count"], reverse=True)

    greeting = f"""
<tr><td style="padding:20px 28px 4px;">
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 6px;">Hi,</p>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 18px;">A monthly rollup across the monitored platform portfolio. {len(incidents)} incidents were logged this month, with a {resolution_rate}% resolution rate.</p>
</td></tr>"""

    stats_html = f"""
<tr><td style="padding:0 28px 18px;">
  {_section_label_html("This month at a glance")}
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#1D2939;">{len(incidents)}</div><div style="font:11px Arial,sans-serif;color:#667085;">total incidents</div></td>
    <td style="width:10px;"></td>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#2E7D32;">{resolution_rate}%</div><div style="font:11px Arial,sans-serif;color:#667085;">resolution rate</div></td>
    <td style="width:10px;"></td>
    <td style="padding:12px 16px;background:#F6F8FA;border-radius:6px;"><div style="font:700 22px Arial,sans-serif;color:#C62828;">{critical_count}</div><div style="font:11px Arial,sans-serif;color:#667085;">critical severity</div></td>
  </tr></table>
</td></tr>"""

    rollup_rows = "".join(f"""
    <tr>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;font:13px Arial,sans-serif;color:#1D2939;font-weight:600;">{escape_html(name)}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;text-align:center;font:13px Arial,sans-serif;color:#1D2939;">{data['count']}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;text-align:center;font:13px Arial,sans-serif;color:#C62828;">{data['critical']}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #D9E0E6;text-align:center;font:13px Arial,sans-serif;color:#B45309;">{data['open']}</td>
    </tr>""" for name, data in ranked[:12])

    if ranked:
        rollup_table = f"""
<tr><td style="padding:6px 28px 8px;">
  {_section_label_html("Incidents by platform")}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #D9E0E6;">
    <tr>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;">PLATFORM</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;text-align:center;">INCIDENTS</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;text-align:center;">CRITICAL</td>
      <td style="padding:6px 14px;font:700 11px Arial,sans-serif;color:#667085;text-align:center;">STILL OPEN</td>
    </tr>
    {rollup_rows}
  </table>
</td></tr>"""
    else:
        rollup_table = f"""
<tr><td style="padding:6px 28px 8px;">
  {_section_label_html("Incidents by platform")}
  <p style="font:14px Arial,sans-serif;color:#667085;margin:0;">Nothing logged this month.</p>
</td></tr>"""

    body = greeting + stats_html + rollup_table + _platform_status_table_html(platforms)
    html = _shell_html("monthly", period_label, recipient_name, sender_name, tagline, body, sender_title, sender_org)

    lines = [
        "Hi,", "",
        f"A monthly rollup across the monitored platform portfolio. {len(incidents)} incidents were logged this month, with a {resolution_rate}% resolution rate.", "",
        f"This month: {len(incidents)} total incidents, {resolution_rate}% resolved, {critical_count} critical severity", "",
        "INCIDENTS BY PLATFORM",
    ]
    if ranked:
        for name, data in ranked[:12]:
            lines.append(f"- {name}: {data['count']} incidents, {data['critical']} critical, {data['open']} still open")
    else:
        lines.append("Nothing logged this month.")
    lines += ["", "PLATFORM STATUS", *[f"- {p.get('project_name')}: {STATUS_LABEL[p.get('health')]}" for p in platforms]]
    text = _finish_text(lines, sender_name, sender_title, sender_org)
    return html, text


def _finish_text(lines, sender_name, sender_title, sender_org):
    signature_lines = [sender_name]
    if sender_title:
        signature_lines.append(sender_title)
    if sender_org:
        signature_lines.append(sender_org)
    lines += [
        "", "Full field level detail is attached as the export.", "",
        "Thanks,", *signature_lines, "",
        "Municipality Digital Operations, Platform Health Monitoring",
    ]
    return "\n".join(lines)
