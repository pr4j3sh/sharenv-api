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


class OtpExpired(Exception):
    pass


class UserAlreadyVerified(Exception):
    pass


class ResendOtpError(Exception):
    pass
