class ProjectAlreadyExists(Exception):
    pass


class ProjectQuotaExceeded(Exception):
    pass


class CreateProjectError(Exception):
    pass


class ProjectNotFound(Exception):
    pass


class ReauthenticationFailed(Exception):
    pass


class MemberNotFound(Exception):
    pass


class ForbiddenAccess(Exception):
    pass


class CannotModifyOwner(Exception):
    pass
