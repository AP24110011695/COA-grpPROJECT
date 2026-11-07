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
