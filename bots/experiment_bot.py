"""Bot 2 — Experiment Runner and Performance Analysis (architecture.md 6.9).

Builds and executes controlled cache experiments and assembles the
reproducible experiment record. Responsibilities and limits:

- Two modes, one variable changed at a time: `policy_comparison` (LRU /
  FIFO / RANDOM with a recorded seed, everything else fixed) and
  `organization_comparison` (direct / set-associative / fully-associative,
  LRU wherever a policy exists, capacity/block/width fixed).
- Never decides hits/misses: every run goes through the injected
  `simulate_fn` (production: bots.engine_client.run_simulate; tests: a
  stub) and the engine stays the single source of truth.
- `summary_text` is generated only from the run summaries through fixed
  templates — byte-identical for identical numbers (AC-P7.4).
- Refuses meaningless comparisons: policy comparison on a direct-mapped
  config (E_CONFIG_INVALID), org comparison without a set-associative base
  (E_JOB_INVALID), empty traces (E_TRACE_INVALID).
"""

import errno
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

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


def run_experiment(request, simulate_fn):
    """Runs one experiment for `request` (architecture.md 6.9).

    `simulate_fn(job)` must return the engine's ok-envelope for
    {"config": ..., "trace": ...} (use bots.engine_client.run_simulate in
    production; tests inject a stub). Returns
    {"ok": True, "record": <experiment record>} or
    {"ok": False, "error": {"code", "message", "details"}}.
    """
    try:
        return {"ok": True, "record": _run_experiment(request, simulate_fn)}
    except ExperimentBotError as err:
        return {"ok": False, "error": err.as_error_dict()}
    except EngineError as err:
        return {"ok": False, "error": err.as_error_dict()}


