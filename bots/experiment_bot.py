"""Bot 2 — Experiment Runner and Performance Analysis (architecture.md 6.9).

Error taxonomy and request/trace validation for cache experiments.
"""

from bots.engine_client import EngineError

_MAX_TRACE_ADDRESSES = 100000  # architecture.md 12
_MAX_COLLECTED_TRACE_ISSUES = 10
_POLICIES = ("LRU", "FIFO", "RANDOM")
_ORG_CAVEAT = ("Caveat: direct-mapped has no selectable replacement "
               "policy; the set-associative and fully-associative runs "
               "use LRU.")
_REQUEST_KEYS = ("mode", "trace", "config", "random_seed")


class ExperimentBotError(Exception):
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


def _validate_shape(request):
    if not isinstance(request, dict):
        raise ExperimentBotError("E_JOB_INVALID",
                                 "request must be a JSON object",
                                 [_issue("(root)", "must be a JSON object",
                                         request)])
    issues = []
    for key in request:
        if key not in _REQUEST_KEYS:
            issues.append(_issue(key, "unknown field (typo or unsupported)",
                                 request[key]))
    for key in ("mode", "trace", "config"):
        if key not in request:
            issues.append(_issue(key, "is required", None))
    if issues:
        raise ExperimentBotError(
            "E_JOB_INVALID",
            f"request validation failed with {len(issues)} problem(s)",
            issues)
    if request["mode"] not in ("policy_comparison", "organization_comparison"):
        raise ExperimentBotError(
            "E_JOB_INVALID",
            "mode must be one of: policy_comparison, organization_comparison",
            [_issue("mode", "must be one of: policy_comparison, "
                    "organization_comparison", request["mode"])])


def _validate_config_shape(config):
    if not isinstance(config, dict):
        raise ExperimentBotError("E_JOB_INVALID",
                                 "config must be a JSON object",
                                 [_issue("config", "must be a JSON object",
                                         config)])
    issues = []
    for key in ("capacity_bytes", "block_size_bytes", "address_width_bits"):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            issues.append(_issue(f"config.{key}",
                                 "must be an integer", value))
    organization = config.get("organization")
    if not isinstance(organization, str):
        issues.append(_issue("config.organization", "must be a string",
                             organization))
    if organization == "set_associative":
        associativity = config.get("associativity")
        if isinstance(associativity, bool) or \
                not isinstance(associativity, int):
            issues.append(_issue(
                "config.associativity",
                "must be an integer for set_associative", associativity))
    if issues:
        raise ExperimentBotError(
            "E_JOB_INVALID",
            f"config shape validation failed with {len(issues)} problem(s)",
            issues)


def _validated_random_seed(request):
    if "random_seed" not in request:
        raise ExperimentBotError(
            "E_JOB_INVALID",
            "random_seed is required for policy_comparison (the RANDOM "
            "run's seed)",
            [_issue("random_seed", "is required for policy_comparison",
                    None)])
    value = request["random_seed"]
    if isinstance(value, bool) or not isinstance(value, int) or \
            value < 0 or value > 4294967295:
        raise ExperimentBotError(
            "E_JOB_INVALID",
            "random_seed must be an integer between 0 and 4294967295",
            [_issue("random_seed",
                    "must be an integer between 0 and 4294967295", value)])
    return value


def _validated_trace(trace, config):
    if not isinstance(trace, dict):
        raise ExperimentBotError("E_TRACE_INVALID", "trace must be a JSON object",
                                 [_issue("trace", "must be a JSON object",
                                         trace)])
    name = trace.get("name")
    if not isinstance(name, str) or not name:
        raise ExperimentBotError("E_TRACE_INVALID",
                                 "trace.name must be a non-empty string",
                                 [_issue("trace.name",
                                         "must be a non-empty string", name)])
    addresses = trace.get("addresses")
    if not isinstance(addresses, list):
        raise ExperimentBotError("E_TRACE_INVALID",
                                 "trace.addresses must be an array",
                                 [_issue("trace.addresses",
                                         "must be an array", addresses)])
    if len(addresses) == 0:
        # An empty-trace comparison is meaningless and would make the
        # summary-text rates null (decision D-22).
        raise ExperimentBotError(
            "E_TRACE_INVALID",
            "experiment traces must contain at least one address",
            [_issue("trace.addresses", "must not be empty", addresses)])
    if len(addresses) > _MAX_TRACE_ADDRESSES:
        raise ExperimentBotError(
            "E_LIMIT",
            f"trace length {len(addresses)} exceeds the "
            f"{_MAX_TRACE_ADDRESSES}-address limit",
            [_issue("trace.addresses",
                    f"must be <= {_MAX_TRACE_ADDRESSES}", len(addresses))])
    width = config.get("address_width_bits")
    max_address = None
    if isinstance(width, int) and not isinstance(width, bool) and \
            4 <= width <= 64:
        max_address = (1 << width) - 1
    issues = []
    bad_total = 0
    for index, value in enumerate(addresses):
        if isinstance(value, bool) or not isinstance(value, int) or \
                value < 0:
            problem = "must be a non-negative integer"
        elif max_address is not None and value > max_address:
            problem = (f"must be between 0 and the maximum valid address "
                       f"{max_address}")
        else:
            continue
        bad_total += 1
        if bad_total <= _MAX_COLLECTED_TRACE_ISSUES:
            issues.append(_issue(f"trace.addresses[{index}]", problem, value))
    if bad_total > _MAX_COLLECTED_TRACE_ISSUES:
        issues.append(_issue("trace.addresses",
                             "further address problems truncated", bad_total))
    if issues:
        raise ExperimentBotError(
            "E_TRACE_INVALID",
            f"trace validation failed with {len(issues)} problem(s)", issues)
    return {"name": name, "addresses": addresses}
