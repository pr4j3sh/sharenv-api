from datetime import datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.api.v1.auth.exceptions import (
    CreateTokenError,
    EmailNotConfigured,
    InvalidCredentials,
    InvalidRefreshToken,
    LogoutError,
    RegisterError,
    ResendOtpError,
    SendEmailError,
    TooManyAttempts,
    UserAlreadyExists,
    UserNotVerified,
    VerifyOtpError,
)
from app.api.v1.auth.models import UserModel
from app.api.v1.auth.schemas import (
    EmailPayload,
    LoginReq,
    LoginRes,
    LogoutRes,
    RefreshRes,
    RegisterReq,
    RegisterRes,
    ResendOtpRes,
    VerifyUserRes,
)
from app.core.config import settings
from app.core.crypto import (
    generate_otp,
    hash_otp,
    hash_secret,
    verify_otp,
)
from app.core.email import send_email
from app.core.logger import get_logger, redact_secrets
from app.core.rate_limit import login_failures, otp_attempts, otp_resends
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.core.utils import get_current_time
from app.db.mongodb import mongo

log = get_logger(__name__)


class Auth:
    def __init__(self) -> None:
        self.db = mongo

    async def _rollback_registration(self, user_id: ObjectId) -> None:
        try:
            if self.db.users is None:
                raise RuntimeError("mongodb is not connected")

            await self.db.users.delete_one({"_id": user_id})
        except Exception:
            log.exception("failed to roll back registration for %s", user_id)

    async def register(self, payload: RegisterReq) -> RegisterRes:
        log.info("registering user %s", hash_secret(payload.email.strip().lower())[:12])
        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        email = payload.email.strip().lower()

        user_exists = await self.db.users.find_one({"email": email})
        if user_exists:
            raise UserAlreadyExists("User already exists")

        now = get_current_time()
        email_enabled = settings.email_enabled
        otp = generate_otp() if email_enabled else None
        user_payload = UserModel(
            email=email,
            password=hash_password(payload.password),
            otp=hash_otp(otp) if otp else None,
            otp_expiry=(now + timedelta(minutes=settings.OTP_EXPIRY) if otp else None),
        )

        try:
            user = await self.db.users.insert_one(
                user_payload.model_dump(
                    by_alias=True,
                    exclude_none=True,
                )
            )
        except DuplicateKeyError as e:
            raise UserAlreadyExists("User already exists") from e

        if not user or not user.inserted_id:
            raise RegisterError("Failed to register user")

        if email_enabled:
            try:
                res = await send_email(payload=EmailPayload(to=email, otp=otp))
            except Exception as e:
                log.error(
                    "Failed to send OTP email (%s): %s",
                    type(e).__name__,
                    redact_secrets(str(e), otp, email),
                )
                await self._rollback_registration(user.inserted_id)
                raise SendEmailError("Failed to send email") from e

            if not res.get("id"):
                await self._rollback_registration(user.inserted_id)
                raise SendEmailError("Failed to send email")

        return RegisterRes(
            success=True,
            verification_required=email_enabled,
        )

    async def verify_user(self, email: str, otp: str) -> VerifyUserRes:
        log.info("verifying user %s", hash_secret(email.strip().lower())[:12])

        if not settings.email_enabled:
            raise EmailNotConfigured("email provider is not configured")

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        email = email.strip().lower()

        retry_after = await otp_attempts.locked(
            f"otp:{email}",
            settings.OTP_VERIFY_ATTEMPTS,
            settings.OTP_EXPIRY * 60,
        )
        if retry_after:
            raise TooManyAttempts(retry_after)

        user = await self.db.users.find_one({"email": email})

        if not user or user.get("is_verified"):
            verify_otp(settings.dummy_otp_hash(), otp)
            await otp_attempts.record(f"otp:{email}", settings.OTP_EXPIRY * 60)
            raise VerifyOtpError("failed to verify otp")

        stored_otp = user.get("otp")
        otp_expiry = user.get("otp_expiry")

        if not stored_otp or not otp_expiry:
            raise VerifyOtpError("no active otp")

        now = get_current_time()

        if now >= datetime.fromisoformat(otp_expiry):
            raise VerifyOtpError("otp expired")

        if not verify_otp(stored_otp, otp):
            await otp_attempts.record(f"otp:{email}", settings.OTP_EXPIRY * 60)
            raise VerifyOtpError("failed to verify otp")

        token_version = user.get("token_version", 0)
        token = create_access_token(str(user["_id"]), token_version)
        refresh_token, refresh_jti = create_refresh_token(
            str(user["_id"]), token_version
        )

        res = await self.db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"is_verified": True, "refresh_jti": refresh_jti},
                "$unset": {"otp": "", "otp_expiry": ""},
            },
        )
        if not res.acknowledged:
            raise VerifyOtpError("failed to verify user")

        await otp_attempts.clear(f"otp:{email}")

        return VerifyUserRes(token=token, refresh_token=refresh_token)

    async def resend_otp(self, email: str) -> ResendOtpRes:
        log.info("resending otp for user %s", hash_secret(email.strip().lower())[:12])

        if not settings.email_enabled:
            raise EmailNotConfigured("email provider is not configured")

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        email = email.strip().lower()

        retry_after = await otp_resends.allow(
            f"resend:{email}",
            settings.OTP_RESEND_LIMIT,
            settings.OTP_EXPIRY * 60,
        )
        if retry_after:
            raise TooManyAttempts(retry_after)

        user = await self.db.users.find_one({"email": email})

        if not user or user.get("is_verified"):
            return ResendOtpRes(success=True)

        otp = generate_otp()
        now = get_current_time()

        res = await self.db.users.update_one(
            {"_id": user["_id"]},
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

        email_result = await send_email(payload=EmailPayload(to=user["email"], otp=otp))

        if not email_result.get("id"):
            raise SendEmailError("Failed to send email")

        return ResendOtpRes(success=True)

    async def login(self, payload: LoginReq) -> LoginRes:
        log.info("logging in user %s", hash_secret(payload.email.strip().lower())[:12])

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        email = payload.email.strip().lower()

        retry_after = await login_failures.locked(
            f"fail:{email}",
            settings.LOGIN_FAILURE_LIMIT,
            settings.LOGIN_LOCKOUT_MINUTES * 60,
        )
        if retry_after:
            raise TooManyAttempts(retry_after)

        user = await self.db.users.find_one({"email": email})

        if not user:
            verify_password(payload.password, DUMMY_HASH)
            await login_failures.record(
                f"fail:{email}", settings.LOGIN_LOCKOUT_MINUTES * 60
            )
            raise InvalidCredentials("invalid credentials")

        if not verify_password(payload.password, user.get("password")):
            await login_failures.record(
                f"fail:{email}", settings.LOGIN_LOCKOUT_MINUTES * 60
            )
            raise InvalidCredentials("invalid credentials")

        if not user.get("is_verified") and settings.email_enabled:
            raise UserNotVerified("User is unverified")

        token_version = user.get("token_version", 0)
        token = create_access_token(str(user["_id"]), token_version)
        refresh_token, refresh_jti = create_refresh_token(
            str(user["_id"]), token_version
        )

        res = await self.db.users.update_one(
            {"_id": user["_id"]}, {"$set": {"refresh_jti": refresh_jti}}
        )
        if not res.acknowledged:
            raise CreateTokenError("Failed to create token")

        await login_failures.clear(f"fail:{email}")

        return LoginRes(
            token=token,
            refresh_token=refresh_token,
            email_verified=bool(user.get("is_verified")),
        )

    async def refresh(self, refresh_token: str) -> RefreshRes:
        log.info("refreshing token")

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        try:
            payload = decode_refresh_token(refresh_token)
        except Exception as e:
            raise InvalidRefreshToken("invalid refresh token") from e

        user_id = payload.get("sub")
        token_version = payload.get("ver")
        jti = payload.get("jti")

        try:
            user_oid = ObjectId(user_id)
        except (InvalidId, TypeError) as e:
            raise InvalidRefreshToken("invalid refresh token") from e

        user = await self.db.users.find_one({"_id": user_oid})
        if not user or user.get("token_version", 0) != token_version:
            raise InvalidRefreshToken("invalid refresh token")

        if token_version is None:
            raise InvalidRefreshToken("invalid refresh token")

        new_token = create_access_token(str(user_oid), token_version)
        new_refresh_token, new_jti = create_refresh_token(str(user_oid), token_version)

        res = await self.db.users.find_one_and_update(
            {"_id": user_oid, "token_version": token_version, "refresh_jti": jti},
            {"$set": {"refresh_jti": new_jti}},
        )
        if not res:
            current = await self.db.users.find_one({"_id": user_oid})
            if current and current.get("token_version", 0) == token_version:
                await self.db.users.update_one(
                    {"_id": user_oid},
                    {
                        "$inc": {"token_version": 1},
                        "$unset": {"refresh_jti": ""},
                    },
                )
            raise InvalidRefreshToken("invalid refresh token")

        return RefreshRes(
            token=new_token,
            refresh_token=new_refresh_token,
            email_verified=bool(user.get("is_verified")),
        )

    async def logout(self, user_id: str) -> LogoutRes:
        log.info("logging out user %s", user_id)

        if self.db.users is None:
            raise RuntimeError("mongodb is not connected")

        res = await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$inc": {"token_version": 1},
                "$unset": {"refresh_jti": ""},
            },
        )

        if not res.acknowledged:
            raise LogoutError("Failed to log out")

        return LogoutRes(success=True)
