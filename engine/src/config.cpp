// Configuration parsing and authoritative validation
// (architecture.md 6.1, prd.md 5, architecture.md 12). Collects ALL problems
// before failing; never clamps, defaults, or repairs input (rules.md 3).

#include "config.hpp"

#include <cmath>
#include <string>
#include <vector>

using json = nlohmann::json;

namespace engine {
namespace {

constexpr std::uint64_t kMaxCapacityBytes = 1048576ULL;  // 2^20
constexpr std::uint64_t kMaxBlockSizeBytes = 128;
constexpr std::uint64_t kMaxSeed = 4294967295ULL;

bool is_power_of_two(std::uint64_t v) {
  return v != 0 && (v & (v - 1)) == 0;
}

const json* member(const json& obj, const char* key) {
  const auto it = obj.find(key);
  return it == obj.end() ? nullptr : &(*it);
}

bool absent_or_null(const json* v) { return v == nullptr || v->is_null(); }

}  // namespace

void add_issue(std::vector<ValidationIssue>* issues, std::string field,
               std::string problem, json received) {
  ValidationIssue issue;
  issue.field = std::move(field);
  issue.problem = std::move(problem);
  issue.received = std::move(received);
  issues->push_back(std::move(issue));
}

bool get_non_negative_int(const json& v, std::uint64_t* out) {
  if (v.is_number_unsigned()) {
    *out = v.get<std::uint64_t>();
    return true;
  }
  if (v.is_number_integer()) {
    const std::int64_t s = v.get<std::int64_t>();
    if (s < 0) return false;
    *out = static_cast<std::uint64_t>(s);
    return true;
  }
  return false;
}

bool parse_and_validate_config(const json& input, Config* out,
                               std::vector<ValidationIssue>* issues) {
  // Reset the output struct unconditionally: flag fields (has_policy etc.)
  // must never leak from a previous parse when callers reuse a Config.
  *out = Config{};
  if (!input.is_object()) {
    add_issue(issues, "(root)", "configuration must be a JSON object", input);
    return false;
  }

  static const char* const kKnownFields[] = {
      "capacity_bytes",   "block_size_bytes",     "organization",
      "associativity",    "address_width_bits",   "policy",
      "seed",             "hit_time",             "miss_penalty"};

  for (auto it = input.begin(); it != input.end(); ++it) {
    bool known = false;
    for (const char* k : kKnownFields) {
      if (it.key() == k) {
        known = true;
        break;
      }
    }
    if (!known) {
      add_issue(issues, it.key(), "unknown field (typo or unsupported)", *it);
    }
  }

  // capacity_bytes ------------------------------------------------------
  const json* cap = member(input, "capacity_bytes");
  bool cap_ok = false;
  std::uint64_t capacity = 0;
  if (absent_or_null(cap)) {
    add_issue(issues, "capacity_bytes", "is required", nullptr);
  } else {
    std::uint64_t v = 0;
    if (!get_non_negative_int(*cap, &v) || !is_power_of_two(v)) {
      add_issue(issues, "capacity_bytes",
                "must be an integer power of two between 1 and 1048576", *cap);
    } else if (v > kMaxCapacityBytes) {
      add_issue(issues, "capacity_bytes", "must not exceed 1048576 (2^20)",
                *cap);
    } else {
      capacity = v;
      cap_ok = true;
    }
  }
  out->capacity_bytes = capacity;

  // block_size_bytes ----------------------------------------------------
  const json* block = member(input, "block_size_bytes");
  bool block_ok = false;
  std::uint64_t block_size = 0;
  if (absent_or_null(block)) {
    add_issue(issues, "block_size_bytes", "is required", nullptr);
  } else {
    std::uint64_t v = 0;
    if (!get_non_negative_int(*block, &v) || !is_power_of_two(v) ||
        v > kMaxBlockSizeBytes) {
      add_issue(issues, "block_size_bytes",
                "must be an integer power of two between 1 and 128", *block);
    } else {
      block_size = v;
      block_ok = true;
    }
  }
  out->block_size_bytes = block_size;
  if (cap_ok && block_ok && block_size > capacity) {
    add_issue(issues, "block_size_bytes",
              "must not exceed capacity_bytes (= " +
                  std::to_string(capacity) + ")",
              *block);
  }

  // organization ---------------------------------------------------------
  const json* org = member(input, "organization");
  bool org_ok = false;
  if (absent_or_null(org)) {
    add_issue(issues, "organization", "is required", nullptr);
  } else if (!org->is_string()) {
    add_issue(issues, "organization",
              "must be one of: direct, set_associative, fully_associative",
              *org);
  } else {
    const std::string s = org->get<std::string>();
    if (s != "direct" && s != "set_associative" && s != "fully_associative") {
      add_issue(issues, "organization",
                "must be one of: direct, set_associative, fully_associative",
                *org);
    } else {
      out->organization = s;
      org_ok = true;
    }
  }

  // address_width_bits ---------------------------------------------------
  // Note: nlohmann parses positive JSON integers as unsigned, so the width
  // must go through get_non_negative_int (which accepts both) rather than
  // any is_number_unsigned() rejection.
  const json* width = member(input, "address_width_bits");
  if (absent_or_null(width)) {
    add_issue(issues, "address_width_bits", "is required", nullptr);
  } else {
    std::uint64_t v = 0;
    if (!get_non_negative_int(*width, &v) || v < 4 || v > 64) {
      add_issue(issues, "address_width_bits",
                "must be an integer between 4 and 64", *width);
    } else {
      out->address_width_bits = static_cast<int>(v);
    }
  }

  // associativity --------------------------------------------------------
  const json* assoc = member(input, "associativity");
  const bool org_is_sa = org_ok && out->organization == "set_associative";
  if (org_is_sa) {
    if (absent_or_null(assoc)) {
      add_issue(issues, "associativity", "is required for set_associative",
                nullptr);
    } else {
      std::uint64_t v = 0;
      if (!get_non_negative_int(*assoc, &v) || v < 2 || !is_power_of_two(v)) {
        add_issue(issues, "associativity",
                  "must be an integer power of two between 2 and "
                  "capacity_bytes / block_size_bytes (use the direct "
                  "organization for one line per set)",
                  *assoc);
      } else if (cap_ok && block_ok && v > capacity / block_size) {
        add_issue(issues, "associativity",
                  "must not exceed capacity_bytes / block_size_bytes (= " +
                      std::to_string(capacity / block_size) + ")",
                  *assoc);
      } else {
        out->has_associativity = true;
        out->associativity = v;
      }
    }
  } else if (!absent_or_null(assoc)) {
    add_issue(issues, "associativity",
              "is only valid for set_associative; remove it or use null",
              *assoc);
  }

  // policy ----------------------------------------------------------------
  const json* pol = member(input, "policy");
  const bool org_is_direct = org_ok && out->organization == "direct";
  if (org_is_direct) {
    if (!absent_or_null(pol)) {
      add_issue(issues, "policy",
                "direct-mapped caches have no selectable replacement policy; "
                "remove policy or use null",
                *pol);
    }
  } else if (org_ok) {
    if (absent_or_null(pol)) {
      add_issue(issues, "policy", "is required for " + out->organization,
                nullptr);
    } else if (!pol->is_string()) {
      add_issue(issues, "policy", "must be one of: LRU, FIFO, RANDOM", *pol);
    } else {
      const std::string s = pol->get<std::string>();
      if (s != "LRU" && s != "FIFO" && s != "RANDOM") {
        add_issue(issues, "policy", "must be one of: LRU, FIFO, RANDOM", *pol);
      } else {
        out->has_policy = true;
        out->policy = s;
      }
    }
  }

  // seed -------------------------------------------------------------------
  const json* seed = member(input, "seed");
  const bool policy_is_random = out->has_policy && out->policy == "RANDOM";
  if (policy_is_random) {
    if (absent_or_null(seed)) {
      add_issue(issues, "seed", "is required when policy is RANDOM", nullptr);
    } else {
      std::uint64_t v = 0;
      if (!get_non_negative_int(*seed, &v) || v > kMaxSeed) {
        add_issue(issues, "seed",
                  "must be an integer between 0 and 4294967295", *seed);
      } else {
        out->has_seed = true;
        out->seed = static_cast<std::uint32_t>(v);
      }
    }
  } else if (!absent_or_null(seed)) {
    add_issue(issues, "seed",
              "is only used by the RANDOM policy; remove it or use null",
              *seed);
  }

  // hit_time / miss_penalty (both-or-neither) ------------------------------
  const json* hit = member(input, "hit_time");
  const json* penalty = member(input, "miss_penalty");
  const bool hit_supplied = !absent_or_null(hit);
  const bool penalty_supplied = !absent_or_null(penalty);
  if (hit_supplied && !penalty_supplied) {
    add_issue(issues, "miss_penalty",
              "is required when hit_time is supplied (supply both timing "
              "assumptions or neither)",
              nullptr);
  } else if (!hit_supplied && penalty_supplied) {
    add_issue(issues, "hit_time",
              "is required when miss_penalty is supplied (supply both timing "
              "assumptions or neither)",
              nullptr);
  }
  auto check_timing = [&](const json* v, const char* name, bool* supplied_ok,
                          double* value) {
    *supplied_ok = false;
    if (absent_or_null(v)) return;
    if (!v->is_number()) {
      add_issue(issues, name, "must be a finite number >= 0", *v);
      return;
    }
    const double d = v->get<double>();
    if (!std::isfinite(d) || d < 0) {
      add_issue(issues, name, "must be a finite number >= 0", *v);
      return;
    }
    *value = d;
    *supplied_ok = true;
  };
  check_timing(hit, "hit_time", &out->has_hit_time, &out->hit_time);
  check_timing(penalty, "miss_penalty", &out->has_miss_penalty,
               &out->miss_penalty);

  return issues->empty();
}

}  // namespace engine
