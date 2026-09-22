"""
email_builder.py

Builds the status email from the current platform list. Used by the
/api/email/preview and /api/email/send routes, and by the scheduler for
automated sends, so the preview the reporter checks is exactly what goes out.

The HTML is table based with inline styles on purpose. That is what actually
renders correctly in Outlook, Gmail, and Apple Mail. It is not the same
markup as the in-app dashboard, which is normal for email.
"""

STATUS_LABEL = {"Healthy": "Healthy", "Degraded": "Warning", "Down": "Critical"}
STATUS_COLOR = {"Healthy": "#2E7D32", "Degraded": "#F9A825", "Down": "#C62828"}
STATUS_BG = {"Healthy": "#E8F5E9", "Degraded": "#FFF8E1", "Down": "#FFEBEE"}


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


def build_email(platforms, sender_name="Reporter", recipient_name="Manager", incidents_by_platform=None,
                 base_url="", sender_title="", sender_org=""):
    incidents_by_platform = incidents_by_platform or {}
    healthy = [p for p in platforms if p.get("health") == "Healthy"]
    warning = [p for p in platforms if p.get("health") == "Degraded"]
    critical = [p for p in platforms if p.get("health") == "Down"]
    issues = [p for p in platforms if p.get("health") != "Healthy"]

    html = _build_html(platforms, healthy, warning, critical, issues, sender_name, recipient_name, incidents_by_platform, base_url, sender_title, sender_org)
    text = _build_text(platforms, healthy, warning, critical, issues, sender_name, recipient_name, incidents_by_platform, base_url, sender_title, sender_org)
    return {"html": html, "text": text, "summary": {"healthy": len(healthy), "warning": len(warning), "critical": len(critical)}}


def _screenshot_urls(platform_id, incidents_by_platform, base_url):
    inc = incidents_by_platform.get(platform_id)
    if not inc or not inc.get("screenshots"):
        return []
    return [f"{base_url}/attachments/{inc['id']}/{name}" for name in inc["screenshots"]]


def _build_html(platforms, healthy, warning, critical, issues, sender_name, recipient_name, incidents_by_platform, base_url, sender_title="", sender_org=""):
    rows = "".join(f"""
    <tr>
      <td style="padding:10px 14px;border-bottom:1px solid #D9E0E6;font:14px/1.4 Arial,sans-serif;color:#1D2939;">{escape_html(p.get('project_name'))}</td>
      <td style="padding:10px 14px;border-bottom:1px solid #D9E0E6;text-align:center;">
        <span style="display:inline-block;padding:3px 10px;border-radius:4px;font:700 12px Arial,sans-serif;color:{STATUS_COLOR[p.get('health')]};background:{STATUS_BG[p.get('health')]};">{STATUS_LABEL[p.get('health')]}</span>
      </td>
    </tr>""" for p in platforms)

    if issues:
        issue_blocks_parts = []
        for p in issues:
            shots = _screenshot_urls(p.get("id"), incidents_by_platform, base_url)
            if shots:
                thumbs = "".join(f"""
                <a href="{url}" style="display:inline-block;margin:8px 8px 0 0;" target="_blank">
                  <img src="{url}" width="120" height="80" style="width:120px;height:80px;object-fit:cover;border-radius:4px;border:1px solid #D9E0E6;display:block;" alt="Incident screenshot">
                </a>""" for url in shots)
                shots_html = f'<div style="margin-top:8px;">{thumbs}</div>'
            else:
                shots_html = ""
            issue_blocks_parts.append(f"""
        <tr>
          <td style="padding:14px 0;border-left:3px solid {STATUS_COLOR[p.get('health')]};padding-left:14px;">
            <div style="font:700 14px Arial,sans-serif;color:#1D2939;margin-bottom:4px;">{escape_html(p.get('project_name'))}, {STATUS_LABEL[p.get('health')]}</div>
            <div style="font:14px/1.5 Arial,sans-serif;color:#667085;">{escape_html(p.get('notes')) or 'No details provided.'}</div>
            {shots_html}
          </td>
        </tr>""")
        issue_blocks = "".join(issue_blocks_parts)
    else:
        issue_blocks = '<tr><td style="font:14px Arial,sans-serif;color:#667085;padding:6px 0;">No warnings or critical issues to report.</td></tr>'

    if critical:
        support_line = "Support needed. Please advise on escalation for " + ", ".join(escape_html(p.get("project_name")) for p in critical) + "."
    elif warning:
        support_line = "Support needed: none at this time. Will flag if warnings are not resolved by the next check."
    else:
        support_line = "Support needed: none at this time."

    overview_line = "flagged for attention below" if critical else ("mostly healthy, with items flagged for attention below" if warning else "fully healthy")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Municipality Digital Operations Status Update</title></head>
<body style="margin:0;padding:0;background:#F6F8FA;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F8FA;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:4px;overflow:hidden;border:1px solid #D9E0E6;">

