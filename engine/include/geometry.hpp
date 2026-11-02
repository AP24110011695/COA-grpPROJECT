#pragma once

// Derived cache geometry (architecture.md 6.3 and 7).

#include <cstdint>
#include <vector>

#include "config.hpp"

namespace engine {

struct Geometry {
  std::uint64_t lines = 0;
  std::uint64_t sets = 0;
  int offset_bits = 0;
  int index_bits = 0;
  int tag_bits = 0;
  bool index_field_present = true;  // false only for fully_associative
  std::uint64_t max_address = 0;    // 2^address_width_bits - 1
};

// Derives geometry from a validated configuration. Returns false (with an
// issue appended to `issues`) when the address width cannot hold the
// derived offset + index bits, i.e. tag_bits would be negative.
bool derive_geometry(const Config& config, Geometry* out,
                     std::vector<ValidationIssue>* issues);

nlohmann::json geometry_to_json(const Geometry& geometry, const Config& config);

nlohmann::json issues_to_json(const std::vector<ValidationIssue>& issues);

}  // namespace engine
