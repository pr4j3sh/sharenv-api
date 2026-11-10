from email.message import EmailMessage

import aiosmtplib
import resend

from app.api.v1.auth.schemas import EmailPayload
from app.core.config import settings
from app.core.logger import get_logger

log = get_logger(__name__)


async def _send_via_smtp(to: str, subject: str, html: str) -> dict:
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    tls = settings.SMTP_TLS
    smtp = aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        timeout=settings.SMTP_TIMEOUT,
        use_tls=(tls == "ssl"),
    )
    async with smtp:
        if tls == "starttls":
            await smtp.starttls()
        if settings.SMTP_USER:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        await smtp.send_message(msg)
    return {"id": "smtp"}


async def _deliver(to: str, subject: str, html: str, kind: str, secret: str) -> dict:
    provider = settings.EMAIL_PROVIDER

    if settings.DEBUG or provider == "console":
        # Dev-only escape hatch so registration/verification can be exercised
        # without a real mail provider. Never enable DEBUG in production:
        # this logs the secret.
        log.info("console email provider: kind=%s to=%s secret=%s", kind, to, secret)
        return {"id": "console"}

    if provider == "resend":
        resend.api_key = settings.RESEND_API_KEY
        res = resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )
        return res

    if provider == "smtp":
        return await _send_via_smtp(to, subject, html)

    # "none": callers must not invoke delivery when no provider is configured.
    raise RuntimeError("email provider is not configured (EMAIL_PROVIDER=none)")


async def send_email(payload: EmailPayload):
    return await _deliver(
        to=payload.to,
        subject=payload.subject,
        html=f"<p><span>OTP:</span>&nbsp;<b>{payload.otp}</b></p>",
        kind="otp",
        secret=payload.otp,
    )


async def send_invitation_email(to: str, project_name: str, role: str, token: str):
    return await _deliver(
        to=to,
        subject=f"Invitation to join {project_name}",
        html=(
            f"<p>You have been invited to join <b>{project_name}</b> "
            f"as <b>{role}</b>.</p>"
            f"<p>Use this invitation token to accept:</p>"
            f"<p><b>{token}</b></p>"
        ),
        kind="invitation",
        secret=token,
    )
