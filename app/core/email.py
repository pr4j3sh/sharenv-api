import resend

from app.api.v1.auth.schemas import EmailPayload
from app.core.config import settings
from app.core.logger import get_logger

log = get_logger(__name__)


async def send_email(payload: EmailPayload):
    if settings.DEBUG:
        # Dev-only escape hatch so registration/verification can be exercised
        # without a real mail provider. Never enable DEBUG in production:
        # this logs the OTP.
        log.info("DEBUG mode: skipping email delivery, otp=%s", payload.otp)
        return {"id": "debug"}

    resend.api_key = settings.RESEND_API_KEY
    res = resend.Emails.send(
        {
            "from": settings.EMAIL_FROM,
            "to": [payload.to],
            "subject": payload.subject,
            "html": f"<p><span>OTP:</span>&nbsp;<b>{payload.otp}</b></p>",
        }
    )
    return res


async def send_invitation_email(to: str, project_name: str, role: str, token: str):
    if settings.DEBUG:
        # Dev-only: never log invitation tokens outside DEBUG.
        log.info(
            "DEBUG mode: skipping email delivery, invitation_token=%s to=%s project=%s role=%s",
            token,
            to,
            project_name,
            role,
        )
        return {"id": "debug"}

    resend.api_key = settings.RESEND_API_KEY
    res = resend.Emails.send(
        {
            "from": settings.EMAIL_FROM,
            "to": [to],
            "subject": f"Invitation to join {project_name}",
            "html": (
                f"<p>You have been invited to join <b>{project_name}</b> "
                f"as <b>{role}</b>.</p>"
                f"<p>Use this invitation token to accept:</p>"
                f"<p><b>{token}</b></p>"
            ),
        }
    )
    return res
