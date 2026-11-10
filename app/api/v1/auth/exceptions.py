class UserAlreadyExists(Exception):
    pass


class UserNotFound(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class RegisterError(Exception):
    pass


class CreateTokenError(Exception):
    pass


class UnauthorizedAccess(Exception):
    pass


class SendEmailError(Exception):
    pass


class VerifyOtpError(Exception):
    pass


class UserAlreadyVerified(Exception):
    pass


class UserNotVerified(Exception):
    pass


class ResendOtpError(Exception):
    pass


class TooManyAttempts(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("too many attempts")


class InvalidRefreshToken(Exception):
    pass


class LogoutError(Exception):
    pass
