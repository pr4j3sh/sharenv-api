from app.api.v1.auth.exceptions import (
    CreateTokenError,
    InvalidCredentials,
    RegisterError,
    UserAlreadyExists,
    UserNotFound,
)
from app.api.v1.auth.schemas import LoginReq, LoginRes, RegisterReq, RegisterRes
from app.core.logger import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongodb import mongo

log = get_logger(__name__)


class Auth:
    def __init__(self) -> None:
        pass

    async def register(self, payload: RegisterReq) -> RegisterRes:
        log.info(f"registering user {payload.email}")
        if mongo.users is None:
            raise RuntimeError("mongodb is not connected")

        user_exists = await mongo.users.find_one(
            {"email": payload.email.strip().lower()}
        )
        if user_exists:
            raise UserAlreadyExists(f"User already exists with email {payload.email}")

        user_payload = {
            "email": payload.email.strip().lower(),
            "password": hash_password(payload.password),
        }
        res = await mongo.users.insert_one(user_payload)

        if not res or not res.inserted_id:
            raise RegisterError("Failed to register user")

        token = create_access_token(str(res.inserted_id))

        if not token:
            raise CreateTokenError("User created but failed to create token")

        return RegisterRes(token=token)

    async def login(self, payload: LoginReq) -> LoginRes:
        log.info(f"logging in user {payload.email}")

        if mongo.users is None:
            raise RuntimeError("mongodb is not connected")

        user = await mongo.users.find_one({"email": payload.email.strip().lower()})
        if not user:
            raise UserNotFound("User not found")

        if not verify_password(payload.password, user.get("password")):
            raise InvalidCredentials("invalid credentials")

        token = create_access_token(str(user.get("_id")))

        if not token:
            raise CreateTokenError("Failed to create token")

        return LoginRes(token=token)
