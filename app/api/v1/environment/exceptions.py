class EnvironmentAlreadyExists(Exception):
    pass


class EnvironmentQuotaExceeded(Exception):
    pass


class CreateEnvironmentError(Exception):
    pass


class EnvironmentNotFound(Exception):
    pass


class DeleteEnvironmentFailed(Exception):
    pass
