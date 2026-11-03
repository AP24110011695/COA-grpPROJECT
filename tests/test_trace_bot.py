"""Phase 6: Bot 1 (trace_bot) unit tests (AC-P6.1..P6.5) plus one
real-engine integration test.

The geometry provider is a lookup-table stub over the *published* fixture
geometries (docs/architecture.md 13 / test_smoke) — no geometry logic is
reimplemented here; the integration test cross-checks the stub table
against the real engine.
"""

import json

import pytest

import test_smoke as ts
from bots import engine_client
from bots.trace_bot import generate

ENGINE = ts.ROOT / "build" / "cache_sim.exe"
ENGINE_SKIP = ts.ENGINE_SKIP

# --- Published geometries for the stub provider ----------------------------

DIRECT_W8_GEOMETRY = {
    "capacity_bytes": 8, "block_size_bytes": 2, "organization": "direct",
    "associativity": None, "address_width_bits": 8, "lines": 4, "sets": 4,
    "offset_bits": 1, "index_bits": 2, "tag_bits": 5,
    "index_field_present": True, "max_address": 255,
}

FULLY_W8_GEOMETRY = {
    "capacity_bytes": 8, "block_size_bytes": 2,
    "organization": "fully_associative", "associativity": None,
    "address_width_bits": 8, "lines": 4, "sets": 1, "offset_bits": 1,
    "index_bits": 0, "tag_bits": 7, "index_field_present": False,
    "max_address": 255,
}

SA_W16 = dict(ts.CONFIG_SET_ASSOCIATIVE, address_width_bits=16)
SA_W16_GEOMETRY = {
    "capacity_bytes": 8, "block_size_bytes": 2,
    "organization": "set_associative", "associativity": 2,
    "address_width_bits": 16, "lines": 4, "sets": 2, "offset_bits": 1,
    "index_bits": 1, "tag_bits": 14, "index_field_present": True,
    "max_address": 65535,
}


def _key(config):
    return json.dumps(config, sort_keys=True)


GEOMETRY_TABLE = {
    _key(ts.CONFIG_SET_ASSOCIATIVE): ts.GEOMETRY_DEMO,
    _key(ts.CONFIG_DIRECT): DIRECT_W8_GEOMETRY,
    _key(ts.CONFIG_FULLY_ASSOCIATIVE): FULLY_W8_GEOMETRY,
    _key(SA_W16): SA_W16_GEOMETRY,
}


def stub_geometry(config):
    try:
        return dict(GEOMETRY_TABLE[_key(config)])
    except KeyError:
        raise AssertionError(
            f"stub_geometry has no entry for config: {_key(config)}")


def failing_geometry(config):
    raise engine_client.EngineError(
        "E_CONFIG_INVALID", "configuration validation failed with 1 problem(s)",
        [{"field": "block_size_bytes",
          "problem": "must be an integer power of two between 1 and 128",
          "received": 6}])


def run(request):
    return generate(request, stub_geometry)


# --- Sequential / repeated (AC-P6.1) ---------------------------------------


class TestSequentialAndRepeated:
    def test_sequential_exact_addresses(self):
        response = run({
            "pattern": "sequential",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"start_address": 0, "count": 8, "stride_bytes": 4},
        })
        assert response["ok"] is True
        trace = response["trace"]
        assert trace["addresses"] == [0, 4, 8, 12, 16, 20, 24, 28]
        assert trace["name"] == "sequential-0-8-4"
        assert trace["pattern"] == "sequential"
        assert trace["params"] == {"start_address": 0, "count": 8,
                                   "stride_bytes": 4}
        assert response["geometry_used"] == ts.GEOMETRY_DEMO
        assert response["warnings"] == []

    def test_sequential_offset_start(self):
        response = run({
            "pattern": "sequential",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"start_address": 100, "count": 3, "stride_bytes": 7},
        })
        assert response["trace"]["addresses"] == [100, 107, 114]

    def test_repeated_exact_addresses(self):
        response = run({
            "pattern": "repeated",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"address": 16, "count": 5},
        })
        assert response["trace"]["addresses"] == [16, 16, 16, 16, 16]
        assert response["trace"]["name"] == "repeated-16-5"

    def test_zero_count_is_an_empty_trace(self):
        response = run({
            "pattern": "repeated",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"address": 16, "count": 0},
        })
        assert response["trace"]["addresses"] == []
        assert response["trace"]["name"] == "repeated-16-0"


