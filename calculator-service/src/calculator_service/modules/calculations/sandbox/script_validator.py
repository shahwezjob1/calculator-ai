import ast

from calculator_service.core.constants import INVALID_SCRIPT_ERROR_CODE, UNIVERSAL_NAMES
from calculator_service.core.exceptions.bad_request_exception import BadRequestException

MAX_AST_NODES = 500
MAX_DICT_KEY_LENGTH = 64

SAFE_CALL_NAMES = UNIVERSAL_NAMES - {"pi", "e", "result"}
READABLE_BUILTIN_NAMES = UNIVERSAL_NAMES - {"result"}

ALLOWED_NODE_TYPES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign,
    ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.Pass, ast.IfExp,
    ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
    ast.Dict, ast.List, ast.Subscript,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


def _reject(detail: str) -> None:
    raise BadRequestException(INVALID_SCRIPT_ERROR_CODE, "Script violates the allowed subset", detail)


def validate_script(script: str, param_names: list[str]) -> None:
    try:
        tree = ast.parse(script, mode="exec")
    except SyntaxError as exc:
        _reject(f"syntax error: {exc.msg} (line {exc.lineno})")

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        _reject(f"script too complex: {len(nodes)} AST nodes (max {MAX_AST_NODES})")

    # String constants are permitted only as result-dict keys.
    allowed_string_nodes: set[int] = set()
    for node in nodes:
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if len(key.value) > MAX_DICT_KEY_LENGTH:
                        _reject(f"dict key too long: '{key.value[:20]}...'")
                    allowed_string_nodes.add(id(key))

    assigned_names: set[str] = set()
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.For)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)

    result_assigned = "result" in assigned_names
    readable = assigned_names | set(param_names) | READABLE_BUILTIN_NAMES

    for node in nodes:
        if not isinstance(node, ALLOWED_NODE_TYPES):
            _reject(f"construct not allowed: {type(node).__name__}")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or isinstance(node.value, (int, float)):
                continue
            if isinstance(node.value, str) and id(node) in allowed_string_nodes:
                continue
            _reject("only numbers are allowed as literals (strings only as result dict keys)")
        if isinstance(node, ast.Name):
            if "__" in node.id:
                _reject(f"name not allowed: '{node.id}'")
            if isinstance(node.ctx, ast.Load) and node.id not in readable:
                _reject(f"unknown name: '{node.id}' (not a param, local, function, or constant)")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_CALL_NAMES:
                _reject("only calls to the whitelisted functions are allowed")
            if node.keywords:
                _reject("keyword arguments are not allowed in calls")
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                _reject("assignments must target a single plain variable")
        if isinstance(node, ast.AugAssign) and not isinstance(node.target, ast.Name):
            _reject("augmented assignments must target a plain variable")
        if isinstance(node, ast.For):
            if not isinstance(node.target, ast.Name):
                _reject("for-loop target must be a plain variable")
            if not (isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name)
                    and node.iter.func.id == "range"):
                _reject("for-loops may only iterate over range(...)")
        if isinstance(node, ast.Subscript) and not isinstance(node.value, ast.Name):
            _reject("subscripts are only allowed on plain variables")

    if not result_assigned:
        _reject("script must assign a variable named 'result'")
