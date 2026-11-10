"""Phase 1 smoke tests: engine CLI contract + canonical schema validation.

Engine tests are skipped with a clear, visible message when the executable
has not been built yet (rules.md 5: the skip is reported, never hidden):

    mingw32-make -C engine all

Schema examples are drawn from the worked examples in architecture.md 6 and
13 (E1-E3); they are documentation fixtures, not simulation expectations.
"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "build" / "cache_sim.exe"
SCHEMAS = ROOT / "schemas"

ENGINE_SKIP = "build/cache_sim.exe is missing - run: mingw32-make -C engine all"


def run_engine(*args: str, stdin_text: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(ENGINE), *args], capture_output=True, text=True, timeout=30,
        input=stdin_text,
    )


@pytest.mark.skipif(not ENGINE.exists(), reason=ENGINE_SKIP)
class TestEngineContract:
    def test_version_envelope_is_exact(self):
        proc = run_engine("--mode", "version")
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == {
            "ok": True,
            "engine": {"name": "cache_sim", "version": "0.1.0"},
        }

    def test_version_with_out_file_leaves_stdout_empty(self, tmp_path):
        out = tmp_path / "version.json"
        proc = run_engine("--mode", "version", "--out", str(out))
        assert proc.returncode == 0
        assert proc.stdout == ""
        assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True

    @pytest.mark.parametrize("args", [[], ["--bogus"], ["--mode", "nope"]])
    def test_usage_errors_are_enveloped_exit_2(self, args):
        proc = run_engine(*args)
        assert proc.returncode == 2
        envelope = json.loads(proc.stdout)
        assert envelope["ok"] is False
        assert envelope["error"]["code"] == "E_USAGE"
        assert "usage: cache_sim" in envelope["error"]["message"]

    def test_simulate_requires_a_readable_job_file(self, tmp_path):
        # Phase 3: simulate is fully implemented; an unreadable input file
        # is still a usage error.
        proc = run_engine("--mode", "simulate", "--in", str(tmp_path / "nope.json"))
        assert proc.returncode == 2
        assert json.loads(proc.stdout)["error"]["code"] == "E_USAGE"

    def test_unreadable_input_file_is_usage_error(self, tmp_path):
        proc = run_engine("--mode", "simulate", "--in", str(tmp_path / "nope.json"))
        assert proc.returncode == 2
        assert json.loads(proc.stdout)["error"]["code"] == "E_USAGE"


@pytest.mark.skipif(not ENGINE.exists(), reason=ENGINE_SKIP)
class TestSimulateMode:
    """Phase 3: --mode simulate (AC-P3.1..P3.4)."""

    def _run_job(self, job, tmp_path):
        f = tmp_path / "job.json"
        f.write_text(json.dumps(job), encoding="utf-8")
        return run_engine("--mode", "simulate", "--in", str(f))

    def test_e1_walk_and_summary(self, tmp_path):
        proc = self._run_job(E1_JOB, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        assert envelope["ok"] is True
        assert envelope["echo"] == CONFIG_DIRECT
        events = envelope["events"]
        assert len(events) == 5
        t1 = events[0]
        assert (t1["address"], t1["block"], t1["offset"], t1["set"],
                t1["tag"], t1["way"]) == (16, 8, 0, 0, 2, 0)
        assert t1["result"] == "miss" and t1["loaded"] is True
        assert t1["evicted"] is None
        assert t1["explanation"] == "Miss: block 8 loaded into set 0 way 0 (empty line)."
        for e in events[1:]:
            assert e["result"] == "hit" and e["loaded"] is False
            assert e["explanation"] == "Hit: block 8 found in set 0 way 0 (tag 2)."
        assert envelope["summary"] == {
            "accesses": 5, "hits": 4, "misses": 1, "evictions": 0,
            "hit_rate": 0.8, "miss_rate": 0.2,
            "amat": {"hit_time": 1.0, "miss_penalty": 20.0, "value": 5.0,
                     "unit": "cycles"},
            "trace_sha256": hashlib.sha256(
                b"addresses:16,16,16,16,16").hexdigest(),
        }
        # Direct-mapped: policy null, way always 0.
        assert all(e["policy_meta"]["policy"] is None and e["way"] == 0
                   for e in events)

    def test_event_and_state_validate_against_schemas(self, tmp_path):
        proc = self._run_job(E1_JOB, tmp_path)
        envelope = json.loads(proc.stdout)
        event_errors = list(_validator("event.schema.json").iter_errors(envelope["events"][0]))
        assert not event_errors, [e.message for e in event_errors]
        state_errors = list(_validator("state.schema.json").iter_errors(envelope["state"]))
        assert not state_errors, [e.message for e in state_errors]

    def test_e2_conflict_evictions_and_final_state(self, tmp_path):
        job = {"config": CONFIG_DIRECT,
               "trace": {"name": "e2-conflict", "addresses": [0, 8, 16, 24, 0]}}
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        assert envelope["summary"]["misses"] == 5
        assert envelope["summary"]["evictions"] == 4
        assert envelope["summary"]["hits"] == 0
        evicted_blocks = [e["evicted"]["block"] for e in envelope["events"]
                          if e["evicted"] is not None]
        assert evicted_blocks == [0, 4, 8, 12]
        # The last access reloads block 0, evicting block 12 (architecture.md 13 E2).
        assert envelope["state"]["sets"][0][0]["block"] == 0
        assert envelope["events"][1]["policy_meta"]["victim_selection"] == "forced"

    def test_e3_lru_sequence(self, tmp_path):
        proc = self._run_job(E3_JOB, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        events = envelope["events"]
        assert envelope["summary"] == {
            "accesses": 5, "hits": 1, "misses": 4, "evictions": 2,
            "hit_rate": 0.2, "miss_rate": 0.8,
            "amat": {"hit_time": 1.0, "miss_penalty": 20.0, "value": 17.0,
                     "unit": "cycles"},
            "replacement_meta": {"policy": "LRU"},
            "trace_sha256": hashlib.sha256(
                b"addresses:0,4,0,8,4").hexdigest(),
        }
        assert events[2]["result"] == "hit"
        assert events[3]["evicted"]["block"] == 2
        assert events[3]["explanation"] == (
            "Miss: block 4 loaded into set 0 way 1, evicting block 2 (LRU).")
        assert events[4]["evicted"]["block"] == 0
        assert events[4]["explanation"] == (
            "Miss: block 2 loaded into set 0 way 0, evicting block 0 (LRU).")
        assert envelope["state"]["sets"][0][0]["block"] == 2
        assert envelope["state"]["sets"][0][1]["block"] == 4

    def test_e4_fully_assoc_index_null(self, tmp_path):
        job = {"config": CONFIG_FULLY_ASSOCIATIVE,
               "trace": {"name": "e4-fully", "addresses": [0, 4, 8]}}
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        assert all(e["index"] is None and e["set"] == 0
                   for e in envelope["events"])
        assert [e["way"] for e in envelope["events"]] == [0, 1, 2]
        assert envelope["summary"]["evictions"] == 0
        assert envelope["state"]["sets"][0][3]["valid"] is False

    def test_snapshots_requested_and_returned(self, tmp_path):
        job = dict(E3_JOB, options={"include_state_after_each": True})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        state = json.loads(proc.stdout)["state"]
        assert len(state["snapshots"]) == 5  # one per access
        assert state["snapshots"][0]["n"] == 1
        assert state["snapshots"][0]["sets"][0][1]["valid"] is False
        assert state["snapshots"][1]["n"] == 2
        assert state["snapshots"][1]["sets"][0][1]["valid"] is True

    def test_snapshot_trace_cap_2000(self, tmp_path):
        # Width 16 so all 2001 addresses are valid; the snapshot cap (not
        # trace validation) must produce the E_LIMIT.
        job = {
            "config": dict(CONFIG_SET_ASSOCIATIVE, address_width_bits=16),
            "trace": {"name": "too-long-for-snapshots",
                      "addresses": list(range(2001))},
            "options": {"include_state_after_each": True},
        }
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 3
        error = json.loads(proc.stdout)["error"]
        assert error["code"] == "E_LIMIT"
        assert "2000" in error["details"][0]["problem"]

    def test_trace_over_100k_is_limit(self, tmp_path):
        job = dict(E1_JOB, trace={"name": "huge", "addresses": [0] * 100001})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 3
        error = json.loads(proc.stdout)["error"]
        assert error["code"] == "E_LIMIT"
        assert "100000" in error["details"][0]["problem"]

    def test_address_above_width_is_trace_invalid(self, tmp_path):
        job = dict(E1_JOB, trace={"name": "bad-addr", "addresses": [256, 16]})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 3
        error = json.loads(proc.stdout)["error"]
        assert error["code"] == "E_TRACE_INVALID"
        assert error["details"][0]["field"] == "addresses[0]"
        assert error["details"][0]["received"] == 256

    def test_unknown_job_key_rejected(self, tmp_path):
        job = dict(E1_JOB, traces={"name": "typo", "addresses": []})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 3
        assert json.loads(proc.stdout)["error"]["code"] == "E_JOB_INVALID"

    def test_extreme_state_demand_never_crashes(self, tmp_path):
        # Regression (2026-10-27 audit-2): a VALID supported configuration
        # (2^20-line cache, 100,000-access trace) exhausted memory and died
        # with an uncaught std::bad_alloc — empty stdout and the abort exit
        # code, colliding with the documented validation code 3. The engine
        # must always return a contract envelope: ok success, or a
        # structured E_INTERNAL with the documented exit code 4.
        job = {"config": {"capacity_bytes": 1048576, "block_size_bytes": 1,
                          "organization": "direct", "address_width_bits": 21},
               "trace": {"name": "huge-state",
                         "addresses": [(7 * i) & 0x1FFFFF
                                       for i in range(100000)]}}
        f = tmp_path / "huge-job.json"
        f.write_text(json.dumps(job), encoding="utf-8")
        proc = subprocess.run(
            [str(ENGINE), "--mode", "simulate", "--in", str(f)],
            capture_output=True, text=True, timeout=120)
        envelope = json.loads(proc.stdout)  # stdout must be a contract envelope
        if envelope["ok"] is True:
            assert proc.returncode == 0
            assert envelope["summary"]["accesses"] == 100000
        else:
            assert proc.returncode == 4
            assert envelope["error"]["code"] == "E_INTERNAL"

    def test_missing_trace_rejected(self, tmp_path):
        job = {"config": CONFIG_DIRECT}
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 3
        error = json.loads(proc.stdout)["error"]
        assert error["code"] == "E_JOB_INVALID"
        assert any(d["field"] == "trace" for d in error["details"])

    def test_unknown_trace_key_rejected(self, tmp_path):
        job = dict(E1_JOB, trace={"name": "x", "addresses": [16], "addr": [16]})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 3
        error = json.loads(proc.stdout)["error"]
        assert error["code"] == "E_TRACE_INVALID"
        assert error["details"][0]["field"] == "addr"

    def test_empty_trace_is_safe(self, tmp_path):
        job = dict(E1_JOB, trace={"name": "empty", "addresses": []})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        assert envelope["events"] == []
        assert envelope["summary"]["hit_rate"] is None
        assert envelope["summary"]["miss_rate"] is None


@pytest.mark.skipif(not ENGINE.exists(), reason=ENGINE_SKIP)
class TestPoliciesAndStats:
    """Phase 4: FIFO/RANDOM policies, AMAT, trace digest, replacement_meta."""

    def _run_job(self, job, tmp_path):
        f = tmp_path / "job.json"
        f.write_text(json.dumps(job), encoding="utf-8")
        return run_engine("--mode", "simulate", "--in", str(f))

    def test_e3_fifo_walk(self, tmp_path):
        job = {"config": dict(CONFIG_SET_ASSOCIATIVE, policy="FIFO"),
               "trace": {"name": "fifo-demo", "addresses": [0, 4, 0, 8, 4]}}
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        summary = envelope["summary"]
        assert (summary["hits"], summary["misses"], summary["evictions"]) == (2, 3, 1)
        events = envelope["events"]
        # t3's hit must not reorder FIFO insertion order...
        assert events[2]["result"] == "hit"
        # ...so t4 evicts A (oldest insert) where LRU evicted B.
        assert events[3]["evicted"]["block"] == 0
        assert events[3]["policy_meta"] == {"policy": "FIFO",
                                            "victim_selection": "fifo_oldest"}
        assert events[3]["explanation"] == (
            "Miss: block 4 loaded into set 0 way 0, evicting block 0 (FIFO).")
        # ...and t5 is a hit under FIFO.
        assert events[4]["result"] == "hit"
        state = envelope["state"]["sets"][0]
        assert state[1]["insert_order_rank"] == 1  # B inserted t2 (oldest)
        assert state[0]["insert_order_rank"] == 2  # C inserted t4
        assert state[0]["last_used_rank"] is None

    def test_pinned_random_seed_12345(self, tmp_path):
        job = {"config": dict(CONFIG_SET_ASSOCIATIVE, policy="RANDOM",
                              seed=12345),
               "trace": {"name": "random-demo", "addresses": [0, 4, 0, 8, 4]}}
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        # D-15: draw 1 = 3992670690 (%2 = 0) -> t4 evicts way 0 (block A).
        events = envelope["events"]
        assert events[2]["result"] == "hit"
        assert events[3]["evicted"]["block"] == 0
        assert events[3]["policy_meta"] == {"policy": "RANDOM",
                                            "victim_selection": "random",
                                            "seed": 12345}
        assert events[3]["explanation"] == (
            "Miss: block 4 loaded into set 0 way 0, evicting block 0 (Random).")
        assert events[4]["result"] == "hit"
        assert envelope["summary"]["replacement_meta"] == {
            "policy": "RANDOM", "seed": 12345, "rng_draws": 1}
        assert envelope["summary"]["hits"] == 2

    def test_summary_validates_against_schema(self, tmp_path):
        proc = self._run_job(E1_JOB, tmp_path)
        summary = json.loads(proc.stdout)["summary"]
        errors = list(_validator("summary.schema.json").iter_errors(summary))
        assert not errors, [e.message for e in errors]

    def test_trace_sha256_matches_hashlib(self, tmp_path):
        proc = self._run_job(E1_JOB, tmp_path)
        summary = json.loads(proc.stdout)["summary"]
        expected = hashlib.sha256(b"addresses:16,16,16,16,16").hexdigest()
        assert summary["trace_sha256"] == expected

    def test_random_determinism_byte_identical(self, tmp_path):
        job = {"config": dict(CONFIG_SET_ASSOCIATIVE, policy="RANDOM", seed=7),
               "trace": {"name": "e5-det", "addresses": [0, 4, 8, 12, 16]}}
        out1 = self._run_job(job, tmp_path).stdout
        out2 = self._run_job(job, tmp_path).stdout
        assert out1 != "" and out1 == out2
        summary = json.loads(out1)["summary"]
        assert summary["hits"] == 0 and summary["evictions"] == 3
        assert summary["replacement_meta"]["rng_draws"] == 3

    def test_amat_values_for_e3(self, tmp_path):
        expectations = {"LRU": 17.0, "FIFO": 13.0, "RANDOM": 13.0}
        for policy, expected in expectations.items():
            cfg = dict(CONFIG_SET_ASSOCIATIVE, policy=policy)
            if policy == "RANDOM":
                cfg["seed"] = 12345
            job = {"config": cfg,
                   "trace": {"name": "amat", "addresses": [0, 4, 0, 8, 4]}}
            proc = self._run_job(job, tmp_path)
            assert proc.returncode == 0, proc.stderr
            summary = json.loads(proc.stdout)["summary"]
            assert summary["amat"] == {"hit_time": 1.0, "miss_penalty": 20.0,
                                       "value": expected, "unit": "cycles"}, policy

    def test_amat_omitted_without_timing(self, tmp_path):
        # AC-P4.4: no timing inputs -> the amat key is absent entirely,
        # never emitted as null, and the summary still schema-validates.
        cfg = {k: v for k, v in CONFIG_DIRECT.items()
               if k not in ("hit_time", "miss_penalty")}
        job = {"config": cfg, "trace": {"name": "no-timing", "addresses": [16]}}
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        summary = json.loads(proc.stdout)["summary"]
        assert "amat" not in summary
        errors = list(_validator("summary.schema.json").iter_errors(summary))
        assert not errors, [e.message for e in errors]

    def test_empty_trace_amat_degenerates_to_hit_time(self, tmp_path):
        job = dict(E1_JOB, trace={"name": "empty", "addresses": []})
        proc = self._run_job(job, tmp_path)
        assert proc.returncode == 0, proc.stderr
        summary = json.loads(proc.stdout)["summary"]
        assert summary["hit_rate"] is None and summary["miss_rate"] is None
        assert summary["amat"]["value"] == 1.0  # D-19: modeled miss rate 0

    def test_replacement_meta_omitted_for_direct(self, tmp_path):
        proc = self._run_job(E1_JOB, tmp_path)
        summary = json.loads(proc.stdout)["summary"]
        assert "replacement_meta" not in summary


@pytest.mark.skipif(not ENGINE.exists(), reason=ENGINE_SKIP)
class TestGeometryMode:
    """Phase 2: --mode geometry (AC-P2.2, AC-P2.3, AC-P2.4)."""

    def test_valid_config_returns_exact_geometry(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(CONFIG_SET_ASSOCIATIVE), encoding="utf-8")
        proc = run_engine("--mode", "geometry", "--in", str(cfg))
        assert proc.returncode == 0, proc.stderr
        envelope = json.loads(proc.stdout)
        assert envelope["ok"] is True
        assert envelope["geometry"] == GEOMETRY_DEMO
        errors = list(_validator("geometry.schema.json").iter_errors(envelope["geometry"]))
        assert not errors, [e.message for e in errors]

    def test_direct_config_geometry(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(CONFIG_DIRECT), encoding="utf-8")
        proc = run_engine("--mode", "geometry", "--in", str(cfg))
        assert proc.returncode == 0, proc.stderr
        geometry = json.loads(proc.stdout)["geometry"]
        assert geometry["sets"] == geometry["lines"] == 4
        assert geometry["associativity"] is None
        assert geometry["offset_bits"] == 1
        assert geometry["index_bits"] == 2
        assert geometry["tag_bits"] == 5

    def test_config_from_stdin(self):
        proc = run_engine("--mode", "geometry", stdin_text=json.dumps(CONFIG_SET_ASSOCIATIVE))
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["geometry"]["sets"] == 2

    def test_invalid_config_exit_3_with_details(self, tmp_path):
        bad = dict(CONFIG_SET_ASSOCIATIVE, block_size_bytes=6)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(bad), encoding="utf-8")
        proc = run_engine("--mode", "geometry", "--in", str(cfg))
        assert proc.returncode == 3
        envelope = json.loads(proc.stdout)
        assert envelope["ok"] is False
        assert envelope["error"]["code"] == "E_CONFIG_INVALID"
        detail = envelope["error"]["details"][0]
        assert detail["field"] == "block_size_bytes"
        assert detail["received"] == 6
        assert "power of two" in detail["problem"]

    def test_all_problems_collected_not_just_first(self, tmp_path):
        bad = {"capacity_bytes": 6, "block_size_bytes": 6, "address_width_bits": 3}
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(bad), encoding="utf-8")
        proc = run_engine("--mode", "geometry", "--in", str(cfg))
        assert proc.returncode == 3
        fields = {d["field"] for d in json.loads(proc.stdout)["error"]["details"]}
        assert {"capacity_bytes", "block_size_bytes", "address_width_bits",
                "organization"} <= fields

    def test_malformed_json_is_job_invalid(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("{oops", encoding="utf-8")
        proc = run_engine("--mode", "geometry", "--in", str(cfg))
        assert proc.returncode == 3
        assert json.loads(proc.stdout)["error"]["code"] == "E_JOB_INVALID"

    def test_tag_bits_negative_rejected_with_conflict_named(self, tmp_path):
        # offset_bits 7 > width 4: no tag bits remain (AC-P2.4).
        bad = {"capacity_bytes": 128, "block_size_bytes": 128,
               "organization": "direct", "address_width_bits": 4}
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(bad), encoding="utf-8")
        proc = run_engine("--mode", "geometry", "--in", str(cfg))
        assert proc.returncode == 3
        error = json.loads(proc.stdout)["error"]
        assert error["code"] == "E_CONFIG_INVALID"
        # The envelope message is a summary; the conflict-naming text is the
        # detail's problem string (architecture.md 5.3).
        assert "offset_bits" in error["details"][0]["problem"]
        assert "tag" in error["details"][0]["problem"]
        assert error["details"][0]["received"] == 4

    def test_inapplicable_fields_rejected(self, tmp_path):
        # D-17: non-null associativity with direct, and non-null seed with
        # LRU, are rejected rather than silently ignored.
        cases = [
            dict(CONFIG_DIRECT, associativity=2),
            dict(CONFIG_SET_ASSOCIATIVE, seed=7),
        ]
        for bad in cases:
            cfg = tmp_path / "config.json"
            cfg.write_text(json.dumps(bad), encoding="utf-8")
            proc = run_engine("--mode", "geometry", "--in", str(cfg))
            assert proc.returncode == 3, bad
            envelope = json.loads(proc.stdout)
            assert envelope["error"]["code"] == "E_CONFIG_INVALID", bad


# --- Canonical schema validation (AC-P4) -----------------------------------

# sha256 of the empty string, used as a realistic 64-hex placeholder in
# documentation fixtures (these are examples, not recorded runs).
SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

CONFIG_DIRECT = {
    "capacity_bytes": 8,
    "block_size_bytes": 2,
    "organization": "direct",
    "address_width_bits": 8,
    "hit_time": 1.0,
    "miss_penalty": 20.0,
}

CONFIG_SET_ASSOCIATIVE = {
    "capacity_bytes": 8,
    "block_size_bytes": 2,
    "organization": "set_associative",
    "associativity": 2,
    "address_width_bits": 8,
    "policy": "LRU",
    "seed": None,
    "hit_time": 1.0,
    "miss_penalty": 20.0,
}

CONFIG_FULLY_ASSOCIATIVE = {
    "capacity_bytes": 8,
    "block_size_bytes": 2,
    "organization": "fully_associative",
    "address_width_bits": 8,
    "policy": "RANDOM",
    "seed": 12345,
}

TRACE_DEMO = {"name": "lru-vs-fifo-demo", "addresses": [0, 4, 0, 8, 4]}

JOB_DEMO = {
    "config": CONFIG_SET_ASSOCIATIVE,
    "trace": TRACE_DEMO,
    "options": {"include_state_after_each": False},
}

GEOMETRY_DEMO = {
    "capacity_bytes": 8,
    "block_size_bytes": 2,
    "organization": "set_associative",
    "associativity": 2,
    "address_width_bits": 8,
    "lines": 4,
    "sets": 2,
    "offset_bits": 1,
    "index_bits": 1,
    "tag_bits": 6,
    "index_field_present": True,
    "max_address": 255,
}

EVENT_DEMO = {
    "n": 4,
    "address": 8,
    "block": 4,
    "tag": 2,
    "index": 0,
    "offset": 0,
    "set": 0,
    "way": 0,
    "result": "miss",
    "loaded": True,
    "evicted": {"block": 0, "tag": 0, "way": 0},
    "policy_meta": {"policy": "FIFO", "victim_selection": "fifo_oldest"},
    "explanation": "Miss: block 4 loaded into set 0 way 0, evicting block 0 (FIFO).",
}

SUMMARY_DEMO = {
    "accesses": 5,
    "hits": 2,
    "misses": 3,
    "evictions": 1,
    "hit_rate": 0.4,
    "miss_rate": 0.6,
    "amat": {"hit_time": 1.0, "miss_penalty": 20.0, "value": 13.0, "unit": "cycles"},
    "replacement_meta": {"policy": "FIFO"},
    "trace_sha256": SHA,
}

STATE_DEMO = {
    "sets": [
        [
            {"way": 0, "valid": True, "tag": 2, "block": 4,
             "last_used_rank": None, "insert_order_rank": 2},
            {"way": 1, "valid": True, "tag": 1, "block": 2,
             "last_used_rank": None, "insert_order_rank": 1},
        ]
    ],
    "snapshots": None,
}


# --- Phase 3 simulate jobs (built on the schema fixtures above) ------------

E1_JOB = {
    "config": CONFIG_DIRECT,
    "trace": {"name": "e1-repeat", "addresses": [16, 16, 16, 16, 16]},
}

E3_JOB = {
    "config": CONFIG_SET_ASSOCIATIVE,
    "trace": {"name": "lru-vs-fifo-demo", "addresses": [0, 4, 0, 8, 4]},
}


def _summary(hits, misses, evictions, hit_rate, amat_value, meta):
    return {
        "accesses": 5,
        "hits": hits,
        "misses": misses,
        "evictions": evictions,
        "hit_rate": hit_rate,
        "miss_rate": 1.0 - hit_rate,
        "amat": {"hit_time": 1.0, "miss_penalty": 20.0,
                 "value": amat_value, "unit": "cycles"},
        "replacement_meta": meta,
        "trace_sha256": SHA,
    }


EXPERIMENT_DEMO = {
    "experiment_id": "exp-20261024-193000-policy",
    "mode": "policy_comparison",
    "created_utc": "2026-10-24T19:30:00Z",
    "engine_version": "0.1.0",
    "trace": {"name": "lru-vs-fifo-demo", "sha256": SHA, "addresses": [0, 4, 0, 8, 4]},
    "fixed": {
        "capacity_bytes": 8,
        "block_size_bytes": 2,
        "organization": "set_associative",
        "associativity": 2,
        "address_width_bits": 8,
    },
    "amat_assumptions": {"hit_time": 1.0, "miss_penalty": 20.0, "unit": "cycles"},
    "runs": [
        {"run_id": 1, "config": CONFIG_SET_ASSOCIATIVE, "policy": "LRU",
         "seed": None,
         "summary": _summary(1, 4, 2, 0.2, 17.0, {"policy": "LRU"})},
        {"run_id": 2, "config": dict(CONFIG_SET_ASSOCIATIVE, policy="FIFO"),
         "policy": "FIFO", "seed": None,
         "summary": _summary(2, 3, 1, 0.4, 13.0, {"policy": "FIFO"})},
        # RANDOM run: the exact deterministic outcome for seed 12345
        # (architecture.md §13 E5): draw 1 = 3992670690 (%2 = 0) → t4 evicts
        # way 0 (block A); t5 hits. 2 hits / 3 misses / 1 eviction /
        # rng_draws 1 / AMAT 13.0. Phase 4 must reproduce this exactly.
        {"run_id": 3,
         "config": dict(CONFIG_SET_ASSOCIATIVE, policy="RANDOM", seed=12345),
         "policy": "RANDOM", "seed": 12345,
         "summary": _summary(2, 3, 1, 0.4, 13.0,
                             {"policy": "RANDOM", "seed": 12345, "rng_draws": 1})},
    ],
    "summary_text": (
        "LRU: 1 hit / 5 accesses (20.00%), 2 evictions. "
        "FIFO: 2 hits / 5 accesses (40.00%), 1 eviction. "
        "RANDOM (seed 12345): 2 hits / 5 accesses (40.00%), 1 eviction. "
        "Best hit rate: FIFO and RANDOM tie at 40.00% (LRU 20.00%)."
    ),
}

CASES = [
    ("config.schema.json", CONFIG_DIRECT),
    ("config.schema.json", CONFIG_SET_ASSOCIATIVE),
    ("config.schema.json", CONFIG_FULLY_ASSOCIATIVE),
    ("trace.schema.json", TRACE_DEMO),
    ("job.schema.json", JOB_DEMO),
    ("geometry.schema.json", GEOMETRY_DEMO),
    ("event.schema.json", EVENT_DEMO),
    ("summary.schema.json", SUMMARY_DEMO),
    ("state.schema.json", STATE_DEMO),
    ("experiment.schema.json", EXPERIMENT_DEMO),
]


def _validator(schema_name: str) -> Draft7Validator:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    store = {
        p.as_uri(): json.loads(p.read_text(encoding="utf-8"))
        for p in SCHEMAS.glob("*.schema.json")
    }
    resolver = RefResolver(base_uri=SCHEMAS.as_uri() + "/", referrer=schema,
                           store=store)
    return Draft7Validator(schema, resolver=resolver)


@pytest.mark.parametrize("schema_name,example", CASES,
                         ids=[f"{s}#{i}" for i, (s, _) in enumerate(CASES)])
def test_schema_example_validates(schema_name, example):
    errors = list(_validator(schema_name).iter_errors(example))
    assert not errors, "\n".join(sorted(e.message for e in errors))


def test_config_schema_rejects_unknown_organization():
    bad = dict(CONFIG_DIRECT, organization="associative")
    assert not _validator("config.schema.json").is_valid(bad)


def test_config_schema_rejects_missing_capacity():
    bad = {k: v for k, v in CONFIG_DIRECT.items() if k != "capacity_bytes"}
    assert not _validator("config.schema.json").is_valid(bad)


def test_config_schema_rejects_random_without_seed():
    # RANDOM requires an integer seed; "seed": null does not satisfy it.
    bad = dict(CONFIG_SET_ASSOCIATIVE, policy="RANDOM", seed=None)
    assert not _validator("config.schema.json").is_valid(bad)


def test_config_schema_rejects_associativity_outside_set_associative():
    # D-17: inapplicable fields must be null or absent.
    assert not _validator("config.schema.json").is_valid(dict(CONFIG_DIRECT, associativity=2))


def test_config_schema_rejects_seed_with_non_random_policy():
    # D-17: inapplicable fields must be null or absent.
    assert not _validator("config.schema.json").is_valid(dict(CONFIG_SET_ASSOCIATIVE, seed=7))