# --- Conflict (AC-P6.1, AC-P6.5) -------------------------------------------


class TestConflictPattern:
    def test_default_blocks_in_one_set(self):
        # sets 2, block size 2: blocks 0,2,4,6 -> addresses 0,4,8,12.
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 4, "passes": 1, "target_set": 0,
                       "start_block": 0},
        })
        assert response["trace"]["addresses"] == [0, 4, 8, 12]
        assert response["warnings"] == []

    def test_target_set_three_with_rounding(self):
        # AC-P6.1: sets 4, target_set 3, start_block 0 -> blocks 3,7,11,15
        # -> addresses 6,14,22,30 (block size 2).
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_DIRECT,
            "params": {"distinct_blocks": 4, "passes": 1, "target_set": 3,
                       "start_block": 0},
        })
        assert response["trace"]["addresses"] == [6, 14, 22, 30]
        assert response["trace"]["name"] == "conflict-4b-set3-p1"

    def test_start_block_rounds_up_to_requested_set(self):
        # sets 2, target_set 0, start_block 1 -> base 2 -> blocks 2,4.
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 2, "passes": 1, "target_set": 0,
                       "start_block": 1},
        })
        assert response["trace"]["addresses"] == [4, 8]

    def test_passes_repeat_the_sequence(self):
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 2, "passes": 3, "target_set": 0,
                       "start_block": 0},
        })
        assert response["trace"]["addresses"] == [0, 4, 0, 4, 0, 4]
        assert response["trace"]["name"] == "conflict-2b-set0-p3"

    def test_target_set_out_of_range_rejected(self):
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_DIRECT,  # sets 4
            "params": {"distinct_blocks": 2, "passes": 1, "target_set": 4,
                       "start_block": 0},
        })
        assert response["ok"] is False
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert "[0, 4)" in response["error"]["message"]


# --- Determinism (AC-P6.2) --------------------------------------------------


class TestDeterminism:
    def test_identical_requests_identical_responses(self):
        request = {
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 4, "passes": 2, "target_set": 1,
                       "start_block": 3},
        }
        first = run(request)
        second = run(request)
        assert first["ok"] is True
        assert first == second

    def test_manual_import_is_deterministic(self):
        request = {
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "0x10 # a\n16"},
        }
        assert run(request) == run(request)


# --- Width and limit rejections (AC-P6.3) -----------------------------------


class TestWidthAndLimitRejections:
    def test_sequential_over_max_rejected(self):
        response = run({
            "pattern": "sequential",
            "config": ts.CONFIG_SET_ASSOCIATIVE,  # max_address 255
            "params": {"start_address": 250, "count": 3, "stride_bytes": 4},
        })
        assert response["ok"] is False
        assert response["error"]["code"] == "E_TRACE_INVALID"
        assert "255" in response["error"]["message"]

    def test_repeated_over_max_rejected(self):
        response = run({
            "pattern": "repeated",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"address": 300, "count": 2},
        })
        assert response["error"]["code"] == "E_TRACE_INVALID"
        assert "255" in response["error"]["message"]

    def test_conflict_over_max_rejected(self):
        # sets 2: start_block 128 -> base 128 -> address 256 > 255.
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 2, "passes": 1, "target_set": 0,
                       "start_block": 128},
        })
        assert response["error"]["code"] == "E_TRACE_INVALID"
        assert "256" in response["error"]["message"]

    def test_conflict_base_congruence_exact_sequence(self):
        # Audit-2 (§6): independently calculated exact sequence. Sets 2:
        # base = start_block + ((target_set - start_block) mod sets)
        # = 7 + ((0 - 7) mod 2) = 8 (first block >= 7 mapping to set 0);
        # blocks 8, 10; block_size 2.
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 2, "passes": 2, "target_set": 0,
                       "start_block": 7},
        })
        assert response["ok"] is True
        assert response["trace"]["addresses"] == [16, 20, 16, 20]
        assert response["warnings"] == []

    def test_sequential_exact_sequence(self):
        response = run({
            "pattern": "sequential",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"start_address": 100, "count": 4, "stride_bytes": 7},
        })
        assert response["ok"] is True
        assert response["trace"]["addresses"] == [100, 107, 114, 121]
        assert response["trace"]["name"] == "sequential-100-4-7"

    def test_sequential_count_over_limit(self):
        response = run({
            "pattern": "sequential",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"start_address": 0, "count": 100001,
                       "stride_bytes": 1},
        })
        assert response["error"]["code"] == "E_LIMIT"
        assert "100000" in response["error"]["message"]

    def test_conflict_total_over_limit(self):
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"distinct_blocks": 100001, "passes": 1,
                       "target_set": 0, "start_block": 0},
        })
        assert response["error"]["code"] == "E_LIMIT"

    def test_manual_over_limit(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "\n".join(["1"] * 100001)},
        })
        assert response["error"]["code"] == "E_LIMIT"


