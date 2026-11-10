class VariableAlreadyExists(Exception):
    pass


class VariableQuotaExceeded(Exception):
    pass


class CreateVariableError(Exception):
    pass


class VariableNotFound(Exception):
    pass


class DeleteVariableFailed(Exception):
    pass


class UpdateVariableFailed(Exception):
    pass