<tr><td style="background:#5A214F;padding:22px 28px;">
  <div style="font:700 11px/1 Arial,sans-serif;letter-spacing:1.5px;color:#27D7D0;text-transform:uppercase;margin-bottom:6px;">Status Report</div>
  <div style="font:700 19px/1.3 Arial,sans-serif;color:#ffffff;">Municipality platform health, operational status</div>
</td></tr>

<tr><td style="padding:20px 28px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font:13px/1.6 Arial,sans-serif;color:#667085;">
    <tr><td style="width:70px;color:#667085;">To</td><td style="color:#1D2939;font-weight:600;">{escape_html(recipient_name)}</td></tr>
    <tr><td style="color:#667085;">From</td><td style="color:#1D2939;font-weight:600;">{escape_html(sender_name)}</td></tr>
    <tr><td style="color:#667085;">Subject</td><td style="color:#1D2939;font-weight:600;">Municipality Digital Operations Status Update</td></tr>
  </table>
</td></tr>

<tr><td style="padding:20px 28px 4px;">
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 6px;">Hi,</p>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0 0 18px;">Sharing the current status across the monitored platform portfolio. Overall, the portfolio is {overview_line}.</p>
</td></tr>

<tr><td style="padding:0 28px 18px;">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr>
    <td style="padding-right:22px;font:700 13px Arial,sans-serif;color:#2E7D32;">&#9679; {len(healthy)} healthy</td>
    <td style="padding-right:22px;font:700 13px Arial,sans-serif;color:#F9A825;">&#9679; {len(warning)} warning</td>
    <td style="font:700 13px Arial,sans-serif;color:#C62828;">&#9679; {len(critical)} critical</td>
  </tr></table>
</td></tr>

<tr><td style="padding:0 28px 8px;">
  <div style="font:700 11px Arial,sans-serif;letter-spacing:1px;color:#667085;text-transform:uppercase;margin-bottom:10px;">Platform status</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #D9E0E6;">
    {rows}
  </table>
</td></tr>

<tr><td style="padding:22px 28px 8px;">
  <div style="font:700 11px Arial,sans-serif;letter-spacing:1px;color:#667085;text-transform:uppercase;margin-bottom:10px;">Issues and follow up</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{issue_blocks}</table>
</td></tr>

<tr><td style="padding:14px 28px 22px;">
  <div style="font:700 11px Arial,sans-serif;letter-spacing:1px;color:#667085;text-transform:uppercase;margin-bottom:8px;">Support needed</div>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0;">{support_line}</p>
</td></tr>

<tr><td style="padding:0 28px 22px;">
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:0;">Full field level detail is attached as the export.</p>
  <p style="font:14px/1.6 Arial,sans-serif;color:#1D2939;margin:14px 0 0;">Thanks,<br>{escape_html(sender_name)}{f'<br><span style="color:#667085;">{escape_html(sender_title)}</span>' if sender_title else ''}{f'<br><span style="color:#667085;">{escape_html(sender_org)}</span>' if sender_org else ''}</p>
</td></tr>

<tr><td style="padding:16px 28px;border-top:1px solid #D9E0E6;background:#F6F8FA;">
  <p style="font:12px Arial,sans-serif;color:#667085;margin:0;">Municipality Digital Operations, Platform Health Monitoring</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _build_text(platforms, healthy, warning, critical, issues, sender_name, recipient_name, incidents_by_platform, base_url, sender_title="", sender_org=""):
    def issue_line(p):
        base = f"- {p.get('project_name')} ({STATUS_LABEL[p.get('health')]}): {p.get('notes') or 'No details provided.'}"
        shots = _screenshot_urls(p.get("id"), incidents_by_platform, base_url)
        if shots:
            base += "\n  Screenshots: " + ", ".join(shots)
        return base

    signature_lines = [sender_name]
    if sender_title:
        signature_lines.append(sender_title)
    if sender_org:
        signature_lines.append(sender_org)

    lines = [
        "Hi,", "",
        "Sharing the current status across the monitored platform portfolio.", "",
        f"Summary: {len(healthy)} healthy, {len(warning)} warning, {len(critical)} critical", "",
        "PLATFORM STATUS",
        *[f"- {p.get('project_name')}: {STATUS_LABEL[p.get('health')]}" for p in platforms], "",
        "ISSUES AND FOLLOW UP",
        *([issue_line(p) for p in issues] if issues else ["None. All platforms healthy."]), "",
        "SUPPORT NEEDED",
        ("Please advise on escalation for " + ", ".join(p.get("project_name") for p in critical) + "." if critical else "None at this time."), "",
        "Full field level detail is attached as the export.", "",
        "Thanks,", *signature_lines, "",
        "Municipality Digital Operations, Platform Health Monitoring",
    ]
    return "\n".join(lines)
