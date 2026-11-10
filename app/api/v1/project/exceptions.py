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
    """Authenticated but not permitted for this action/role."""


class CannotModifyOwner(Exception):
    pass

