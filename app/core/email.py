import resend

from app.api.v1.auth.schemas import EmailPayload
from app.core.config import settings


async def send_email(payload: EmailPayload):
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
