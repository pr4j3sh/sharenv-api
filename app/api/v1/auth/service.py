from app.api.v1.auth.schemas import LoginReq, LoginRes, RegisterReq, RegisterRes


class Auth:
    def __init__(self) -> None:
        pass

    async def register(self, payload: RegisterReq) -> RegisterRes:
        print(payload)
        return RegisterRes(token="1")

    async def login(self, payload: LoginReq) -> LoginRes:
        print(payload)
        return LoginRes(token="1")
