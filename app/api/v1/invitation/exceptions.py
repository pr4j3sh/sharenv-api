class InvitationNotFound(Exception):
    pass


class InvitationAlreadyExists(Exception):
    pass


class InvitationExpired(Exception):
    pass


class InvitationAlreadyAccepted(Exception):
    pass


class InvitationEmailMismatch(Exception):
    pass


class InvalidInvitationEnvironments(Exception):
    pass
