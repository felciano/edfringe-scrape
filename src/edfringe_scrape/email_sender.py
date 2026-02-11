"""Email sending functionality for daily updates."""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    from_email: str | None = None,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
) -> bool:
    """Send an email with optional HTML body.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        text_body: Plain text body
        html_body: Optional HTML body
        from_email: Sender email (defaults to smtp_user)
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port (587 for TLS, 465 for SSL)
        smtp_user: SMTP username
        smtp_password: SMTP password or app password

    Returns:
        True if email sent successfully, False otherwise
    """
    if not smtp_user or not smtp_password:
        logger.error("SMTP credentials not configured")
        return False

    from_email = from_email or smtp_user

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    # Attach text part
    text_part = MIMEText(text_body, "plain")
    msg.attach(text_part)

    # Attach HTML part if provided
    if html_body:
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

    try:
        # Create secure connection
        context = ssl.create_default_context()

        if smtp_port == 465:
            # SSL connection
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())
        else:
            # TLS connection (port 587)
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
