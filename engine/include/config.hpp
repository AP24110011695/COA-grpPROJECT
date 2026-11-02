#pragma once

// Configuration model and authoritative validation
// (architecture.md 6.1, prd.md 5, architecture.md 12).

#include <cstdint>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace engine {

struct Config {
  std::uint64_t capacity_bytes = 0;
  std::uint64_t block_size_bytes = 0;
  std::string organization;  // "direct" | "set_associative" | "fully_associative"
  bool has_associativity = false;
  std::uint64_t associativity = 0;
  int address_width_bits = 0;  // 4..64
  bool has_policy = false;     // "LRU" | "FIFO" | "RANDOM" (never for direct)
  std::string policy;
  bool has_seed = false;  // required iff policy == "RANDOM"
  std::uint32_t seed = 0;
  bool has_hit_time = false;      // both-or-neither with miss_penalty
  double hit_time = 0.0;
  bool has_miss_penalty = false;
  double miss_penalty = 0.0;
};

struct ValidationIssue {
  std::string field;
  std::string problem;
  nlohmann::json received;  // null when the field was missing
};

// Parses and validates a configuration JSON object, collecting ALL problems
// before failing. Returns true iff the configuration is usable; on false,
// `issues` carries every violated rule (field, problem, received value).
// Never clamps, defaults, or repairs input (rules.md 3).
bool parse_and_validate_config(const nlohmann::json& input, Config* out,
                               std::vector<ValidationIssue>* issues);

// Appends one validation issue (shared by config and trace validation).
void add_issue(std::vector<ValidationIssue>* issues, std::string field,
               std::string problem, nlohmann::json received);

// Reads a JSON integer that must be non-negative. Returns false (and does
// not touch *out) for negatives, floats, bools, and strings. Handles both
// signed and unsigned nlohmann integers (positive parsed integers are
// unsigned — see D-17).
bool get_non_negative_int(const nlohmann::json& v, std::uint64_t* out);

}  // namespace engine
