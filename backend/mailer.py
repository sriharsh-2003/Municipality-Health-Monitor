"""
mailer.py

Thin wrapper around smtplib. Nothing here talks to any cloud service. It
only talks to the mail server the reporter puts in config.json.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


def send_email(smtp_config, recipient, subject, html_body, text_body, attachment_bytes=None, attachment_name=None, extra_attachments=None):
    """
    extra_attachments: optional list of (filename, bytes, subtype) tuples for
    additional files beyond the single legacy attachment_bytes/attachment_name pair.
    """
    host = smtp_config.get("smtp_host")
    port = int(smtp_config.get("smtp_port", 587))
    username = smtp_config.get("smtp_username")
    password = smtp_config.get("smtp_password")
    use_tls = smtp_config.get("use_tls", True)
    from_address = smtp_config.get("from_address") or username

    if not host or not username or not password:
        raise ValueError("SMTP settings are incomplete. Fill smtp_host, smtp_username, and smtp_password in config.json.")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = recipient

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if attachment_bytes is not None:
        part = MIMEApplication(attachment_bytes, _subtype="xlsx")
        part.add_header("Content-Disposition", "attachment", filename=attachment_name or "platform-health-export.xlsx")
        msg.attach(part)

    for filename, data, subtype in (extra_attachments or []):
        part = MIMEApplication(data, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(from_address, [recipient], msg.as_string())
