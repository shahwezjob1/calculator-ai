"""Child-process entrypoint for sandboxed script execution.

Reads {script, params, limits} as JSON on stdin, self-applies resource limits,
executes the (already statically validated) script in a restricted namespace,
and writes {ok, result | error} as JSON on stdout. Run with `python -I`.
"""

import json
import math
import sys


def _safe_namespace() -> dict:
    return {
        "range": range, "int": int, "float": float, "abs": abs, "min": min,
        "max": max, "len": len, "round": round,
        "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "exp": math.exp,
        "sin": math.sin, "cos": math.cos, "tan": math.tan, "factorial": math.factorial,
        "pi": math.pi, "e": math.e,
    }


def _apply_limits(limits: dict) -> None:
    try:
        import resource

        cpu_seconds = int(limits.get("cpu_seconds", 2)) + 1
        memory_bytes = int(limits.get("memory_mb", 128)) * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ValueError, OSError):
            pass  # RLIMIT_AS is unreliable on macOS; the parent's wall-clock kill still applies
    except ImportError:
        pass


def _normalize_result(value) -> dict:
    if isinstance(value, bool):
        raise ValueError("result must be a number or a dict of numbers")
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("result is not a finite number")
        return {"result": float(value)}
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if not isinstance(key, str) or isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError("result dict must map names to numbers")
            if not math.isfinite(item):
                raise ValueError(f"result '{key}' is not a finite number")
            normalized[key] = float(item)
        if not normalized:
            raise ValueError("result dict is empty")
        return normalized
    raise ValueError("result must be a number or a dict of numbers")


def main() -> None:
    payload = json.load(sys.stdin)
    _apply_limits(payload.get("limits", {}))
    namespace = {"__builtins__": {}}
    namespace.update(_safe_namespace())
    namespace.update({name: float(value) for name, value in payload["params"].items()})
    try:
        exec(compile(payload["script"], "<calculation>", "exec"), namespace)
        result = _normalize_result(namespace.get("result"))
    except Exception as exc:  # reported back as a structured execution error
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return
    print(json.dumps({"ok": True, "result": result}))


if __name__ == "__main__":
    main()
