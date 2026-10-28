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