# --- Manual import (AC-P6.4) -------------------------------------------------


class TestManualImport:
    def test_e3_trace_text(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "0 # A\n4 # B\n0\n8 # C\n4"},
        })
        assert response["trace"]["addresses"] == [0, 4, 0, 8, 4]
        assert response["trace"]["name"] == "manual-import"

    def test_hex_upper_and_lower(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "0x10\n0XFF\n16   # trailing comment"},
        })
        assert response["trace"]["addresses"] == [16, 255, 16]

    def test_blank_and_comment_only_is_empty(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "# nothing here\n\n   \n"},
        })
        assert response["trace"]["addresses"] == []

    def test_bad_token_reports_line_number(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "4\nxyz\n8"},
        })
        assert response["ok"] is False
        assert response["error"]["code"] == "E_TRACE_INVALID"
        detail = response["error"]["details"][0]
        assert detail["field"] == "line 2"
        assert detail["received"] == "xyz"

    def test_all_problem_lines_collected(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "zzz\n4\nqqq"},
        })
        assert len(response["error"]["details"]) == 2

    def test_problem_lines_truncated_like_the_engine(self):
        # Regression (2026-10-27 audit): a pathological all-bad paste must
        # not build an unbounded issue list — details cap at 10 lines plus
        # one truncation summary; the message keeps the true total.
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "\n".join(["zzz"] * 15)},
        })
        assert response["ok"] is False
        assert response["error"]["code"] == "E_TRACE_INVALID"
        assert "15 problem line(s)" in response["error"]["message"]
        assert len(response["error"]["details"]) == 11
        assert response["error"]["details"][-1]["problem"] == \
            "further problem lines truncated (5 more)"

    def test_line_over_max_rejected(self):
        response = run({
            "pattern": "manual",
            "config": ts.CONFIG_SET_ASSOCIATIVE,
            "params": {"text": "4\n300"},
        })
        assert response["error"]["code"] == "E_TRACE_INVALID"
        assert "255" in response["error"]["details"][0]["problem"]


# --- Fully-associative conflict (AC-P6.5) ------------------------------------


class TestFullyAssociativeConflict:
    def test_single_set_with_ignored_target(self):
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_FULLY_ASSOCIATIVE,
            "params": {"distinct_blocks": 3, "passes": 1, "target_set": 5,
                       "start_block": 2},
        })
        assert response["ok"] is True  # no crash
        # sets 1: base = start_block = 2 -> blocks 2,3,4 -> addresses 4,6,8.
        assert response["trace"]["addresses"] == [4, 6, 8]
        assert len(response["warnings"]) == 1
        assert "target_set 5 ignored" in response["warnings"][0]

    def test_single_set_no_warning_when_target_zero(self):
        response = run({
            "pattern": "conflict",
            "config": ts.CONFIG_FULLY_ASSOCIATIVE,
            "params": {"distinct_blocks": 2, "passes": 1, "target_set": 0,
                       "start_block": 0},
        })
        assert response["ok"] is True
        assert response["warnings"] == []
        assert response["trace"]["addresses"] == [0, 2]


