"""Bot 1 — Trace Generation Bot (architecture.md 6.8).

Deterministic, pure-Python trace generation: request dict in, response
dict out. Responsibilities and limits:

- Implements the four patterns (sequential, repeated, conflict, manual)
  with strict, explicit parameters — nothing is defaulted or repaired.
- Never derives cache geometry itself: every request consults the engine's
  `geometry` mode through the injected `geometry_provider` (decision D-6).
- Never decides hits/misses and contains no randomness (rules.md 2).
- Identical requests always produce identical responses (AC-P6.2), so
  trace names are derived from the parameters, never from a clock.
"""

from bots.engine_client import EngineError

_MAX_TRACE_ADDRESSES = 100000  # architecture.md 12
_MAX_COLLECTED_MANUAL_ISSUES = 10  # mirrors the engine's trace-issue cap
_KNOWN_PATTERNS = ("sequential", "repeated", "conflict", "manual")

# Per-pattern parameter keys (architecture.md 6.8). All are required;
# unknown keys are rejected as typos.
_PATTERN_PARAMS = {
    "sequential": ("start_address", "count", "stride_bytes"),
    "repeated": ("address", "count"),
    "conflict": ("distinct_blocks", "passes", "target_set", "start_block"),
    "manual": ("text",),
}


class TraceBotError(Exception):
    """Bot-level failure carrying an E_* code from the engine vocabulary."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details if details is not None else []

    def as_error_dict(self):
        return {"code": self.code, "message": self.message,
                "details": self.details}


def _issue(field, problem, received):
    return {"field": field, "problem": problem, "received": received}


def _int_param(params, key, minimum, hint=None):
    """Reads a required integer parameter (bools are not integers here)."""
    if key not in params:
        raise TraceBotError(
            "E_JOB_INVALID", f"params.{key} is required",
            [_issue(f"params.{key}", "is required", None)])
    value = params[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceBotError(
            "E_JOB_INVALID",
            f"params.{key} must be an integer >= {minimum}",
            [_issue(f"params.{key}", f"must be an integer >= {minimum}",
                    value)])
    if value < minimum:
        problem = f"must be an integer >= {minimum}"
        if hint:
            problem = f"{problem} ({hint})"
        raise TraceBotError(
            "E_JOB_INVALID", f"params.{key} {problem}",
            [_issue(f"params.{key}", problem, value)])
    return value


def _check_unknown_params(pattern, params):
    known = _PATTERN_PARAMS[pattern]
    for key in params:
        if key not in known:
            raise TraceBotError(
                "E_JOB_INVALID",
                f"params.{key} is unknown for the {pattern} pattern "
                f"(expected: {', '.join(known)})",
                [_issue(f"params.{key}", "unknown parameter (typo or "
                        "unsupported)", params[key])])


def _sequential(params, geometry):
    _check_unknown_params("sequential", params)
    start = _int_param(params, "start_address", 0)
    count = _int_param(params, "count", 0)
    stride = _int_param(
        params, "stride_bytes", 1,
        hint="use the repeated pattern for a constant address")
    max_address = geometry["max_address"]
    if count > _MAX_TRACE_ADDRESSES:
        raise TraceBotError(
            "E_LIMIT",
            f"count {count} exceeds the {_MAX_TRACE_ADDRESSES}-address limit",
            [_issue("params.count",
                    f"must be <= {_MAX_TRACE_ADDRESSES}", count)])
    last = start + (count - 1) * stride if count > 0 else start
    if last > max_address:
        raise TraceBotError(
            "E_TRACE_INVALID",
            f"generated address {last} exceeds the maximum valid address "
            f"{max_address}",
            [_issue("params",
                    f"start_address {start} + ({count} - 1) x stride "
                    f"{stride} reaches {last}; maximum is {max_address}",
                    {"start_address": start, "count": count,
                     "stride_bytes": stride})])
    addresses = [start + k * stride for k in range(count)]
    name = f"sequential-{start}-{count}-{stride}"
    return name, addresses, []


def _repeated(params, geometry):
    _check_unknown_params("repeated", params)
    address = _int_param(params, "address", 0)
    count = _int_param(params, "count", 0)
    max_address = geometry["max_address"]
    if count > _MAX_TRACE_ADDRESSES:
        raise TraceBotError(
            "E_LIMIT",
            f"count {count} exceeds the {_MAX_TRACE_ADDRESSES}-address limit",
            [_issue("params.count",
                    f"must be <= {_MAX_TRACE_ADDRESSES}", count)])
    if address > max_address:
        raise TraceBotError(
            "E_TRACE_INVALID",
            f"address {address} exceeds the maximum valid address "
            f"{max_address}",
            [_issue("params.address",
                    f"must be between 0 and {max_address}", address)])
    name = f"repeated-{address}-{count}"
    return name, [address] * count, []


def _conflict(params, geometry):
    _check_unknown_params("conflict", params)
    distinct_blocks = _int_param(params, "distinct_blocks", 1)
    passes = _int_param(params, "passes", 1)
    target_set = _int_param(params, "target_set", 0)
    start_block = _int_param(params, "start_block", 0)
    sets = geometry["sets"]
    block_size = geometry["block_size_bytes"]
    max_address = geometry["max_address"]

    warnings = []
    if sets == 1:
        # fully_associative: every block maps to the single set (§6.8).
        if target_set != 0:
            warnings.append(
                f"fully_associative: all blocks map to the single set "
                f"(set 0); target_set {target_set} ignored")
            target_set = 0
    elif target_set >= sets:
        raise TraceBotError(
            "E_JOB_INVALID",
            f"target_set must be in [0, {sets}) for this configuration "
            f"(got {target_set})",
            [_issue("params.target_set",
                    f"must be in [0, {sets})", target_set)])

    if distinct_blocks * passes > _MAX_TRACE_ADDRESSES:
        raise TraceBotError(
            "E_LIMIT",
            f"distinct_blocks x passes = {distinct_blocks * passes} "
            f"exceeds the {_MAX_TRACE_ADDRESSES}-address limit",
            [_issue("params",
                    f"must be <= {_MAX_TRACE_ADDRESSES}",
                    {"distinct_blocks": distinct_blocks, "passes": passes})])

    # Base block: the smallest block >= start_block congruent to
    # target_set (mod sets) — Python's % is non-negative (§6.8).
    base = start_block + ((target_set - start_block) % sets)
    addresses = []
    for k in range(distinct_blocks):
        block = base + k * sets
        address = block * block_size
        if address > max_address:
            raise TraceBotError(
                "E_TRACE_INVALID",
                f"generated address {address} (block {block}) exceeds the "
                f"maximum valid address {max_address}",
                [_issue("params",
                        f"block {block} maps to address {address}; maximum "
                        f"is {max_address}",
                        {"start_block": start_block, "target_set": target_set,
                         "distinct_blocks": distinct_blocks})])
        addresses.append(address)
    addresses = addresses * passes
    name = f"conflict-{distinct_blocks}b-set{target_set}-p{passes}"
    return name, addresses, warnings


def _manual(params, geometry):
    _check_unknown_params("manual", params)
    if "text" not in params or not isinstance(params["text"], str):
        raise TraceBotError(
            "E_JOB_INVALID", "params.text is required and must be a string",
            [_issue("params.text", "must be a string",
                    params.get("text"))])
    max_address = geometry["max_address"]
    issues = []
    addresses = []
    bad_total = 0
    for line_no, raw in enumerate(params["text"].splitlines(), start=1):
        content = raw.split("#", 1)[0].strip()
        if not content:
            continue  # blank lines and comments are ignored (§6.4)
        try:
            if content[:2].lower() == "0x":
                value = int(content[2:], 16)
            else:
                value = int(content, 10)
        except ValueError:
            problem = "not a valid address (decimal or 0x hex)"
        else:
            if 0 <= value <= max_address:
                addresses.append(value)
                continue
            problem = f"must be between 0 and {max_address}"
        bad_total += 1
        if len(issues) < _MAX_COLLECTED_MANUAL_ISSUES:
            issues.append(_issue(f"line {line_no}", problem, content))
    if bad_total > len(issues):
        issues.append(_issue("params.text",
                             f"further problem lines truncated "
                             f"({bad_total - len(issues)} more)", bad_total))
    if issues:
        raise TraceBotError(
            "E_TRACE_INVALID",
            f"manual trace text has {bad_total} problem line(s)", issues)
    if len(addresses) > _MAX_TRACE_ADDRESSES:
        raise TraceBotError(
            "E_LIMIT",
            f"manual trace has {len(addresses)} addresses, exceeding the "
            f"{_MAX_TRACE_ADDRESSES}-address limit",
            [_issue("params.text",
                    f"must contain <= {_MAX_TRACE_ADDRESSES} addresses",
                    len(addresses))])
    return "manual-import", addresses, []


_GENERATORS = {
    "sequential": _sequential,
    "repeated": _repeated,
    "conflict": _conflict,
    "manual": _manual,
}


def generate(request, geometry_provider):
    """Generates a trace for `request` (architecture.md 6.8).

    `geometry_provider(config)` must return the engine's geometry dict for
    the configuration (use bots.engine_client.fetch_geometry in production;
    tests inject a stub). Returns the contract response dict:
    {"ok": True, "trace": {...}, "geometry_used": {...}, "warnings": []}
    on success, or {"ok": False, "error": {"code", "message", "details"}}
    on failure with codes from the engine's closed E_* vocabulary.
    """
    try:
        return _generate(request, geometry_provider)
    except TraceBotError as err:
        return {"ok": False, "error": err.as_error_dict()}
    except EngineError as err:
        return {"ok": False, "error": err.as_error_dict()}


def _generate(request, geometry_provider):
    if not isinstance(request, dict):
        raise TraceBotError("E_JOB_INVALID", "request must be a JSON object",
                            [_issue("(root)", "must be a JSON object",
                                    request)])
    issues = []
    for key in request:
        if key not in ("pattern", "config", "params"):
            issues.append(_issue(key, "unknown field (typo or unsupported)",
                                 request[key]))
    for key in ("pattern", "config", "params"):
        if key not in request:
            issues.append(_issue(key, "is required", None))
    if issues:
        raise TraceBotError("E_JOB_INVALID",
                            f"request validation failed with {len(issues)} "
                            f"problem(s)", issues)
    pattern = request["pattern"]
    if pattern not in _KNOWN_PATTERNS:
        raise TraceBotError(
            "E_JOB_INVALID",
            f"pattern must be one of: {', '.join(_KNOWN_PATTERNS)}",
            [_issue("pattern",
                    f"must be one of: {', '.join(_KNOWN_PATTERNS)}",
                    pattern)])
    params = request["params"]
    config = request["config"]
    if not isinstance(params, dict):
        raise TraceBotError("E_JOB_INVALID", "params must be a JSON object",
                            [_issue("params", "must be a JSON object",
                                    params)])
    if not isinstance(config, dict):
        raise TraceBotError("E_JOB_INVALID", "config must be a JSON object",
                            [_issue("config", "must be a JSON object",
                                    config)])

    # D-6: geometry (sets, max_address, block size) always comes from the
    # engine — the engine also authoritatively validates the config here.
    geometry = geometry_provider(config)
    name, addresses, warnings = _GENERATORS[pattern](params, geometry)
    return {
        "ok": True,
        "trace": {
            "name": name,
            "pattern": pattern,
            "params": params,
            "addresses": addresses,
        },
        "geometry_used": geometry,
        "warnings": warnings,
    }
