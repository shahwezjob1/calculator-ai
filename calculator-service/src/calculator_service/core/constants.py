NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"

# Shared contract with the agent's evaluator and the reviewer's script-subset prompt:
# these names are built into the sandbox namespace and may never be used as custom
# constant names, calculation names, or param names. "result" is the script output slot.
UNIVERSAL_NAMES = frozenset(
    {
        "pi", "e", "result",
        "range", "int", "float", "abs", "min", "max", "len", "round",
        "sqrt", "log", "log10", "exp", "sin", "cos", "tan", "factorial",
    }
)

VALIDATION_FAILED_ERROR_CODE = "VALIDATION_FAILED"
INVALID_NAME_ERROR_CODE = "INVALID_NAME"
INVALID_VALUE_ERROR_CODE = "INVALID_VALUE"
INVALID_SCRIPT_ERROR_CODE = "INVALID_SCRIPT"
INVALID_PARAMS_ERROR_CODE = "INVALID_PARAMS"
CONSTANT_NOT_FOUND_ERROR_CODE = "CONSTANT_NOT_FOUND"
CALCULATION_NOT_FOUND_ERROR_CODE = "CALCULATION_NOT_FOUND"
CALCULATION_EXISTS_ERROR_CODE = "CALCULATION_EXISTS"
CALCULATION_DISABLED_ERROR_CODE = "CALCULATION_DISABLED"
EXECUTION_FAILED_ERROR_CODE = "EXECUTION_FAILED"
EXECUTION_TIMEOUT_ERROR_CODE = "EXECUTION_TIMEOUT"
REVIEWER_UNAVAILABLE_ERROR_CODE = "REVIEWER_UNAVAILABLE"
INTERNAL_ERROR_CODE = "INTERNAL_ERROR"

VALIDATION_FAILED_MESSAGE = "Request validation failed"
GENERIC_ERROR_MESSAGE = "An unexpected error occurred"

REVIEW_STATUS_APPROVED = "APPROVED"
REVIEW_STATUS_FLAGGED = "FLAGGED"