def save_report(record, directory):
    """Writes the record as `<directory>/<experiment_id>.json` with
    deterministic bytes (sorted keys, 2-space indent, trailing newline).
    Returns the written path. The caller decides the directory (rules.md 4;
    the production location is `reports/`).

    The write is an atomic no-clobber creation (`O_CREAT | O_EXCL`, honored
    on POSIX and Windows), so two concurrent saves of DIFFERENT content
    under one experiment_id can never overwrite each other — exactly one
    wins and the loser raises FileExistsError; the original file is never
    modified by a refused save. Saving the identical record is idempotent
    (a short bounded poll tolerates a winner that is still mid-write).
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['experiment_id']}.json"
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    data = payload.encode("utf-8")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_BINARY", 0), 0o666)
    except FileExistsError:
        # Lost the creation race, or the file predates this save. Poll
        # briefly so a concurrent identical save stays idempotent (the
        # winner may not have finished writing yet), then fail loudly on a
        # real content conflict — never overwriting the original.
        for _ in range(50):
            if path.read_text(encoding="utf-8") == payload:
                return path
            time.sleep(0.01)
        raise FileExistsError(
            errno.EEXIST,
            f"a different report already exists for experiment_id "
            f"{record['experiment_id']!r}; not overwriting it (remove the "
            f"stale file or re-run the experiment)", str(path))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except OSError:
        # This file was exclusively created by THIS save, so a failed write
        # must not leave a misleading empty/partial report behind. The
        # primary error is re-raised; only the best-effort cleanup is
        # allowed to fail silently.
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _run_experiment(request, simulate_fn):
    _validate_shape(request)
    mode = request["mode"]
    config = request["config"]
    _validate_config_shape(config)

    if mode == "policy_comparison":
        if config.get("organization") == "direct":
            raise ExperimentBotError(
                "E_CONFIG_INVALID",
                "policy_comparison requires a multi-way organization: "
                "direct-mapped caches have no selectable replacement "
                "policy (use organization_comparison, or a "
                "set_associative/fully_associative config)",
                [_issue("config.organization",
                        "direct-mapped configs cannot be policy-compared",
                        config.get("organization"))])
        random_seed = _validated_random_seed(request)
        run_specs = _policy_run_specs(config, random_seed)
        # associativity exists only for set_associative (architecture.md 6.1);
        # fully_associative configs carry no such field.
        fixed = {"capacity_bytes": config["capacity_bytes"],
                 "block_size_bytes": config["block_size_bytes"],
                 "organization": config["organization"],
                 "address_width_bits": config["address_width_bits"]}
        if config["organization"] == "set_associative":
            fixed["associativity"] = config["associativity"]
    else:
        if "random_seed" in request:
            raise ExperimentBotError(
                "E_JOB_INVALID",
                "random_seed is only used by policy_comparison",
                [_issue("random_seed", "not applicable in "
                        "organization_comparison", request["random_seed"])])
        if config.get("organization") != "set_associative":
            raise ExperimentBotError(
                "E_JOB_INVALID",
                "organization_comparison requires a set_associative base "
                "config (it supplies the associativity); got "
                f"{config.get('organization')!r}",
                [_issue("config.organization",
                        "must be set_associative for organization_comparison",
                        config.get("organization"))])
        associativity = config.get("associativity")
        if isinstance(associativity, bool) or \
                not isinstance(associativity, int):
            raise ExperimentBotError(
                "E_JOB_INVALID",
                "organization_comparison requires an integer "
                "config.associativity in the set_associative base config",
                [_issue("config.associativity", "must be an integer",
                        associativity)])
        run_specs = _organization_run_specs(config)
        fixed = {"capacity_bytes": config["capacity_bytes"],
                 "block_size_bytes": config["block_size_bytes"],
                 "address_width_bits": config["address_width_bits"]}

    trace = _validated_trace(request["trace"], config)

    runs = []
    versions = set()
    digests = set()
    for run_id, (run_config, policy, seed) in enumerate(run_specs, start=1):
        envelope = simulate_fn({"config": run_config, "trace": trace})
        if not isinstance(envelope, dict) or envelope.get("ok") is not True:
            raise ExperimentBotError(
                "E_INTERNAL", "simulate_fn returned a non-ok envelope")
        summary = envelope["summary"]
        versions.add(envelope["engine"]["version"])
        digests.add(summary["trace_sha256"])
        runs.append({"run_id": run_id, "config": run_config,
                     "policy": policy, "seed": seed, "summary": summary})
    if len(versions) != 1:
        raise ExperimentBotError(
            "E_INTERNAL", "runs disagree on the engine version",
            [_issue("engine.version", "must be identical across runs",
                    sorted(versions))])
    if len(digests) != 1:
        raise ExperimentBotError(
            "E_INTERNAL", "runs disagree on the trace digest",
            [_issue("summary.trace_sha256", "must be identical across runs",
                    sorted(digests))])

    created = datetime.now(timezone.utc)
    mode_word = "policy" if mode == "policy_comparison" else "organization"
    amat_assumptions = None
    if config.get("hit_time") is not None and \
            config.get("miss_penalty") is not None:
        amat_assumptions = {"hit_time": config["hit_time"],
                            "miss_penalty": config["miss_penalty"],
                            "unit": "cycles"}
    return {
        # Microsecond precision (D-30): two different experiments completing
        # in the same wall-clock second must never share an id and overwrite
        # each other's report files. The schema accepts the historical
        # second-resolution format for records saved before D-30.
        "experiment_id": f"exp-{created:%Y%m%d-%H%M%S}-"
                         f"{created.microsecond:06d}-{mode_word}",
        "mode": mode,
        "created_utc": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine_version": versions.pop(),
        "trace": {"name": trace["name"], "sha256": digests.pop(),
                  "addresses": trace["addresses"]},
        "fixed": fixed,
        "amat_assumptions": amat_assumptions,
        "runs": runs,
        "summary_text": _summary_text(mode, runs),
    }


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


def _policy_run_specs(config, random_seed):
    """One variable changes: only `policy` (and the RANDOM run's seed)
    differ between the three run configs."""
    specs = []
    for policy in _POLICIES:
        run_config = dict(config)
        run_config["policy"] = policy
        run_config.pop("seed", None)  # a stale seed would be invalid (D-17)
        seed = None
        if policy == "RANDOM":
            run_config["seed"] = random_seed
            seed = random_seed
        specs.append((run_config, policy, seed))
    return specs


def _organization_run_specs(config):
    """One variable changes: only `organization` (plus the structurally
    implied policy/associativity) differs between the three run configs."""
    common = {key: value for key, value in config.items()
              if key not in ("organization", "associativity", "policy",
                             "seed")}
    direct = dict(common, organization="direct")
    set_associative = dict(common, organization="set_associative",
                           associativity=config["associativity"],
                           policy="LRU")
    fully = dict(common, organization="fully_associative", policy="LRU")
    return [(direct, None, None),
            (set_associative, "LRU", None),
            (fully, "LRU", None)]


def _run_label(mode, run):
    if mode == "policy_comparison":
        if run["policy"] == "RANDOM":
            return f"RANDOM (seed {run['seed']})"
        return run["policy"]
    return run["config"]["organization"]


def _short_label(mode, run):
    """Label for the best-hit-rate sentence: the seed stays in the per-run
    sentences, so winners/losers are named by policy or organization only."""
    if mode == "policy_comparison":
        return run["policy"]
    return run["config"]["organization"]


def _join(names):
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _summary_text(mode, runs):
    """Fixed sentence templates over the run summaries (architecture.md
    6.9): one sentence per run, then the best-hit-rate sentence, then the
    org-mode caveat. Deterministic for identical numbers."""

    def pct(rate):
        return f"{rate * 100:.2f}"

    def plural(count, singular, plural_form=None):
        if count == 1:
            return f"{count} {singular}"
        return f"{count} {plural_form or singular + 's'}"

    sentences = []
    for run in runs:
        summary = run["summary"]
        sentences.append(
            f"{_run_label(mode, run)}: "
            f"{plural(summary['hits'], 'hit')} / "
            f"{plural(summary['accesses'], 'access', 'accesses')} "
            f"({pct(summary['hit_rate'])}%), "
            f"{plural(summary['evictions'], 'eviction')}.")
    best = max(run["summary"]["hit_rate"] for run in runs)
    winners = [_short_label(mode, run) for run in runs
               if abs(run["summary"]["hit_rate"] - best) <= 1e-12]
    losers = [(_short_label(mode, run), run["summary"]["hit_rate"])
              for run in runs
              if abs(run["summary"]["hit_rate"] - best) > 1e-12]
    if len(winners) == 1:
        if losers:
            tail = " vs " + " and ".join(
                f"{label} {pct(rate)}%" for label, rate in losers)
            sentences.append(f"Best hit rate: {winners[0]} "
                             f"({pct(best)}%{tail}).")
        else:
            sentences.append(f"Best hit rate: {winners[0]} ({pct(best)}%).")
    elif losers:
        sentences.append(
            f"Best hit rate: {_join(winners)} tie at {pct(best)}% "
            f"({' and '.join(f'{label} {pct(rate)}%' for label, rate in losers)}).")
    else:
        sentences.append(f"Best hit rate: {_join(winners)} tie at {pct(best)}%.")
    if mode == "organization_comparison":
        sentences.append(_ORG_CAVEAT)
    return " ".join(sentences)
