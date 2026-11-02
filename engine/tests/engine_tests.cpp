// Engine test runner — assert-based, no external framework (decision D-9).
// Phase 2 sections: configuration validation (every prd.md 5 rule) and
// geometry derivation (architecture.md 7), with exact hand-written
// expectations. Worked examples E1-E6 event-level tests land in Phase 5
// (architecture.md 13).

#include <chrono>
#include <cstdio>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "config.hpp"
#include "geometry.hpp"
#include "simulator.hpp"
#include "stats.hpp"
#include "version.hpp"

using json = nlohmann::json;

namespace {

int g_checks = 0;
int g_failures = 0;
const char* g_section = nullptr;
int g_section_checks = 0;
int g_section_failures = 0;

void section(const char* name) {
  if (g_section != nullptr) {
    // Per-section summary (AC-P5.4).
    std::printf("[done] %s: %d checks, %d failures\n", g_section,
                g_checks - g_section_checks, g_failures - g_section_failures);
  }
  g_section = name;
  g_section_checks = g_checks;
  g_section_failures = g_failures;
  std::printf("[section] %s\n", name);
}

void check_true(bool cond, const std::string& what, int line) {
  ++g_checks;
  if (!cond) {
    ++g_failures;
    std::printf("FAIL %s:%d  %s\n", g_section, line, what.c_str());
  }
}

void check_eq_str(const std::string& expected, const std::string& actual,
                  const std::string& what, int line) {
  ++g_checks;
  if (expected != actual) {
    ++g_failures;
    std::printf("FAIL %s:%d  %s\n  expected: %s\n  actual:   %s\n", g_section,
                line, what.c_str(), expected.c_str(), actual.c_str());
  }
}

void check_eq_ll(long long expected, long long actual,
                 const std::string& what, int line) {
  ++g_checks;
  if (expected != actual) {
    ++g_failures;
    // MinGW's msvcrt printf lacks %lld; format via std::to_string.
    std::printf("FAIL %s:%d  %s\n  expected: %s\n  actual:   %s\n", g_section,
                line, what.c_str(), std::to_string(expected).c_str(),
                std::to_string(actual).c_str());
  }
}

#define CHECK_TRUE(cond) check_true((cond), #cond, __LINE__)
#define CHECK_EQ_LL(expected, actual) \
  check_eq_ll((long long)(expected), (long long)(actual), #actual, __LINE__)
#define CHECK_EQ_STR(expected, actual) \
  check_eq_str(std::string(expected), std::string(actual), #actual, __LINE__)

// Valid E3-style set-associative configuration (architecture.md 13 E3).
json base_config() {
  return json{
      {"capacity_bytes", 8},
      {"block_size_bytes", 2},
      {"organization", "set_associative"},
      {"associativity", 2},
      {"address_width_bits", 8},
      {"policy", "LRU"},
      {"hit_time", 1.0},
      {"miss_penalty", 20.0}};
}

struct Validated {
  bool ok = false;
  std::vector<engine::ValidationIssue> issues;
  engine::Config config;
  engine::Geometry geometry;
};

Validated validate_config(const json& j) {
  Validated r;
  r.ok = engine::parse_and_validate_config(j, &r.config, &r.issues);
  if (r.issues.empty()) {
    r.ok = r.ok && engine::derive_geometry(r.config, &r.geometry, &r.issues);
  }
  return r;
}

const engine::ValidationIssue* find_issue(
    const std::vector<engine::ValidationIssue>& issues,
    const std::string& field) {
  for (const auto& issue : issues) {
    if (issue.field == field) return &issue;
  }
  return nullptr;
}

// Validates a config JSON, derives geometry, and simulates the trace.
engine::SimulateResult run_sim(const json& config_json,
                               const std::vector<std::uint64_t>& addresses,
                               bool snapshots = false) {
  engine::Config cfg;
  std::vector<engine::ValidationIssue> iss;
  if (!engine::parse_and_validate_config(config_json, &cfg, &iss)) {
    check_true(false, "config unexpectedly invalid", __LINE__);
    return engine::SimulateResult();
  }
  engine::Geometry geo;
  if (!engine::derive_geometry(cfg, &geo, &iss)) {
    check_true(false, "geometry unexpectedly invalid", __LINE__);
    return engine::SimulateResult();
  }
  engine::SimulateResult r;
  check_true(engine::simulate(cfg, geo, addresses, snapshots, &r),
             "simulate invariants", __LINE__);
  return r;
}

json state_json(const engine::Config& cfg, const engine::SimulateResult& r) {
  // serialize with whatever the run actually requested, so snapshot
  // assertions see the captured array and non-snapshot runs see null
  return engine::state_to_json(r.final_state, r.snapshots,
                               engine::policy_from_config(cfg),
                               r.snapshots_requested);
}

json state_json(const json& config_json, const engine::SimulateResult& r) {
  engine::Config cfg;
  std::vector<engine::ValidationIssue> iss;
  if (!engine::parse_and_validate_config(config_json, &cfg, &iss)) {
    check_true(false, "config unexpectedly invalid in state_json", __LINE__);
    return json();
  }
  return state_json(cfg, r);
}

// Serializes everything a simulate envelope carries beyond echo/geometry —
// used for the byte-identical determinism comparisons.
std::string result_dump(const engine::Config& cfg,
                        const engine::SimulateResult& r,
                        const std::vector<std::uint64_t>& addresses) {
  json env;
  json events = json::array();
  for (const auto& e : r.events) {
    events.push_back(engine::event_to_json(e, cfg));
  }
  env["events"] = events;
  env["summary"] = engine::build_summary(cfg, r.counts, r.rng_draws, addresses);
  env["state"] = state_json(cfg, r);
  return env.dump();
}

}  // namespace

int main() {
  section("version");
  CHECK_EQ_STR("cache_sim", engine::kName);
  CHECK_EQ_STR("0.1.0", engine::kVersion);

  section("geometry_valid");
  {
    // E1/E2 geometry: direct, 8 B capacity, 2 B blocks, width 8.
    json c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    Validated r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(4, r.geometry.lines);
    CHECK_EQ_LL(4, r.geometry.sets);
    CHECK_EQ_LL(1, r.geometry.offset_bits);
    CHECK_EQ_LL(2, r.geometry.index_bits);
    CHECK_EQ_LL(5, r.geometry.tag_bits);
    CHECK_EQ_LL(255, r.geometry.max_address);
    CHECK_TRUE(r.geometry.index_field_present);
    json gj = engine::geometry_to_json(r.geometry, r.config);
    CHECK_TRUE(gj["associativity"].is_null());

    // E3 geometry: set_associative, associativity 2 (architecture.md 6.3).
    r = validate_config(base_config());
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(4, r.geometry.lines);
    CHECK_EQ_LL(2, r.geometry.sets);
    CHECK_EQ_LL(1, r.geometry.offset_bits);
    CHECK_EQ_LL(1, r.geometry.index_bits);
    CHECK_EQ_LL(6, r.geometry.tag_bits);
    CHECK_EQ_LL(255, r.geometry.max_address);
    CHECK_TRUE(r.geometry.index_field_present);

    // E4 geometry: fully_associative — one set, zero index bits.
    c = base_config();
    c["organization"] = "fully_associative";
    c.erase("associativity");
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(4, r.geometry.lines);
    CHECK_EQ_LL(1, r.geometry.sets);
    CHECK_EQ_LL(1, r.geometry.offset_bits);
    CHECK_EQ_LL(0, r.geometry.index_bits);
    CHECK_EQ_LL(7, r.geometry.tag_bits);
    CHECK_EQ_LL(255, r.geometry.max_address);
    CHECK_TRUE(!r.geometry.index_field_present);

    // Boundary: block size 1 -> zero offset bits.
    c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    c["block_size_bytes"] = 1;
    c["capacity_bytes"] = 8;
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(0, r.geometry.offset_bits);
    CHECK_EQ_LL(8, r.geometry.lines);
    CHECK_EQ_LL(8, r.geometry.sets);
    CHECK_EQ_LL(3, r.geometry.index_bits);
    CHECK_EQ_LL(5, r.geometry.tag_bits);

    // Boundary: capacity == block size -> single line, single set.
    c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    c["capacity_bytes"] = 2;
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(1, r.geometry.lines);
    CHECK_EQ_LL(1, r.geometry.sets);
    CHECK_EQ_LL(0, r.geometry.index_bits);
    CHECK_EQ_LL(7, r.geometry.tag_bits);

    // Boundary: associativity == capacity / block size -> single set.
    c = base_config();
    c["associativity"] = 4;
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(1, r.geometry.sets);
    CHECK_EQ_LL(0, r.geometry.index_bits);
    CHECK_EQ_LL(7, r.geometry.tag_bits);
    CHECK_TRUE(r.geometry.index_field_present);

    // Boundary: minimum width 4.
    c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    c["address_width_bits"] = 4;
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(1, r.geometry.offset_bits);
    CHECK_EQ_LL(2, r.geometry.index_bits);
    CHECK_EQ_LL(1, r.geometry.tag_bits);
    CHECK_EQ_LL(15, r.geometry.max_address);

    // Boundary: maximum width 64 -> max_address = 2^64 - 1 without overflow.
    c = base_config();
    c["address_width_bits"] = 64;
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_TRUE(r.geometry.max_address == 0xFFFFFFFFFFFFFFFFULL);

    // Boundary: maximum capacity 2^20.
    c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    c["capacity_bytes"] = 1048576;
    c["block_size_bytes"] = 1;
    c["address_width_bits"] = 32;
    r = validate_config(c);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(1048576, r.geometry.lines);
    CHECK_EQ_LL(1048576, r.geometry.sets);
    CHECK_EQ_LL(20, r.geometry.index_bits);
    CHECK_EQ_LL(0, r.geometry.offset_bits);
    CHECK_EQ_LL(12, r.geometry.tag_bits);
    CHECK_EQ_LL(4294967295LL, r.geometry.max_address);

    // Regression: text-parsed positive integers are unsigned in nlohmann —
    // validation must accept them (this exact case failed before the fix).
    const json parsed_text = json::parse(
        "{\"capacity_bytes\":8,\"block_size_bytes\":2,"
        "\"organization\":\"set_associative\",\"associativity\":2,"
        "\"address_width_bits\":8,\"policy\":\"LRU\"}");
    CHECK_TRUE(parsed_text.is_object());
    r = validate_config(parsed_text);
    CHECK_TRUE(r.ok);
    CHECK_EQ_LL(2, r.geometry.sets);
    CHECK_EQ_LL(6, r.geometry.tag_bits);

    // Valid: seed null with LRU; RANDOM with seed 0 and with the uint32 max;
    // timing assumptions absent.
    c = base_config();
    c["seed"] = nullptr;
    CHECK_TRUE(validate_config(c).ok);
    c["policy"] = "RANDOM";
    c["seed"] = 0;
    CHECK_TRUE(validate_config(c).ok);
    c["seed"] = 4294967295ULL;
    CHECK_TRUE(validate_config(c).ok);
    c.erase("hit_time");
    c.erase("miss_penalty");
    CHECK_TRUE(validate_config(c).ok);
  }

  section("config_invalid");
  {
    // Every prd.md 5 rule violated once, asserting field, problem, received.

    // capacity_bytes --------------------------------------------------
    Validated r = validate_config(base_config());
    json c = base_config();
    c["capacity_bytes"] = 6;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be an integer power of two between 1 and 1048576",
                 find_issue(r.issues, "capacity_bytes")->problem);
    CHECK_EQ_STR("6", find_issue(r.issues, "capacity_bytes")->received.dump());

    c["capacity_bytes"] = 0;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "capacity_bytes") != nullptr);

