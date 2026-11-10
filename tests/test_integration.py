"""Phase 8: cross-component integration tests — the full non-UI stack.

Bot 1 (trace generation with real geometry) → engine (simulate via
engine_client) → Bot 2 (experiment runner) → saved report, plus error
paths, the retry taxonomy (AC-P8.1), and AC-6/AC-7/AC-9/AC-12 through the
Python path. Skipped loudly when the engine has not been built.
"""

import hashlib
import json

import pytest

import test_smoke as ts
from bots import engine_client
from bots.experiment_bot import run_experiment, save_report
from bots.trace_bot import generate

ENGINE = ts.ROOT / "build" / "cache_sim.exe"
ENGINE_SKIP = ts.ENGINE_SKIP

pytestmark = pytest.mark.skipif(not ENGINE.exists(), reason=ENGINE_SKIP)


def _generate(request):
    return generate(request, engine_client.fetch_geometry)


# --- Retry taxonomy (AC-P8.1) -------------------------------------------------


class TestRetryTaxonomy:
    def test_validation_errors_are_never_retried(self, monkeypatch):
        calls = []

        def fake_spawn(exe, mode, payload_text, timeout_s):
            calls.append(mode)
            return 3, json.dumps({
                "ok": False,
                "engine": {"name": "cache_sim", "version": "0.1.0"},
                "error": {"code": "E_CONFIG_INVALID",
                          "message": "bad config", "details": []},
            }), ""

        monkeypatch.setattr(engine_client, "_spawn_attempt", fake_spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_mode("geometry", {"capacity_bytes": 8})
        assert excinfo.value.code == "E_CONFIG_INVALID"
        assert len(calls) == 1  # terminal — the engine spoke, no retry

    def test_transient_failures_retry_then_raise(self, monkeypatch):
        calls = []

        def flaky_spawn(exe, mode, payload_text, timeout_s):
            calls.append(mode)
            raise engine_client._TransientError("simulated crash")

        monkeypatch.setattr(engine_client, "_spawn_attempt", flaky_spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_mode("geometry", {"capacity_bytes": 8})
        assert excinfo.value.code == "E_INTERNAL"
        assert "3 attempt(s)" in excinfo.value.message
        assert len(calls) == 3  # first try + max 2 retries

    def test_success_after_one_transient_failure(self, monkeypatch):
        calls = []
        envelope = {"ok": True,
                    "engine": {"name": "cache_sim", "version": "0.1.0"},
                    "geometry": ts.GEOMETRY_DEMO}

        def flaky_spawn(exe, mode, payload_text, timeout_s):
            calls.append(mode)
            if len(calls) == 1:
                raise engine_client._TransientError("simulated crash")
            return 0, json.dumps(envelope), ""

        monkeypatch.setattr(engine_client, "_spawn_attempt", flaky_spawn)
        result = engine_client.run_mode("geometry", ts.CONFIG_SET_ASSOCIATIVE)
        assert result["geometry"] == ts.GEOMETRY_DEMO
        assert len(calls) == 2  # retried once, then succeeded

    def test_undocumented_exit_code_is_transient(self, monkeypatch):
        calls = []

        def crashing_spawn(exe, mode, payload_text, timeout_s):
            calls.append(mode)
            return 139, "", ""

        monkeypatch.setattr(engine_client, "_spawn_attempt", crashing_spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_mode("geometry", {"capacity_bytes": 8})
        assert excinfo.value.code == "E_INTERNAL"
        assert len(calls) == 3

    def test_empty_stdout_with_documented_exit_code_is_transient(self,
                                                                 monkeypatch):
        # Regression (2026-10-27 audit-2): the pre-fix engine could die with
        # std::bad_alloc — empty stdout on the DOCUMENTED exit code 3. The
        # client must treat that as transient, not accept it as a result.
        calls = []

        def crashing_spawn(exe, mode, payload_text, timeout_s):
            calls.append(mode)
            return 3, "", ""  # documented code, no envelope

        monkeypatch.setattr(engine_client, "_spawn_attempt", crashing_spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_mode("simulate", {"config": {}, "trace": {}})
        assert excinfo.value.code == "E_INTERNAL"
        assert len(calls) == 3


class TestOkEnvelopeShape:
    """Transport-level ok-envelope shape validation (audit-2): a stale or
    mismatched engine binary emitting a 'successful' envelope without its
    contract fields must fail as E_INTERNAL at this boundary — never flow
    through as a false success that crashes consumers with a KeyError."""

    @staticmethod
    def _ok_envelope(mode):
        envelope = {"ok": True,
                    "engine": {"name": "cache_sim", "version": "0.1.0"}}
        if mode == "geometry":
            envelope["geometry"] = ts.GEOMETRY_DEMO
        else:
            envelope.update({
                "geometry": ts.GEOMETRY_DEMO,
                "events": [],
                "summary": {"accesses": 0, "hits": 0, "misses": 0,
                            "evictions": 0, "hit_rate": None,
                            "miss_rate": None, "trace_sha256": "0" * 64},
                "state": {"sets": [], "snapshots": None},
            })
        return envelope

    def test_complete_envelopes_are_accepted(self, monkeypatch):
        for mode in ("version", "geometry", "simulate"):
            def spawn(exe, m, payload_text, timeout_s, _mode=mode):
                return 0, json.dumps(self._ok_envelope(_mode)), ""
            monkeypatch.setattr(engine_client, "_spawn_attempt", spawn)
            payload = ({} if mode == "version"
                       else ts.CONFIG_SET_ASSOCIATIVE if mode == "geometry"
                       else {"config": ts.CONFIG_SET_ASSOCIATIVE,
                             "trace": {"name": "t", "addresses": []}})
            assert engine_client.run_mode(mode, payload)["ok"] is True

    def test_missing_summary_is_terminal_internal(self, monkeypatch):
        calls = []
        envelope = self._ok_envelope("simulate")
        del envelope["summary"]

        def spawn(exe, mode, payload_text, timeout_s):
            calls.append(mode)
            return 0, json.dumps(envelope), ""

        monkeypatch.setattr(engine_client, "_spawn_attempt", spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_simulate({"config": ts.CONFIG_SET_ASSOCIATIVE,
                                        "trace": {"name": "t",
                                                  "addresses": []}})
        assert excinfo.value.code == "E_INTERNAL"
        assert "contract fields" in excinfo.value.message
        assert len(calls) == 1  # terminal — retrying a stale exe is futile

    def test_missing_engine_version_is_terminal_internal(self, monkeypatch):
        envelope = self._ok_envelope("geometry")
        envelope["engine"] = {"name": "cache_sim"}

        def spawn(exe, mode, payload_text, timeout_s):
            return 0, json.dumps(envelope), ""

        monkeypatch.setattr(engine_client, "_spawn_attempt", spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.fetch_geometry(ts.CONFIG_SET_ASSOCIATIVE)
        assert excinfo.value.code == "E_INTERNAL"

    def test_wrongly_typed_events_is_terminal_internal(self, monkeypatch):
        envelope = self._ok_envelope("simulate")
        envelope["events"] = {"not": "a list"}

        def spawn(exe, mode, payload_text, timeout_s):
            return 0, json.dumps(envelope), ""

        monkeypatch.setattr(engine_client, "_spawn_attempt", spawn)
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_simulate({"config": ts.CONFIG_SET_ASSOCIATIVE,
                                        "trace": {"name": "t",
                                                  "addresses": []}})
        assert excinfo.value.code == "E_INTERNAL"


# --- Missing engine (AC-P8.3) --------------------------------------------------


class TestMissingEngine:
    def test_actionable_error_not_a_crash(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ENGINE_PATH", str(tmp_path / "nope.exe"))
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.fetch_geometry(ts.CONFIG_SET_ASSOCIATIVE)
        assert excinfo.value.code == "E_INTERNAL"
        assert "mingw32-make" in excinfo.value.message

    def test_structured_error_through_the_bot_boundary(self, tmp_path,
                                                       monkeypatch):
        monkeypatch.setenv("ENGINE_PATH", str(tmp_path / "nope.exe"))
        response = _generate({
            "pattern": "repeated",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"address": 16, "count": 2},
        })
        assert response["ok"] is False
        assert response["error"]["code"] == "E_INTERNAL"
        assert "mingw32-make" in response["error"]["message"]

    def test_spawn_is_working_directory_independent(self, tmp_path,
                                                    monkeypatch):
        # Audit-2 (§8): the engine reads only stdin/stdout and the client
        # spawns it by absolute path — the caller's cwd must not matter.
        monkeypatch.chdir(tmp_path)
        envelope = engine_client.run_mode("version", {})
        assert envelope["ok"] is True
        assert envelope["engine"]["version"] == "0.1.0"


# --- Sample traces --------------------------------------------------------------


class TestSampleTraces:
    def test_json_and_txt_versions_agree(self):
        traces = ts.ROOT / "traces"
        for stem in ("e1-repeated", "e2-conflict", "e3-lru-vs-fifo",
                     "sequential-100"):
            data = json.loads(
                (traces / f"{stem}.json").read_text(encoding="utf-8"))
            text = (traces / f"{stem}.txt").read_text(encoding="utf-8")
            response = _generate({"pattern": "manual",
                                  "config": ts.CONFIG_SET_ASSOCIATIVE,
                                  "params": {"text": text}})
            assert response["ok"] is True, (stem, response)
            assert response["trace"]["addresses"] == data["addresses"]

    def test_e3_sample_matches_the_published_trace(self):
        data = json.loads(
            (ts.ROOT / "traces" / "e3-lru-vs-fifo.json")
            .read_text(encoding="utf-8"))
        assert data["addresses"] == [0, 4, 0, 8, 4]


# --- Full scripted workflow (AC-P8.2) --------------------------------------------


class TestFullWorkflow:
    def test_bot1_engine_bot2_report_reproducible(self, tmp_path):
        # 1. Bot 1 generates a conflict trace (real geometry, D-6).
        gen = _generate({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 4, "passes": 1, "target_set": 0,
                       "start_block": 0},
        })
        assert gen["ok"] is True
        trace = {"name": gen["trace"]["name"],
                 "addresses": gen["trace"]["addresses"]}
        assert trace["addresses"] == [0, 4, 8, 12]

        # 2. The engine processes that trace.
        job = {"config": ts.CONFIG_SET_ASSOCIATIVE, "trace": trace}
        sim1 = engine_client.run_simulate(job)
        assert sim1["summary"]["accesses"] == 4

        # 3. Bot 2 runs a policy comparison on that trace.
        request = {"mode": "policy_comparison", "trace": trace,
                   "config": ts.CONFIG_SET_ASSOCIATIVE,
                   "random_seed": 12345}
        exp1 = run_experiment(request, engine_client.run_simulate)
        assert exp1["ok"] is True
        record = exp1["record"]
        assert [run["policy"] for run in record["runs"]] == [
            "LRU", "FIFO", "RANDOM"]

        # 4. The report is saved under the caller's directory.
        path = save_report(record, tmp_path / "reports")
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == record

        # 5. Re-running reproduces byte-identical summaries (AC-P8.2).
        sim2 = engine_client.run_simulate(job)
        assert json.dumps(sim1["summary"], sort_keys=True) == \
            json.dumps(sim2["summary"], sort_keys=True)
        exp2 = run_experiment(request, engine_client.run_simulate)
        assert exp2["record"]["summary_text"] == record["summary_text"]
        assert [run["summary"] for run in exp2["record"]["runs"]] == \
            [run["summary"] for run in record["runs"]]
        assert exp2["record"]["trace"]["sha256"] == record["trace"]["sha256"]

    def test_e1_sample_through_the_python_path(self):
        data = json.loads(
            (ts.ROOT / "traces" / "e1-repeated.json")
            .read_text(encoding="utf-8"))
        envelope = engine_client.run_simulate(
            {"config": ts.CONFIG_DIRECT, "trace": data})
        assert envelope["summary"] == {
            "accesses": 5, "hits": 4, "misses": 1, "evictions": 0,
            "hit_rate": 0.8, "miss_rate": 0.2,
            "amat": {"hit_time": 1.0, "miss_penalty": 20.0, "value": 5.0,
                     "unit": "cycles"},
            "trace_sha256": hashlib.sha256(
                b"addresses:16,16,16,16,16").hexdigest(),
        }

    def test_engine_determinism_through_the_python_path(self):
        job = {"config": dict(ts.CONFIG_SET_ASSOCIATIVE, policy="RANDOM",
                              seed=12345),
               "trace": {"name": "det", "addresses": [0, 4, 0, 8, 4]}}
        first = engine_client.run_simulate(job)
        second = engine_client.run_simulate(job)
        assert json.dumps(first, sort_keys=True) == \
            json.dumps(second, sort_keys=True)


# --- Error paths through the Python path (AC-P8.4) --------------------------------


class TestErrorPaths:
    def test_invalid_config_surfaces_details(self):  # AC-6
        response = _generate({
            "pattern": "sequential",
            "config": dict(ts.CONFIG_SET_ASSOCIATIVE, block_size_bytes=6),
            "params": {"start_address": 0, "count": 4, "stride_bytes": 1},
        })
        assert response["ok"] is False
        assert response["error"]["code"] == "E_CONFIG_INVALID"
        detail = response["error"]["details"][0]
        assert detail["field"] == "block_size_bytes"
        assert detail["received"] == 6

    def test_address_over_width_surfaces_twice_over(self):  # AC-7
        # Bot-level rejection before the engine is consulted.
        bot_response = _generate({
            "pattern": "repeated",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"address": 300, "count": 2},
        })
        assert bot_response["error"]["code"] == "E_TRACE_INVALID"
        # Engine-level rejection when the address arrives in a job.
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_simulate({
                "config": ts.CONFIG_DIRECT,
                "trace": {"name": "over", "addresses": [256]}})
        assert excinfo.value.code == "E_TRACE_INVALID"
        # The engine's detail fields are trace-relative (architecture.md 5.3).
        assert excinfo.value.details[0]["field"] == "addresses[0]"

    def test_empty_trace_is_safe(self):  # AC-9
        envelope = engine_client.run_simulate({
            "config": ts.CONFIG_DIRECT,
            "trace": {"name": "empty", "addresses": []}})
        assert envelope["summary"]["accesses"] == 0
        assert envelope["summary"]["hit_rate"] is None
        assert envelope["summary"]["miss_rate"] is None

    def test_malformed_job_rejected(self):  # AC-9
        with pytest.raises(engine_client.EngineError) as excinfo:
            engine_client.run_simulate({"config": ts.CONFIG_DIRECT})
        assert excinfo.value.code == "E_JOB_INVALID"
        assert any(d["field"] == "trace"
                   for d in excinfo.value.details)

    def test_engine_determinism_double_run(self):  # AC-12
        job = {"config": ts.CONFIG_SET_ASSOCIATIVE,
               "trace": {"name": "e3", "addresses": [0, 4, 0, 8, 4]}}
        first = engine_client.run_simulate(job)
        second = engine_client.run_simulate(job)
        assert first["events"] == second["events"]
        assert first["summary"] == second["summary"]
