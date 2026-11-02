#pragma once

// Simulation of read-only address traces
// (architecture.md 6.4-6.7, 8). All three replacement policies (LRU, FIFO,
// seeded RANDOM) and direct-mapped no-policy operation.

#include <cstdint>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "cache.hpp"
#include "config.hpp"
#include "geometry.hpp"

namespace engine {

struct Trace {
  std::string name;
  std::vector<std::uint64_t> addresses;
};

struct TraceValidation {
  bool ok = false;
  std::size_t limit_problems = 0;  // > 0 routes the envelope to E_LIMIT
  std::vector<ValidationIssue> issues;
  Trace trace;  // meaningful only when ok
};

// Validates the trace object: name, address array (each within
// [0, max_address]), and the 100,000-address limit. Address problems are
// collected up to a cap of 10 details plus one truncation note — a
// 100,000-entry array cannot report every bad element.
TraceValidation validate_trace(const nlohmann::json& trace,
                               std::uint64_t max_address);

struct SimulateEvent {
  std::uint64_t n = 0;
  std::uint64_t address = 0;
  std::uint64_t block = 0;
  std::uint64_t tag = 0;
  bool has_index = true;  // false for fully_associative (index reported null)
  std::uint64_t index = 0;
  std::uint64_t offset = 0;
  std::uint64_t set = 0;
  std::uint64_t way = 0;
  bool hit = false;
  bool loaded = false;
  bool evicted_valid = false;  // evicted_* fields present only when true
  std::uint64_t evicted_block = 0;
  std::uint64_t evicted_tag = 0;
  std::uint64_t evicted_way = 0;
  std::string explanation;
};

struct SimulateResult {
  std::vector<SimulateEvent> events;
  SimulateCounts counts;
  std::uint64_t rng_draws = 0;  // consumed only by RANDOM valid-line evictions
  bool snapshots_requested = false;  // mirrors options.include_state_after_each
  CacheState final_state;
  nlohmann::json snapshots = nlohmann::json::array();  // empty unless requested
};

// Simulates the trace and asserts the architecture.md 9 invariants.
// Returns false on an internal invariant violation — an engine bug, which
// the caller reports as E_INTERNAL.
bool simulate(const Config& config, const Geometry& geometry,
              const std::vector<std::uint64_t>& addresses,
              bool include_state_after_each, SimulateResult* out);

nlohmann::json event_to_json(const SimulateEvent& event, const Config& config);
nlohmann::json state_to_json(const CacheState& state,
                             const nlohmann::json& snapshots, Policy policy,
                             bool snapshots_requested);

}  // namespace engine