    c["capacity_bytes"] = 2097152;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must not exceed 1048576 (2^20)",
                 find_issue(r.issues, "capacity_bytes")->problem);

    c["capacity_bytes"] = 8.0;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be an integer power of two between 1 and 1048576",
                 find_issue(r.issues, "capacity_bytes")->problem);

    c["capacity_bytes"] = "8";
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "capacity_bytes") != nullptr);

    c = base_config();
    c.erase("capacity_bytes");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is required",
                 find_issue(r.issues, "capacity_bytes")->problem);
    CHECK_EQ_STR("null", find_issue(r.issues, "capacity_bytes")->received.dump());

    // block_size_bytes --------------------------------------------------
    c = base_config();
    c["block_size_bytes"] = 6;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be an integer power of two between 1 and 128",
                 find_issue(r.issues, "block_size_bytes")->problem);

    c["block_size_bytes"] = 256;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "block_size_bytes") != nullptr);

    c["block_size_bytes"] = 16;  // > capacity 8
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must not exceed capacity_bytes (= 8)",
                 find_issue(r.issues, "block_size_bytes")->problem);

    // organization --------------------------------------------------------
    c = base_config();
    c["organization"] = "associative";
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be one of: direct, set_associative, fully_associative",
                 find_issue(r.issues, "organization")->problem);

    c["organization"] = 5;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "organization") != nullptr);

    c = base_config();
    c.erase("organization");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is required", find_issue(r.issues, "organization")->problem);

    // address_width_bits --------------------------------------------------
    c = base_config();
    c["address_width_bits"] = 3;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be an integer between 4 and 64",
                 find_issue(r.issues, "address_width_bits")->problem);

    c["address_width_bits"] = 65;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "address_width_bits") != nullptr);

    c["address_width_bits"] = true;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "address_width_bits") != nullptr);

    // associativity --------------------------------------------------------
    c = base_config();
    c.erase("associativity");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is required for set_associative",
                 find_issue(r.issues, "associativity")->problem);

    c["associativity"] = 1;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "associativity")->problem.find(
                   "use the direct organization") != std::string::npos);

    c["associativity"] = 3;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "associativity") != nullptr);

    c["associativity"] = 8;  // capacity/block = 4
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must not exceed capacity_bytes / block_size_bytes (= 4)",
                 find_issue(r.issues, "associativity")->problem);

    c["associativity"] = 2.0;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "associativity") != nullptr);

    c = base_config();
    c["organization"] = "direct";
    c.erase("policy");
    r = validate_config(c);  // associativity 2 with direct -> rejected (D-17)
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is only valid for set_associative; remove it or use null",
                 find_issue(r.issues, "associativity")->problem);

    c["associativity"] = nullptr;
    r = validate_config(c);  // null with direct is fine
    CHECK_TRUE(r.ok);

    // policy ----------------------------------------------------------------
    c = base_config();
    c.erase("policy");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is required for set_associative",
                 find_issue(r.issues, "policy")->problem);

    c = base_config();
    c["organization"] = "fully_associative";
    c.erase("associativity");
    c.erase("policy");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is required for fully_associative",
                 find_issue(r.issues, "policy")->problem);

    c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    r = validate_config(c);  // policy LRU with direct
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "policy")->problem.find(
                   "no selectable replacement policy") != std::string::npos);

    c["policy"] = nullptr;
    r = validate_config(c);  // policy null with direct is fine
    CHECK_TRUE(r.ok);

    c = base_config();
    c["policy"] = "MRU";
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be one of: LRU, FIFO, RANDOM",
                 find_issue(r.issues, "policy")->problem);

    // seed -------------------------------------------------------------------
    c = base_config();
    c["policy"] = "RANDOM";
    c.erase("seed");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is required when policy is RANDOM",
                 find_issue(r.issues, "seed")->problem);

    c["seed"] = nullptr;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "seed") != nullptr);

    c["seed"] = -1;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be an integer between 0 and 4294967295",
                 find_issue(r.issues, "seed")->problem);

    c["seed"] = 4294967296ULL;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "seed") != nullptr);

    c = base_config();
    c["seed"] = 7;  // seed with LRU is rejected (D-17)
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("is only used by the RANDOM policy; remove it or use null",
                 find_issue(r.issues, "seed")->problem);

    // timing assumptions -------------------------------------------------
    c = base_config();
    c.erase("miss_penalty");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR(
        "is required when hit_time is supplied (supply both timing "
        "assumptions or neither)",
        find_issue(r.issues, "miss_penalty")->problem);

    c = base_config();
    c.erase("hit_time");
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "hit_time") != nullptr);

    c["hit_time"] = -1.0;
    c["miss_penalty"] = 20.0;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("must be a finite number >= 0",
                 find_issue(r.issues, "hit_time")->problem);

    c["hit_time"] = "x";
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "hit_time") != nullptr);

    c["hit_time"] = true;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "hit_time") != nullptr);

    // unknown field --------------------------------------------------------
    c = base_config();
    c["associtivity"] = 2;
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("unknown field (typo or unsupported)",
                 find_issue(r.issues, "associtivity")->problem);

    // tag_bits < 0: address width cannot hold offset + index bits (AC-P2.4)
    c = {{"capacity_bytes", 128},
         {"block_size_bytes", 128},
         {"organization", "direct"},
         {"address_width_bits", 4}};
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "address_width_bits") != nullptr);
    CHECK_TRUE(find_issue(r.issues, "address_width_bits")->problem.find(
                   "offset_bits") != std::string::npos);
    CHECK_TRUE(find_issue(r.issues, "address_width_bits")->problem.find(
                   "tag") != std::string::npos);
    CHECK_EQ_STR("4", find_issue(r.issues, "address_width_bits")->received.dump());

    // ALL problems collected, not just the first (AC-P2.3)
    c = {{"capacity_bytes", 6}, {"block_size_bytes", 6}, {"address_width_bits", 3}};
    r = validate_config(c);
    CHECK_TRUE(!r.ok);
    CHECK_TRUE(find_issue(r.issues, "capacity_bytes") != nullptr);
    CHECK_TRUE(find_issue(r.issues, "block_size_bytes") != nullptr);
    CHECK_TRUE(find_issue(r.issues, "address_width_bits") != nullptr);
    CHECK_TRUE(find_issue(r.issues, "organization") != nullptr);
    CHECK_TRUE(r.issues.size() >= 4);

    // root shape ------------------------------------------------------------
    r = validate_config(json::array({1, 2}));
    CHECK_TRUE(!r.ok);
    CHECK_EQ_STR("configuration must be a JSON object",
                 find_issue(r.issues, "(root)")->problem);
  }

  section("simulate_direct");
  {
    // E1 walk (architecture.md 13): trace [16,16,16,16,16], direct 8 B /
    // 2 B blocks / width 8. Address 16 -> block 8, set 0, tag 2, offset 0.
    json c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    engine::SimulateResult r = run_sim(c, {16, 16, 16, 16, 16});
    CHECK_EQ_LL(5, r.events.size());
    const engine::SimulateEvent& t1 = r.events[0];
    CHECK_EQ_LL(1, t1.n);
    CHECK_EQ_LL(16, t1.address);
    CHECK_EQ_LL(8, t1.block);
    CHECK_EQ_LL(0, t1.offset);
    CHECK_EQ_LL(0, t1.set);
    CHECK_EQ_LL(2, t1.tag);
    CHECK_EQ_LL(0, t1.way);
    CHECK_TRUE(!t1.hit);
    CHECK_TRUE(t1.loaded);
    CHECK_TRUE(!t1.evicted_valid);
    CHECK_EQ_STR("Miss: block 8 loaded into set 0 way 0 (empty line).",
                 t1.explanation);
    for (int i = 1; i < 5; ++i) {
      const engine::SimulateEvent& e = r.events[static_cast<std::size_t>(i)];
      CHECK_TRUE(e.hit);
      CHECK_TRUE(!e.loaded);
      CHECK_EQ_LL(0, e.way);
      CHECK_TRUE(!e.evicted_valid);
      CHECK_EQ_STR("Hit: block 8 found in set 0 way 0 (tag 2).",
                   e.explanation);
    }
    CHECK_EQ_LL(5, r.counts.accesses);
    CHECK_EQ_LL(4, r.counts.hits);
    CHECK_EQ_LL(1, r.counts.misses);
    CHECK_EQ_LL(0, r.counts.evictions);
    CHECK_EQ_LL(4, r.final_state.sets.size());
    CHECK_TRUE(r.final_state.sets[0][0].valid);
    CHECK_EQ_LL(8, r.final_state.sets[0][0].block);
    CHECK_EQ_LL(2, r.final_state.sets[0][0].tag);
    CHECK_TRUE(!r.final_state.sets[1][0].valid);

    // Serialization: policy_meta for direct-mapped, index present, state.
    json cfg_copy = c;  // config for event_to_json
    engine::Config parsed_cfg;
    std::vector<engine::ValidationIssue> tmp_issues;
    CHECK_TRUE(engine::parse_and_validate_config(cfg_copy, &parsed_cfg, &tmp_issues));
    json ev0 = engine::event_to_json(r.events[0], parsed_cfg);
    CHECK_EQ_STR("miss", ev0["result"]);
    CHECK_TRUE(ev0["index"] == 0);
    CHECK_TRUE(ev0["evicted"].is_null());
    CHECK_TRUE(ev0["policy_meta"]["policy"].is_null());
    CHECK_EQ_STR("none", ev0["policy_meta"]["victim_selection"]);
    json state = state_json(parsed_cfg, r);
    CHECK_TRUE(state["snapshots"].is_null());
    CHECK_TRUE(state["sets"][0][0]["valid"] == true);
    CHECK_TRUE(state["sets"][0][0]["last_used_rank"] == 1);
    CHECK_TRUE(state["sets"][1][0]["valid"] == false);
    CHECK_TRUE(state["sets"][1][0]["tag"].is_null());
    json summary = engine::build_summary(parsed_cfg, r.counts, r.rng_draws,
                                         {16, 16, 16, 16, 16});
    CHECK_TRUE(summary["hit_rate"] == 0.8);
    CHECK_TRUE(summary["miss_rate"] == 0.2);
  }

  section("simulate_direct_conflict");
  {
    // E2 walk: trace [0,8,16,24,0] — blocks 0,4,8,12 all map to set 0.
    // Expected: 5 misses, 4 forced single-way evictions, 0 hits; final
    // set 0 holds block 12.
    json c = base_config();
    c["organization"] = "direct";
    c.erase("associativity");
    c.erase("policy");
    engine::SimulateResult r = run_sim(c, {0, 8, 16, 24, 0});
    CHECK_EQ_LL(5, r.counts.accesses);
    CHECK_EQ_LL(0, r.counts.hits);
    CHECK_EQ_LL(5, r.counts.misses);
    CHECK_EQ_LL(4, r.counts.evictions);
    const engine::SimulateEvent& t1 = r.events[0];
    CHECK_TRUE(!t1.evicted_valid);
    CHECK_EQ_STR("Miss: block 0 loaded into set 0 way 0 (empty line).",
                 t1.explanation);
    const std::uint64_t expected_evicted[4] = {0, 4, 8, 12};
    const std::uint64_t expected_loaded[4] = {4, 8, 12, 0};
    const std::uint64_t expected_tag[4] = {1, 2, 3, 0};
    for (int i = 0; i < 4; ++i) {
      const engine::SimulateEvent& e = r.events[static_cast<std::size_t>(i + 1)];
      CHECK_TRUE(e.evicted_valid);
      CHECK_EQ_LL(expected_evicted[i], e.evicted_block);
      CHECK_EQ_LL(0, e.evicted_way);
      CHECK_EQ_LL(expected_loaded[i], e.block);
      CHECK_EQ_LL(expected_tag[i], e.tag);
      CHECK_EQ_STR("Miss: block " + std::to_string(expected_loaded[i]) +
                       " loaded into set 0 way 0, evicting block " +
                       std::to_string(expected_evicted[i]) + " (direct).",
                   e.explanation);
    }
    // Final: the last access (t5) reloads block 0, evicting block 12 —
    // corrected final-state expectation (see architecture.md 13 E2 note).
    CHECK_TRUE(r.final_state.sets[0][0].valid);
    CHECK_EQ_LL(0, r.final_state.sets[0][0].block);
    CHECK_EQ_LL(0, r.final_state.sets[0][0].tag);
  }

  section("simulate_lru");
  {
    // E6 walk: trace [0,4,8,4,0], 2-way LRU — no eviction while an invalid
    // way exists (AC-P3.4): evictions stay 0 through t2.
    engine::SimulateResult r = run_sim(base_config(), {0, 4, 8, 4, 0});
    CHECK_EQ_LL(5, r.counts.accesses);
    CHECK_EQ_LL(1, r.counts.hits);
    CHECK_EQ_LL(4, r.counts.misses);
    CHECK_EQ_LL(2, r.counts.evictions);
    CHECK_TRUE(!r.events[0].evicted_valid);
    CHECK_TRUE(!r.events[1].evicted_valid);
    // Full t1/t2 fields: fills into empty ways, no evictions yet (AC-P3.4).
    CHECK_TRUE(!r.events[0].hit);
    CHECK_TRUE(r.events[0].loaded);
    CHECK_EQ_LL(0, r.events[0].address);
    CHECK_EQ_LL(0, r.events[0].block);
    CHECK_EQ_LL(0, r.events[0].tag);
    CHECK_EQ_LL(0, r.events[0].way);
    CHECK_EQ_LL(0, r.events[0].offset);
    CHECK_EQ_STR("Miss: block 0 loaded into set 0 way 0 (empty line).",
                 r.events[0].explanation);
    CHECK_TRUE(!r.events[1].hit);
    CHECK_TRUE(r.events[1].loaded);
    CHECK_EQ_LL(4, r.events[1].address);
    CHECK_EQ_LL(2, r.events[1].block);
    CHECK_EQ_LL(1, r.events[1].tag);
    CHECK_EQ_LL(1, r.events[1].way);
    CHECK_EQ_LL(0, r.events[1].offset);
    CHECK_EQ_STR("Miss: block 2 loaded into set 0 way 1 (empty line).",
                 r.events[1].explanation);
    // t3: C (block 4) evicts A (block 0, smallest used stamp), fills way 0.
    CHECK_TRUE(r.events[2].evicted_valid);
    CHECK_EQ_LL(0, r.events[2].evicted_block);
    CHECK_EQ_LL(0, r.events[2].way);
    CHECK_EQ_STR("Miss: block 4 loaded into set 0 way 0, evicting block 0 (LRU).",
                 r.events[2].explanation);
    // t4: B hit.
    CHECK_TRUE(r.events[3].hit);
    CHECK_EQ_LL(1, r.events[3].way);
    // t5: A miss evicts C (block 4), fills way 0.
    CHECK_TRUE(r.events[4].evicted_valid);
    CHECK_EQ_LL(4, r.events[4].evicted_block);
    CHECK_EQ_STR("Miss: block 0 loaded into set 0 way 0, evicting block 4 (LRU).",
                 r.events[4].explanation);
    // Final: way 0 = A (block 0, tag 0), way 1 = B (block 2, tag 1).
    CHECK_EQ_LL(0, r.final_state.sets[0][0].block);
    CHECK_EQ_LL(2, r.final_state.sets[0][1].block);
    json state = state_json(base_config(), r);
    CHECK_TRUE(state["sets"][0][0]["last_used_rank"] == 1);
    CHECK_TRUE(state["sets"][0][1]["last_used_rank"] == 2);
    CHECK_TRUE(state["sets"][0][0]["insert_order_rank"].is_null());
    // Event serialization: LRU meta.
    engine::Config cfg;
    std::vector<engine::ValidationIssue> iss;
    CHECK_TRUE(engine::parse_and_validate_config(base_config(), &cfg, &iss));
    json ev3 = engine::event_to_json(r.events[2], cfg);
    CHECK_EQ_STR("LRU", ev3["policy_meta"]["policy"]);
    CHECK_EQ_STR("lru", ev3["policy_meta"]["victim_selection"]);
    json ev0 = engine::event_to_json(r.events[0], cfg);
    CHECK_EQ_STR("none", ev0["policy_meta"]["victim_selection"]);

    // E3 LRU walk: trace [0,4,0,8,4] — the published controlled
    // demonstration sequence (architecture.md 13 E3): t4 evicts B,
    // t5 evicts A; 1 hit / 4 misses / 2 evictions.
    r = run_sim(base_config(), {0, 4, 0, 8, 4});
    CHECK_EQ_LL(1, r.counts.hits);
    CHECK_EQ_LL(4, r.counts.misses);
    CHECK_EQ_LL(2, r.counts.evictions);
    CHECK_TRUE(r.events[2].hit);                              // t3: A hit
    CHECK_TRUE(r.events[3].evicted_valid);
    CHECK_EQ_LL(2, r.events[3].evicted_block);                // t4: B out
    CHECK_EQ_LL(1, r.events[3].way);
    CHECK_EQ_STR("Miss: block 4 loaded into set 0 way 1, evicting block 2 (LRU).",
                 r.events[3].explanation);
    CHECK_TRUE(r.events[4].evicted_valid);
    CHECK_EQ_LL(0, r.events[4].evicted_block);                // t5: A out
    CHECK_EQ_STR("Miss: block 2 loaded into set 0 way 0, evicting block 0 (LRU).",
                 r.events[4].explanation);
    CHECK_EQ_LL(2, r.final_state.sets[0][0].block);           // B in way 0
    CHECK_EQ_LL(4, r.final_state.sets[0][1].block);           // C in way 1
  }

  section("simulate_fully_assoc");
  {
    // E4 walk: trace [0,4,8], fully-associative — one set, index null in
    // every event, ways filled 0,1,2, tags = block numbers, 0 evictions.
    json c = base_config();
    c["organization"] = "fully_associative";
    c.erase("associativity");
    engine::SimulateResult r = run_sim(c, {0, 4, 8});
    CHECK_EQ_LL(3, r.events.size());
    CHECK_EQ_LL(3, r.counts.misses);
    CHECK_EQ_LL(0, r.counts.hits);
    CHECK_EQ_LL(0, r.counts.evictions);
    for (int i = 0; i < 3; ++i) {
      const engine::SimulateEvent& e = r.events[static_cast<std::size_t>(i)];
      CHECK_TRUE(!e.has_index);
      CHECK_EQ_LL(0, e.set);
      CHECK_EQ_LL(static_cast<std::uint64_t>(i), e.way);
      CHECK_TRUE(!e.hit);
      CHECK_TRUE(e.loaded);
      CHECK_TRUE(!e.evicted_valid);
      CHECK_EQ_LL(4 * static_cast<std::uint64_t>(i), e.address);
      CHECK_EQ_LL(2 * static_cast<std::uint64_t>(i), e.block);
      CHECK_EQ_LL(0, e.offset);
      CHECK_EQ_LL(2 * static_cast<std::uint64_t>(i), e.tag);
      CHECK_EQ_STR("Miss: block " + std::to_string(2 * i) +
                       " loaded into set 0 way " + std::to_string(i) +
                       " (empty line).",
                   e.explanation);
    }
    CHECK_EQ_LL(1, r.final_state.sets.size());
    CHECK_EQ_LL(4, r.final_state.sets[0].size());
    for (int w = 0; w < 3; ++w) {
      CHECK_TRUE(r.final_state.sets[0][static_cast<std::size_t>(w)].valid);
      CHECK_EQ_LL(2 * w, r.final_state.sets[0][static_cast<std::size_t>(w)].block);
    }
    CHECK_TRUE(!r.final_state.sets[0][3].valid);
    // Serialization: index null; ranks 1..3 by recency.
    engine::Config cfg;
    std::vector<engine::ValidationIssue> iss;
    CHECK_TRUE(engine::parse_and_validate_config(c, &cfg, &iss));
    json ev0 = engine::event_to_json(r.events[0], cfg);
    CHECK_TRUE(ev0["index"].is_null());
    CHECK_EQ_STR("LRU", ev0["policy_meta"]["policy"]);
    json state = state_json(cfg, r);
    CHECK_TRUE(state["sets"][0][0]["last_used_rank"] == 3);
    CHECK_TRUE(state["sets"][0][1]["last_used_rank"] == 2);
    CHECK_TRUE(state["sets"][0][2]["last_used_rank"] == 1);
    CHECK_TRUE(state["sets"][0][3]["last_used_rank"].is_null());
  }

  section("simulate_snapshots_and_empty");
  {
    // Per-access snapshots (include_state_after_each = true).
    engine::SimulateResult r = run_sim(base_config(), {0, 4}, true);
    CHECK_EQ_LL(2, r.events.size());
    CHECK_TRUE(r.snapshots.is_array());
    CHECK_EQ_LL(2, r.snapshots.size());
    CHECK_TRUE(r.snapshots[0]["n"] == 1);
    CHECK_TRUE(r.snapshots[0]["sets"][0][0]["valid"] == true);
    CHECK_TRUE(r.snapshots[0]["sets"][0][1]["valid"] == false);
    CHECK_TRUE(r.snapshots[1]["sets"][0][0]["valid"] == true);
    CHECK_TRUE(r.snapshots[1]["sets"][0][1]["valid"] == true);
    json state = state_json(base_config(), r);
    CHECK_TRUE(state["snapshots"].is_array());
    CHECK_EQ_LL(2, state["snapshots"].size());

    // Empty trace: safe handling — no events, zeroed counts, null rates.
    r = run_sim(base_config(), {});
    CHECK_EQ_LL(0, r.events.size());
    CHECK_EQ_LL(0, r.counts.accesses);
    CHECK_EQ_LL(0, r.counts.hits);
    CHECK_EQ_LL(0, r.counts.misses);
    CHECK_EQ_LL(0, r.counts.evictions);
    engine::Config empty_cfg;
    std::vector<engine::ValidationIssue> empty_iss;
    CHECK_TRUE(engine::parse_and_validate_config(base_config(), &empty_cfg,
                                                 &empty_iss));
    json summary = engine::build_summary(empty_cfg, r.counts, r.rng_draws, {});
    CHECK_TRUE(summary["hit_rate"].is_null());
    CHECK_TRUE(summary["miss_rate"].is_null());
    // D-19: empty trace with timing inputs -> modeled miss rate 0, so the
    // AMAT value degenerates to hit_time.
    CHECK_TRUE(summary["amat"]["value"] == 1.0);
    CHECK_EQ_STR("cycles", summary["amat"]["unit"]);
  }

  section("rng_reference");
  {
    // Pins the documented RNG (D-15): std::mt19937 seeded 12345 — first two
    // draws verified with the toolchain probe on 2026-10-24.
    engine::SeededRandom rng(12345);
    CHECK_EQ_LL(3992670690ULL, rng.draw());
    CHECK_EQ_LL(3823185381ULL, rng.draw());
    CHECK_EQ_LL(2, rng.draws_used());
  }

  section("sha256_vectors");
  {
    // FIPS 180-4 canonical vectors for the trace-digest implementation.
    CHECK_EQ_STR(
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        engine::sha256_hex(""));
    CHECK_EQ_STR(
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        engine::sha256_hex("abc"));
  }

  section("simulate_fifo");
  {
    // E3 FIFO walk (architecture.md 13): trace [0,4,0,8,4], 2-way FIFO.
    // t3's hit must NOT reorder insertion order, so t4 evicts A (oldest
    // insert) while LRU evicted B — and t5 is a hit.
    json c = base_config();
    c["policy"] = "FIFO";
    engine::SimulateResult r = run_sim(c, {0, 4, 0, 8, 4});
    CHECK_EQ_LL(5, r.events.size());
    CHECK_EQ_LL(2, r.counts.hits);
    CHECK_EQ_LL(3, r.counts.misses);
    CHECK_EQ_LL(1, r.counts.evictions);
    CHECK_EQ_LL(0, r.rng_draws);  // FIFO consumes no draws
    CHECK_TRUE(!r.events[0].evicted_valid);
    CHECK_TRUE(!r.events[1].evicted_valid);
    CHECK_TRUE(r.events[2].hit);  // t3: A hit
    CHECK_TRUE(r.events[3].evicted_valid);
    CHECK_EQ_LL(0, r.events[3].evicted_block);  // t4: A out (oldest insert)
    CHECK_EQ_LL(0, r.events[3].way);
    CHECK_EQ_STR("Miss: block 4 loaded into set 0 way 0, evicting block 0 (FIFO).",
                 r.events[3].explanation);
    CHECK_TRUE(r.events[4].hit);  // t5: B still resident (hit did not reorder)
    CHECK_EQ_LL(1, r.events[4].way);
    // Final: way 0 = C (block 4), way 1 = B (block 2).
    CHECK_EQ_LL(4, r.final_state.sets[0][0].block);
    CHECK_EQ_LL(2, r.final_state.sets[0][1].block);
    json state = state_json(c, r);  // FIFO config: insert ranks, no LRU ranks
    CHECK_TRUE(state["sets"][0][0]["last_used_rank"].is_null());
    CHECK_TRUE(state["sets"][0][1]["last_used_rank"].is_null());
    CHECK_TRUE(state["sets"][0][1]["insert_order_rank"] == 1);  // B oldest
    CHECK_TRUE(state["sets"][0][0]["insert_order_rank"] == 2);  // C newer
    // Event serialization: FIFO meta.
    engine::Config cfg;
    std::vector<engine::ValidationIssue> iss;
    CHECK_TRUE(engine::parse_and_validate_config(c, &cfg, &iss));
    json ev3 = engine::event_to_json(r.events[3], cfg);
    CHECK_EQ_STR("FIFO", ev3["policy_meta"]["policy"]);
    CHECK_EQ_STR("fifo_oldest", ev3["policy_meta"]["victim_selection"]);
    json ev0 = engine::event_to_json(r.events[0], cfg);
    CHECK_EQ_STR("none", ev0["policy_meta"]["victim_selection"]);
  }

  section("simulate_random");
  {
    // Pinned seed-12345 reference (D-15, architecture.md 13 E5): draw 1 =
    // 3992670690, % 2 = way 0, so t4 evicts block A (block 0); draw 2 is
    // never consumed; t5 hits. Outcome 2 hits / 3 misses / 1 eviction.
    json c = base_config();
    c["policy"] = "RANDOM";
    c["seed"] = 12345;
    engine::SimulateResult r = run_sim(c, {0, 4, 0, 8, 4});
    CHECK_EQ_LL(2, r.counts.hits);
    CHECK_EQ_LL(3, r.counts.misses);
    CHECK_EQ_LL(1, r.counts.evictions);
    CHECK_EQ_LL(1, r.rng_draws);
    CHECK_TRUE(r.events[2].hit);  // t3: A hit (both ways filled by t2)
    CHECK_TRUE(r.events[3].evicted_valid);
    CHECK_EQ_LL(0, r.events[3].evicted_block);
    CHECK_EQ_LL(0, r.events[3].way);
    CHECK_EQ_STR("Miss: block 4 loaded into set 0 way 0, evicting block 0 (Random).",
                 r.events[3].explanation);
    CHECK_TRUE(r.events[4].hit);  // t5: B survived the draw
    CHECK_EQ_LL(4, r.final_state.sets[0][0].block);
    CHECK_EQ_LL(2, r.final_state.sets[0][1].block);
    json state = state_json(c, r);
    CHECK_TRUE(state["sets"][0][0]["last_used_rank"].is_null());
    CHECK_TRUE(state["sets"][0][0]["insert_order_rank"].is_null());
    engine::Config cfg;
    std::vector<engine::ValidationIssue> iss;
    CHECK_TRUE(engine::parse_and_validate_config(c, &cfg, &iss));
    json ev3 = engine::event_to_json(r.events[3], cfg);
    CHECK_EQ_STR("RANDOM", ev3["policy_meta"]["policy"]);
    CHECK_EQ_STR("random", ev3["policy_meta"]["victim_selection"]);
    CHECK_EQ_LL(12345, ev3["policy_meta"]["seed"]);
    json ev0 = engine::event_to_json(r.events[0], cfg);
    CHECK_TRUE(ev0["policy_meta"]["seed"].is_null());

    // Invalid-line fills consume no draws: two fills -> 0 draws.
    r = run_sim(c, {0, 4});
    CHECK_EQ_LL(0, r.rng_draws);
    CHECK_EQ_LL(2, r.counts.misses);
    CHECK_EQ_LL(0, r.counts.evictions);

    const std::vector<std::uint64_t> e5_trace = {0, 4, 8, 12, 16};

    // Pinned seed-7 walk for the E5 trace (architecture.md 13 E5): draws
    // 327741615 (%2=1), 976413892 (%2=0), 3349725721 (%2=1) -> victims
    // way 1, way 0, way 1. Full expected-vs-actual table.
    json c7 = base_config();
    c7["policy"] = "RANDOM";
    c7["seed"] = 7;
    r = run_sim(c7, e5_trace);
    CHECK_EQ_LL(5, r.counts.misses);
    CHECK_EQ_LL(0, r.counts.hits);
    CHECK_EQ_LL(3, r.counts.evictions);
    CHECK_EQ_LL(3, r.rng_draws);
    CHECK_TRUE(!r.events[0].evicted_valid);
    CHECK_TRUE(!r.events[1].evicted_valid);
    const std::uint64_t e5_block[5] = {0, 2, 4, 6, 8};
    const std::uint64_t e5_tag[5] = {0, 1, 2, 3, 4};
    const std::uint64_t e5_way[5] = {0, 1, 1, 0, 1};
    const std::uint64_t e5_evicted[5] = {0, 0, 2, 0, 4};
    for (int i = 0; i < 5; ++i) {
      const engine::SimulateEvent& ev =
          r.events[static_cast<std::size_t>(i)];
      CHECK_EQ_LL(4 * i, ev.address);
      CHECK_EQ_LL(e5_block[i], ev.block);
      CHECK_EQ_LL(e5_tag[i], ev.tag);
      CHECK_EQ_LL(e5_way[i], ev.way);
      CHECK_TRUE(!ev.hit);
      CHECK_TRUE(ev.loaded);
      if (i < 2) {
        CHECK_TRUE(!ev.evicted_valid);
      } else {
        CHECK_TRUE(ev.evicted_valid);
        CHECK_EQ_LL(e5_evicted[i], ev.evicted_block);
        CHECK_EQ_STR(
            "Miss: block " + std::to_string(e5_block[i]) +
                " loaded into set 0 way " + std::to_string(e5_way[i]) +
                ", evicting block " + std::to_string(e5_evicted[i]) +
                " (Random).",
            ev.explanation);
      }
    }
    CHECK_EQ_LL(6, r.final_state.sets[0][0].block);
    CHECK_EQ_LL(8, r.final_state.sets[0][1].block);

    // E5 determinism (architecture.md 13): same seed twice -> byte-identical
    // serialized results; different seed also deterministic.
    engine::SimulateResult a = run_sim(c, e5_trace);
    engine::SimulateResult b = run_sim(c, e5_trace);
    CHECK_EQ_STR(result_dump(cfg, a, e5_trace),
                 result_dump(cfg, b, e5_trace));
    CHECK_EQ_LL(5, a.counts.misses);
    CHECK_EQ_LL(0, a.counts.hits);
    CHECK_EQ_LL(3, a.counts.evictions);
    CHECK_EQ_LL(3, a.rng_draws);
    json c2 = c;
    c2["seed"] = 8;
    engine::Config cfg2;
    CHECK_TRUE(engine::parse_and_validate_config(c2, &cfg2, &iss));
    engine::SimulateResult run_d = run_sim(c2, e5_trace);
    engine::SimulateResult run_e = run_sim(c2, e5_trace);
    CHECK_EQ_STR(result_dump(cfg2, run_d, e5_trace),
                 result_dump(cfg2, run_e, e5_trace));
  }

  section("simulate_stats");
  {
    // AMAT values for the E3 trace (architecture.md 13 E3): LRU 17.00,
    // FIFO 13.00, RANDOM (seed 12345) 13.00 — hit_time 1, miss_penalty 20.
    engine::Config cfg;
    std::vector<engine::ValidationIssue> iss;
    json lru = base_config();
    CHECK_TRUE(engine::parse_and_validate_config(lru, &cfg, &iss));
    engine::SimulateResult r = run_sim(lru, {0, 4, 0, 8, 4});
    json s = engine::build_summary(cfg, r.counts, r.rng_draws, {0, 4, 0, 8, 4});
    CHECK_TRUE(s["amat"]["value"] == 17.0);
    CHECK_EQ_STR("LRU", s["replacement_meta"]["policy"]);
    CHECK_TRUE(s["replacement_meta"]["seed"].is_null());

    json fifo = base_config();
    fifo["policy"] = "FIFO";
    CHECK_TRUE(engine::parse_and_validate_config(fifo, &cfg, &iss));
    r = run_sim(fifo, {0, 4, 0, 8, 4});
    s = engine::build_summary(cfg, r.counts, r.rng_draws, {0, 4, 0, 8, 4});
    CHECK_TRUE(s["amat"]["value"] == 13.0);
    CHECK_EQ_STR("FIFO", s["replacement_meta"]["policy"]);

    json rnd = base_config();
    rnd["policy"] = "RANDOM";
    rnd["seed"] = 12345;
    CHECK_TRUE(engine::parse_and_validate_config(rnd, &cfg, &iss));
    r = run_sim(rnd, {0, 4, 0, 8, 4});
    s = engine::build_summary(cfg, r.counts, r.rng_draws, {0, 4, 0, 8, 4});
    CHECK_TRUE(s["amat"]["value"] == 13.0);
    CHECK_EQ_STR("RANDOM", s["replacement_meta"]["policy"]);
    CHECK_EQ_LL(12345, s["replacement_meta"]["seed"]);
    CHECK_EQ_LL(1, s["replacement_meta"]["rng_draws"]);
    const std::string digest = s["trace_sha256"];
    CHECK_EQ_LL(64, digest.size());
    CHECK_TRUE(s["amat"]["unit"] == "cycles");

    // amat is omitted entirely when timing inputs are absent — never
    // emitted as null (AC-P4.4). Use find(): operator[] would insert null.
    json no_timing = base_config();
    no_timing.erase("hit_time");
    no_timing.erase("miss_penalty");
    CHECK_TRUE(engine::parse_and_validate_config(no_timing, &cfg, &iss));
    r = run_sim(no_timing, {16});
    s = engine::build_summary(cfg, r.counts, r.rng_draws, {16});
    CHECK_TRUE(s.find("amat") == s.end());

    // replacement_meta is omitted for direct-mapped; AMAT from counts.
    json direct = base_config();
    direct["organization"] = "direct";
    direct.erase("associativity");
    direct.erase("policy");
    CHECK_TRUE(engine::parse_and_validate_config(direct, &cfg, &iss));
    r = run_sim(direct, {16, 16});
    s = engine::build_summary(cfg, r.counts, r.rng_draws, {16, 16});
    CHECK_TRUE(s.find("replacement_meta") == s.end());
    CHECK_TRUE(s["amat"]["value"] == 11.0);  // 1 miss / 2 accesses -> 0.5
  }

  section("trace_validation_unit");
  {
    // Engine-level unit tests for validate_trace — AC-7 (address outside
    // the width) and AC-9 (empty/malformed traces) at the engine layer.
    json t = {{"name", "ok"}, {"addresses", {0, 255}}};
    engine::TraceValidation tv = engine::validate_trace(t, 255);
    CHECK_TRUE(tv.ok);
    CHECK_EQ_LL(2, (long long)tv.trace.addresses.size());
    CHECK_EQ_STR("ok", tv.trace.name);

    t = {{"addresses", {1}}};  // name missing
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "name") != nullptr);

    t = {{"name", 5}, {"addresses", {1}}};  // name wrong type
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "name") != nullptr);

    t = {{"name", ""}, {"addresses", {1}}};  // name empty
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "name") != nullptr);

    t = {{"name", "x"}, {"addresses", 5}};  // addresses not an array
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "addresses") != nullptr);

    t = {{"name", "x"}};  // addresses missing
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "addresses") != nullptr);

    // AC-7: address above the width — rejected with the max stated.
    t = {{"name", "x"}, {"addresses", {0, 256}}};
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    const engine::ValidationIssue* over =
        find_issue(tv.issues, "addresses[1]");
    CHECK_TRUE(over != nullptr);
    CHECK_TRUE(over->problem.find("255") != std::string::npos);
    CHECK_EQ_STR("256", over->received.dump());

    // Negative and fractional addresses rejected.
    t = {{"name", "x"}, {"addresses", {-1}}};
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "addresses[0]") != nullptr);

    t = {{"name", "x"}, {"addresses", {1.5}}};
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "addresses[0]") != nullptr);

    // 100,001 addresses: limit violation routed to E_LIMIT (tv.limit_problems).
    json many = json::array();
    for (int i = 0; i < 100001; ++i) many.push_back(0);
    t = {{"name", "x"}, {"addresses", many}};
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_EQ_LL(1, (long long)tv.limit_problems);
    CHECK_TRUE(find_issue(tv.issues, "addresses") != nullptr);

    // Unknown trace key (typo protection).
    t = {{"name", "x"}, {"addresses", {1}}, {"addrss", {2}}};
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    CHECK_TRUE(find_issue(tv.issues, "addrss") != nullptr);

    // Detail cap: 15 bad addresses -> 10 collected + one truncation note.
    json bad = json::array();
    for (int i = 0; i < 15; ++i) bad.push_back(999);
    t = {{"name", "x"}, {"addresses", bad}};
    tv = engine::validate_trace(t, 255);
    CHECK_TRUE(!tv.ok);
    std::size_t address_details = 0;
    bool truncation_note = false;
    for (const auto& issue : tv.issues) {
      if (issue.field.compare(0, 9, "addresses") == 0) {
        if (issue.problem.find("truncated") != std::string::npos) {
          truncation_note = true;
        } else {
          ++address_details;
        }
      }
    }
    CHECK_EQ_LL(10, (long long)address_details);
    CHECK_TRUE(truncation_note);
  }

  section("boundaries");
  {
    // Maximum valid address accepted (width 64, address = 2^64 - 1) with
    // no overflow anywhere: block = a, set = a & 7, tag = a >> 3.
    json c = {{"capacity_bytes", 8},
              {"block_size_bytes", 1},
              {"organization", "direct"},
              {"address_width_bits", 64}};
    engine::SimulateResult r =
        run_sim(c, {18446744073709551615ULL});
    CHECK_EQ_LL(1, r.events.size());
    CHECK_EQ_LL(18446744073709551615ULL, r.events[0].block);
    CHECK_EQ_LL(7, r.events[0].set);
    CHECK_EQ_LL(2305843009213693951ULL, r.events[0].tag);
    CHECK_TRUE(!r.events[0].hit);
    CHECK_TRUE(r.final_state.sets[7][0].valid);

    // AC-P5.3: 100,000 sequential accesses complete in < 1 s, with exact
    // hand-derived counts — pairs (2k, 2k+1) share block k, so one miss +
    // one hit per block and an eviction for every fill after the first.
    json seq = {{"capacity_bytes", 8},
                {"block_size_bytes", 2},
                {"organization", "direct"},
                {"address_width_bits", 32}};
    std::vector<std::uint64_t> trace;
    trace.reserve(100000);
    for (std::uint64_t a = 0; a < 100000; ++a) trace.push_back(a);
    const auto perf_start = std::chrono::steady_clock::now();
    r = run_sim(seq, trace);
    const auto perf_end = std::chrono::steady_clock::now();
    const double seconds =
        std::chrono::duration<double>(perf_end - perf_start).count();
    std::printf("[perf] 100000-access simulate: %.4f s\n", seconds);
    CHECK_TRUE(seconds < 1.0);
    CHECK_EQ_LL(100000, r.counts.accesses);
    CHECK_EQ_LL(50000, r.counts.misses);
    CHECK_EQ_LL(50000, r.counts.hits);
    // The first four misses fill the four empty sets; every one of the
    // remaining 49,996 misses evicts (50000 - 4). Corrected expectation —
    // the engine count was verified against this walk.
    CHECK_EQ_LL(49996, r.counts.evictions);
    CHECK_EQ_LL(100000, (long long)r.events.size());
    CHECK_EQ_LL(49999, r.final_state.sets[3][0].block);
    CHECK_EQ_LL(12499, r.final_state.sets[3][0].tag);

    // The 100,001-address refusal is covered by trace_validation_unit
    // above; the include_state_after_each 2,001 refusal by pytest
    // TestSimulateMode::test_snapshot_trace_cap_2000.
  }

  section("determinism_matrix");
  {
    // AC-12: LRU, FIFO, RANDOM(seed 7), RANDOM(seed 8) — each run twice on
    // the E3 trace; every pair must be byte-identical.
    const std::vector<std::uint64_t> trace = {0, 4, 0, 8, 4};
    const char* policies[] = {"LRU", "FIFO"};
    for (const char* policy_name : policies) {
      json c = base_config();
      c["policy"] = policy_name;
      engine::Config cfg;
      std::vector<engine::ValidationIssue> iss;
      CHECK_TRUE(engine::parse_and_validate_config(c, &cfg, &iss));
      engine::SimulateResult r1 = run_sim(c, trace);
      engine::SimulateResult r2 = run_sim(c, trace);
      CHECK_EQ_STR(result_dump(cfg, r1, trace),
                   result_dump(cfg, r2, trace));
    }
    for (std::uint32_t seed : {7u, 8u}) {
      json c = base_config();
      c["policy"] = "RANDOM";
      c["seed"] = seed;
      engine::Config cfg;
      std::vector<engine::ValidationIssue> iss;
      CHECK_TRUE(engine::parse_and_validate_config(c, &cfg, &iss));
      engine::SimulateResult r1 = run_sim(c, trace);
      engine::SimulateResult r2 = run_sim(c, trace);
      CHECK_EQ_STR(result_dump(cfg, r1, trace),
                   result_dump(cfg, r2, trace));
    }
  }

  section("property_sweep");
  {
    // AC-11: seeded, deterministic sweep over configs x traces. Every run
    // must satisfy the architecture.md 9 invariants (asserted inside
    // run_sim) plus recountable event/summary consistency. Expectations
    // are invariants only — no invented numbers.
    std::vector<json> configs;
    configs.push_back(json{{"capacity_bytes", 8},
                           {"block_size_bytes", 2},
                           {"organization", "direct"},
                           {"address_width_bits", 16}});
    configs.push_back(base_config());
    json fifo = base_config();
    fifo["policy"] = "FIFO";
    configs.push_back(fifo);
    json random42 = base_config();
    random42["policy"] = "RANDOM";
    random42["seed"] = 42;
    configs.push_back(random42);
    json fully = base_config();
    fully["organization"] = "fully_associative";
    fully.erase("associativity");
    configs.push_back(fully);
    json fully_random = fully;
    fully_random["policy"] = "RANDOM";
    fully_random["seed"] = 99;
    configs.push_back(fully_random);
    configs.push_back(json{{"capacity_bytes", 64},
                           {"block_size_bytes", 4},
                           {"organization", "set_associative"},
                           {"associativity", 2},
                           {"address_width_bits", 16},
                           {"policy", "LRU"}});

    // Deterministic pseudo-random addresses (fixed-seed LCG — no unseeded
    // randomness anywhere, rules.md 2).
    auto lcg = [](std::uint64_t& state, std::uint64_t modulus) {
      state = state * 6364136223846793005ULL + 1442695040888963407ULL;
      return (state >> 33) % modulus;
    };
    std::vector<std::vector<std::uint64_t>> traces;
    {
      std::vector<std::uint64_t> strided;
      for (std::uint64_t a = 0; a < 100; ++a) strided.push_back(a * 3 % 256);
      traces.push_back(strided);
      std::vector<std::uint64_t> conflict;
      for (int k = 0; k < 25; ++k) {
        conflict.push_back(0);
        conflict.push_back(8);
        conflict.push_back(16);
        conflict.push_back(24);
      }
      traces.push_back(conflict);
      traces.push_back(std::vector<std::uint64_t>(50, 40));
      std::vector<std::uint64_t> pseudo;
      std::uint64_t state = 12345;
      for (int i = 0; i < 200; ++i) pseudo.push_back(lcg(state, 256));
      traces.push_back(pseudo);
    }

    for (const json& config_json : configs) {
      engine::Config cfg;
      std::vector<engine::ValidationIssue> iss;
      CHECK_TRUE(engine::parse_and_validate_config(config_json, &cfg, &iss));
      const bool is_random = cfg.has_policy && cfg.policy == "RANDOM";
      for (const auto& trace : traces) {
        engine::SimulateResult r = run_sim(config_json, trace);
        CHECK_EQ_LL((long long)trace.size(), (long long)r.events.size());
        std::uint64_t hits = 0, misses = 0, evictions = 0;
        for (const auto& e : r.events) {
          if (e.hit) ++hits;
          else ++misses;
          if (e.evicted_valid) ++evictions;
        }
        CHECK_EQ_LL((long long)hits, (long long)r.counts.hits);
        CHECK_EQ_LL((long long)misses, (long long)r.counts.misses);
        CHECK_EQ_LL((long long)evictions, (long long)r.counts.evictions);
        if (is_random) {
          CHECK_EQ_LL((long long)evictions, (long long)r.rng_draws);
        }
      }
    }
  }

  if (g_section != nullptr) {
    std::printf("[done] %s: %d checks, %d failures\n", g_section,
                g_checks - g_section_checks, g_failures - g_section_failures);
  }
  std::printf("summary: %d checks, %d failures\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
