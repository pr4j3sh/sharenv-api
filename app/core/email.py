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
