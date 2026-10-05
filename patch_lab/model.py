"""Private-copy execution with whole-patch discard; no external resource changes."""
import json
import re
from .contract import LIMITS, SCHEMA, LabError, Unsupported, _walk, validate


class Rejected(ValueError):
    """An admitted operation failed with a fixed trusted reason."""


def _clone(value):
    # Admission guarantees exact builtins; logical aliases become separate copies.
    if type(value) is dict:
        return {key: _clone(child) for key, child in value.items()}
    if type(value) is list:
        return [_clone(child) for child in value]
    return value


def _equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_equal(value, right[key]) for key, value in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _index(token, length, inserting=False):
    # B105 false positive: JSON Pointer array-end marker, not a credential.
    if inserting and token == "-":  # nosec B105
        return length
    if re.fullmatch(r"0|[1-9][0-9]*", token, flags=re.ASCII) is None:
        raise Rejected("invalid-array-index")
    maximum = str(length if inserting else length - 1)
    if (not inserting and not length) or len(token) > len(maximum) or (len(token) == len(maximum) and token > maximum):
        raise Rejected("array-index-out-of-range")
    return int(token)


def _lookup(value, path):
    current = value
    for token in path:
        if type(current) is dict:
            if token not in current:
                raise Rejected("missing-member")
            current = current[token]
        elif type(current) is list:
            current = current[_index(token, len(current))]
        else:
            raise Rejected("cannot-traverse-scalar")
    return current


def _parent(value, path):
    return _lookup(value, path[:-1]), path[-1]


def _add(value, path, added):
    if not path:
        return added
    parent, name = _parent(value, path)
    if type(parent) is dict:
        parent[name] = added
    elif type(parent) is list:
        parent.insert(_index(name, len(parent), inserting=True), added)
    else:
        raise Rejected("cannot-traverse-scalar")
    return value


def _remove(value, path):
    parent, name = _parent(value, path)
    if type(parent) is dict:
        if name not in parent:
            raise Rejected("missing-member")
        del parent[name]
    elif type(parent) is list:
        del parent[_index(name, len(parent))]
    else:
        raise Rejected("cannot-traverse-scalar")
    return value


def _replace(value, path, added):
    _lookup(value, path)
    if not path:
        return added
    parent, name = _parent(value, path)
    if type(parent) is list:
        parent[_index(name, len(parent))] = added
    else:
        parent[name] = added
    return value


def _copy_value(value):
    # Snapshot before insertion, especially when the source is the entire root.
    return _clone(value)


def _move(value, source, path):
    selected = _lookup(value, source)
    if len(source) < len(path) and path[:len(source)] == source:
        raise Rejected("descendant-move")
    if source == path:
        return value
    moved = _clone(selected)
    value = _remove(value, source)
    return _add(value, path, moved)


def _apply(value, operation, parsed):
    name, path, source = parsed
    if name == "add":
        return _add(value, path, _clone(operation["value"]))
    if name == "remove":
        return _remove(value, path)
    if name == "replace":
        return _replace(value, path, _clone(operation["value"]))
    if name == "test":
        if not _equal(_lookup(value, path), operation["value"]):
            raise Rejected("test-failed")
        return value
    if name == "copy":
        return _add(value, path, _copy_value(_lookup(value, source)))
    return _move(value, source, path)


def analyze(envelope):
    """Return (detached report, exit code); input/support failures raise LabError.

    Successful steps are local attempts only. Any rejection publishes an original
    snapshot, while discarded candidates never mutate or become caller inputs.
    """
    parsed = validate(envelope)
    if envelope["schema"] != SCHEMA:
        raise Unsupported("unsupported schema")
    working = _clone(envelope["target"])
    trace, failure = [], None
    for index, (operation, spec) in enumerate(zip(envelope["operations"], parsed)):
        row = {"index": index, "op": spec[0], "status": "not-run", "reason": None}
        if failure is None:
            candidate = _clone(working)
            try:
                candidate = _apply(candidate, operation, spec)
                try:
                    _walk(candidate, "result")
                except LabError as error:
                    # Only trusted admitted builtins reach here; limits can grow.
                    raise Rejected("resource-limit") from error
            except Rejected as error:
                failure = index
                row.update(status="failed", reason=str(error))
            else:
                working = candidate
                row["status"] = "completed"
        trace.append(row)
    result = _clone(envelope["target"]) if failure is not None else _clone(working)
    changed = not _equal(envelope["target"], result)
    kinds = {dict:"object", list:"array", str:"string", int:"integer", bool:"boolean", type(None):"null"}
    report = {"profile": SCHEMA, "representation": "ordered-patch-value",
              "assumption": "synthetic supplied values; no resource modification or authorization verdict",
              "policy": "discard-private-working-copy-on-failure", "limits": dict(LIMITS),
              "target": _clone(envelope["target"]), "operations": _clone(envelope["operations"]),
              "result": result, "result_type": kinds[type(result)],
              "outcome": "rejected" if failure is not None else "applied", "changed": changed,
              "completed_operations": len(parsed) if failure is None else failure,
              "failure_index": failure, "trace": trace}
    return report, 4 if failure is not None else 1 if changed else 0


def render(report):
    """Cap this model's admitted report (or fixed diagnostic) before delivery.

    This helper is not an admission API for arbitrary user-supplied reports.
    """
    content = json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n"
    if len(content.encode("ascii")) > LIMITS["output_bytes"]:
        raise LabError("resource limit")
    return content
