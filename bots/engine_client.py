"""Subprocess client for the cache_sim engine (architecture.md 5).

Contract hardening (Phase 8, decision D-23): one subprocess attempt is
wrapped in a bounded retry loop that retries only transient failures —
never validation errors. Payloads travel via stdin, so the engine keeps
its filesystem contract (reads only --in/stdin, writes only
--out/stdout).

Failure taxonomy (AC-P8.1):
- Error envelopes from the engine (it ran and reported an E_* code) are
  terminal: raised as EngineError with the engine's code/message/details,
  never retried.
- Spawn failures, timeouts, undocumented exit codes, and unparseable
  output are transient: retried up to `max_retries` times, then raised as
  EngineError("E_INTERNAL", ...).
"""

import json
import os
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ENGINE_PATH = _PROJECT_ROOT / "build" / "cache_sim.exe"
_DEFAULT_TIMEOUT_S = 30.0  # architecture.md 12
_DEFAULT_MAX_RETRIES = 2   # architecture.md 11: transient failures only
_DOCUMENTED_EXIT_CODES = (0, 2, 3, 4)


class EngineError(Exception):
    """Engine-side or client-side failure carrying an E_* code."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details if details is not None else []

    def as_error_dict(self):
        return {"code": self.code, "message": self.message,
                "details": self.details}


class _TransientError(Exception):
    """Internal: a failure worth retrying (spawn, timeout, crash, or
    unparseable output — the engine never got far enough to report an
    E_* code)."""


def engine_path():
    """Engine location: the ENGINE_PATH environment variable overrides the
    default build/ output (architecture.md 4)."""
    override = os.environ.get("ENGINE_PATH")
    return Path(override) if override else _DEFAULT_ENGINE_PATH


def _spawn_attempt(exe, mode, payload_text, timeout_s):
    """One subprocess attempt. Returns (returncode, stdout, stderr); raises
    _TransientError on spawn or timeout failures and on exit codes outside
    the documented vocabulary (a crash before an envelope was written)."""
    try:
        proc = subprocess.run(
            [str(exe), "--mode", mode],
            input=payload_text,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        raise _TransientError(f"engine did not finish within {timeout_s} s")
    except OSError as err:
        raise _TransientError(f"cannot run the engine: {err}")
    if proc.returncode not in _DOCUMENTED_EXIT_CODES:
        raise _TransientError(
            f"engine exited with undocumented code {proc.returncode}")
    return proc.returncode, proc.stdout, proc.stderr


def _parse_envelope(stdout):
    """Parses the JSON envelope; raises _TransientError for unparseable or
    wrongly shaped output."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        raise _TransientError("engine produced no valid JSON envelope")
    if not isinstance(envelope, dict) or "ok" not in envelope:
        raise _TransientError("engine envelope has an unexpected shape")
    return envelope


# Required members of an ok envelope per mode (architecture.md 6.2-6.7).
# Transport-level shape validation: a stale or mismatched engine binary
# that emits a "successful" envelope missing its contract fields must
# produce a clear E_INTERNAL at this boundary — never a false success that
# crashes later consumers with a KeyError.
_OK_ENVELOPE_FIELDS = {
    "version": ("engine",),
    "geometry": ("engine", "geometry"),
    "simulate": ("engine", "geometry", "events", "summary", "state"),
}


def _ok_envelope_complete(mode, envelope):
    """True when the ok envelope carries the mode's contract fields with
    the documented shapes (architecture.md 6.3-6.7)."""
    engine_meta = envelope.get("engine")
    if not isinstance(engine_meta, dict) or \
            not isinstance(engine_meta.get("version"), str) or \
            not engine_meta["version"]:
        return False
    for field in _OK_ENVELOPE_FIELDS.get(mode, ()):  # unknown modes: lenient
        value = envelope.get(field)
        if field == "engine":
            continue  # already checked above
        if field == "events":
            if not isinstance(value, list):
                return False
        elif not isinstance(value, dict):
            return False
    return True


def run_mode(mode, payload, timeout_s=_DEFAULT_TIMEOUT_S,
             max_retries=_DEFAULT_MAX_RETRIES):
    """Runs `cache_sim --mode <mode>` with the payload on stdin.

    Returns the parsed ok-envelope. Error envelopes are terminal and raise
    EngineError with the engine's E_* code/message/details (never retried);
    transient failures retry up to `max_retries` times, then raise
    EngineError("E_INTERNAL", ...) (architecture.md 11).
    """
    exe = engine_path()
    if not exe.exists():
        raise EngineError(
            "E_INTERNAL",
            f"engine executable not found at {exe}; build it with: "
            "mingw32-make -C engine all")
    payload_text = json.dumps(payload)
    last_transient = None
    envelope = None
    returncode = None
    for _ in range(max_retries + 1):
        try:
            returncode, stdout, _stderr = _spawn_attempt(
                exe, mode, payload_text, timeout_s)
            envelope = _parse_envelope(stdout)
        except _TransientError as err:
            last_transient = err
            continue
        exit_ok = returncode == 0
        envelope_ok = envelope.get("ok") is True
        if exit_ok != envelope_ok:
            # The engine ran and produced an envelope that contradicts its
            # own exit code — a contract bug, not a transient failure.
            raise EngineError(
                "E_INTERNAL",
                f"engine exit code {returncode} contradicts the envelope",
                [_issue_like("returncode", "must agree with envelope.ok",
                             returncode)])
        if envelope_ok and not _ok_envelope_complete(mode, envelope):
            # Terminal: a stale/broken engine binary will not fix itself on
            # retry (rules.md 3 — retries are for transient spawn/IO only).
            raise EngineError(
                "E_INTERNAL",
                f"engine ok envelope is missing its {mode}-mode contract "
                "fields (stale or mismatched engine binary?)",
                [_issue_like("envelope",
                             "missing required fields: "
                             + ", ".join(_OK_ENVELOPE_FIELDS.get(mode, ())),
                             sorted(envelope.keys()))])
        last_transient = None
        break
    if last_transient is not None:
        raise EngineError(
            "E_INTERNAL",
            f"engine could not be started after {max_retries + 1} "
            f"attempt(s): {last_transient}")
    if envelope_ok:
        return envelope
    error = envelope.get("error", {})
    raise EngineError(error.get("code", "E_INTERNAL"),
                      error.get("message", "engine reported failure"),
                      error.get("details", []))


def _issue_like(field, problem, received):
    return {"field": field, "problem": problem, "received": received}


def fetch_geometry(config):
    """Validates `config` through the engine's geometry mode and returns
    the derived geometry dict (decision D-6: Bot 1 never derives geometry
    itself)."""
    return run_mode("geometry", config)["geometry"]


def run_simulate(job, timeout_s=_DEFAULT_TIMEOUT_S):
    """Runs `--mode simulate` with the job (config + trace + options) and
    returns the ok-envelope (architecture.md 6.4-6.7). Used by Bot 2 and
    the integration layer."""
    return run_mode("simulate", job, timeout_s)