# --- Error pass-through and request shape ------------------------------------


class TestErrorsAndShape:
    def test_engine_error_passthrough(self):
        response = generate(
            {"pattern": "sequential",
             "config": ts.CONFIG_SET_ASSOCIATIVE,
             "params": {"start_address": 0, "count": 4, "stride_bytes": 1}},
            failing_geometry)
        assert response["ok"] is False
        assert response["error"]["code"] == "E_CONFIG_INVALID"
        assert response["error"]["details"][0]["field"] == "block_size_bytes"

    def test_unknown_pattern(self):
        response = run({"pattern": "wavefront",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {}})
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert "must be one of" in response["error"]["message"]

    def test_missing_members(self):
        response = run({"pattern": "repeated"})
        assert response["error"]["code"] == "E_JOB_INVALID"
        fields = {d["field"] for d in response["error"]["details"]}
        assert {"config", "params"} <= fields

    def test_unknown_request_key(self):
        response = run({"pattern": "repeated",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {"address": 16, "count": 1},
                        "patter": "typo"})
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert response["error"]["details"][0]["field"] == "patter"

    def test_non_integer_param(self):
        response = run({"pattern": "repeated",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {"address": 16, "count": "8"}})
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert "params.count" in response["error"]["message"]

    def test_bool_param_rejected(self):
        response = run({"pattern": "repeated",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {"address": 16, "count": True}})
        assert response["error"]["code"] == "E_JOB_INVALID"

    def test_unknown_param_key(self):
        response = run({"pattern": "repeated",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {"address": 16, "count": 1,
                                   "addres": 16}})
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert response["error"]["details"][0]["field"] == "params.addres"

    def test_stride_zero_suggests_repeated(self):
        response = run({"pattern": "sequential",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {"start_address": 0, "count": 4,
                                   "stride_bytes": 0}})
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert "repeated" in response["error"]["message"]

    def test_missing_param_key(self):
        response = run({"pattern": "repeated",
                        "config": ts.CONFIG_SET_ASSOCIATIVE,
                        "params": {"address": 16}})
        assert response["error"]["code"] == "E_JOB_INVALID"
        assert "params.count is required" in response["error"]["message"]

    def test_config_must_be_object(self):
        response = run({"pattern": "repeated", "config": "nope",
                        "params": {"address": 16, "count": 1}})
        assert response["error"]["code"] == "E_JOB_INVALID"


# --- Integration with the real engine (Phase 6 task 6) -----------------------


@pytest.mark.skipif(not ENGINE.exists(), reason=ENGINE_SKIP)
class TestRealEngineIntegration:
    def test_fetch_geometry_matches_published_fixture(self):
        geometry = engine_client.fetch_geometry(ts.CONFIG_SET_ASSOCIATIVE)
        assert geometry == ts.GEOMETRY_DEMO

    def test_generate_with_real_engine(self):
        response = generate(
            {"pattern": "conflict",
             "config": ts.CONFIG_SET_ASSOCIATIVE,
             "params": {"distinct_blocks": 4, "passes": 1, "target_set": 0,
                        "start_block": 0}},
            engine_client.fetch_geometry)
        assert response["ok"] is True
        assert response["trace"]["addresses"] == [0, 4, 8, 12]
        assert response["geometry_used"] == ts.GEOMETRY_DEMO

    def test_generate_rejects_bad_config_via_engine(self):
        response = generate(
            {"pattern": "sequential",
             "config": dict(ts.CONFIG_SET_ASSOCIATIVE, block_size_bytes=6),
             "params": {"start_address": 0, "count": 4, "stride_bytes": 1}},
            engine_client.fetch_geometry)
        assert response["ok"] is False
        assert response["error"]["code"] == "E_CONFIG_INVALID"
        assert response["error"]["details"][0]["field"] == "block_size_bytes"
