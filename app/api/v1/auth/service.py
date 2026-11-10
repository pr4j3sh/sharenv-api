from datetime import datetime, timedelta

from bson import ObjectId

from app.api.v1.auth.exceptions import (
    CreateTokenError,
    InvalidCredentials,
    RegisterError,
    ResendOtpError,
    SendEmailError,
    UserAlreadyExists,
    UserAlreadyVerified,
    UserNotFound,
    UserNotVerified,
    VerifyOtpError,
)
from app.api.v1.auth.models import UserModel
from app.api.v1.auth.schemas import (
    EmailPayload,
    LoginReq,
    LoginRes,
    RegisterReq,
    RegisterRes,
    ResendOtpRes,
    VerifyUserRes,
)
from app.core.config import settings
from app.core.crypto import generate_otp, hash_otp, verify_otp
from app.core.email import send_email
from app.core.logger import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Auth:
    def __init__(self) -> None:
        self.db = mongo

    async def _rollback_registration(self, user_id: ObjectId) -> None:
        try:
            await self.db.users.delete_one({"_id": user_id})
        except Exception:
            log.exception("failed to roll back registration for %s", user_id)

    async def register(self, payload: RegisterReq) -> RegisterRes:
        log.info(f"registering user {payload.email}")
        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        email = payload.email.strip().lower()

        user_exists = await self.db.users.find_one({"email": email})
        if user_exists:
            raise UserAlreadyExists("User already exists")

        otp = generate_otp()
        now = get_current_time()
        user_payload = UserModel(
            email=email,
            password=hash_password(payload.password),
            otp=hash_otp(otp),
            otp_expiry=now + timedelta(minutes=settings.OTP_EXPIRY),
        )

        user = await self.db.users.insert_one(
            user_payload.model_dump(
                by_alias=True,
                exclude_none=True,
            )
        )

        if not user or not user.inserted_id:
            raise RegisterError("Failed to register user")

        try:
            res = await send_email(payload=EmailPayload(to=email, otp=otp))
        except Exception as e:
            await self._rollback_registration(user.inserted_id)
            raise SendEmailError("Failed to send email") from e

        if not res.get("id"):
            await self._rollback_registration(user.inserted_id)
            raise SendEmailError("Failed to send email")

        return RegisterRes(success=True, user_id=str(user.inserted_id))

    async def verify_user(self, user_id: str, otp: str) -> VerifyUserRes:
        log.info(f"verifying user {user_id}")

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise UserNotFound("User does not exist")

        if user.get("is_verified"):
            raise UserAlreadyVerified("User is already verified")

        stored_otp = user.get("otp")
        otp_expiry = user.get("otp_expiry")

        if not stored_otp or not otp_expiry:
            raise VerifyOtpError("no active otp")

        now = get_current_time()

        if now >= datetime.fromisoformat(otp_expiry):
            raise VerifyOtpError("otp expired")

        if not verify_otp(stored_otp, otp):
            raise VerifyOtpError("failed to verify otp")

        res = await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_verified": True}, "$unset": {"otp": "", "otp_expiry": ""}},
        )
        if not res.acknowledged:
            raise VerifyOtpError("failed to verify user")

        token = create_access_token(str(user["_id"]))

        if not token:
            raise CreateTokenError("failed to create token")

        return VerifyUserRes(token=token)

    async def resent_otp(self, user_id: str) -> ResendOtpRes:
        log.info(f"resending otp for user {user_id}")

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise UserNotFound("User does not exist")

        if user.get("is_verified"):
            raise UserAlreadyVerified("User is already verified")

        otp = generate_otp()
        now = get_current_time()

        res = await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "otp": hash_otp(otp),
                    "otp_expiry": (
                        now + timedelta(minutes=settings.OTP_EXPIRY)
                    ).isoformat(),
                }
            },
        )

        if not res.acknowledged:
            raise ResendOtpError("failed to resend otp")

        res = await send_email(payload=EmailPayload(to=user["email"], otp=otp))

        if not res.get("id"):
            raise SendEmailError("Failed to send email")

        return ResendOtpRes(success=True, user_id=str(user["_id"]))

    async def login(self, payload: LoginReq) -> LoginRes:
        log.info(f"logging in user {payload.email}")

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await self.db.users.find_one({"email": payload.email.strip().lower()})
        if not user:
            raise UserNotFound("User not found")

        if not user.get("is_verified"):
            raise UserNotVerified("User is unverified")

        if not verify_password(payload.password, user.get("password")):
            raise InvalidCredentials("invalid credentials")

        token = create_access_token(str(user.get("_id")))

        if not token:
            raise CreateTokenError("Failed to create token")

        return LoginRes(token=token)
