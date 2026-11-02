// Geometry derivation (architecture.md 7): integer-safe bit widths via
// shift counting (never floating-point log), 64-bit address arithmetic with
// an explicit width==64 guard, and rejection when the address width cannot
// hold the derived offset + index bits.

#include "geometry.hpp"

#include <string>
#include <vector>

using json = nlohmann::json;

namespace engine {
namespace {

// v > 0 and a power of two (validated upstream), so the loop terminates.
int ctz_shift_count(std::uint64_t v) {
  int n = 0;
  while ((v & 1ULL) == 0) {
    ++n;
    v >>= 1;
  }
  return n;
}

}  // namespace

bool derive_geometry(const Config& config, Geometry* out,
                     std::vector<ValidationIssue>* issues) {
  out->offset_bits = ctz_shift_count(config.block_size_bytes);
  out->lines = config.capacity_bytes / config.block_size_bytes;
  std::uint64_t sets = 1;
  if (config.organization == "direct") {
    sets = out->lines;
  } else if (config.organization == "set_associative") {
    sets = config.capacity_bytes /
           (config.block_size_bytes * config.associativity);
  }
  out->sets = sets;
  out->index_bits = ctz_shift_count(sets);

  const std::uint64_t needed =
      static_cast<std::uint64_t>(out->offset_bits) +
      static_cast<std::uint64_t>(out->index_bits);
  const std::uint64_t width =
      static_cast<std::uint64_t>(config.address_width_bits);
  if (width < needed) {
    ValidationIssue issue;
    issue.field = "address_width_bits";
    issue.problem =
        "address_width_bits (" + std::to_string(config.address_width_bits) +
        ") is too small: the derived geometry needs offset_bits (" +
        std::to_string(out->offset_bits) + ") + index_bits (" +
        std::to_string(out->index_bits) + ") = " + std::to_string(needed) +
        " bits, leaving no bits for the tag";
    issue.received = config.address_width_bits;
    issues->push_back(issue);
    return false;
  }
  out->tag_bits = config.address_width_bits - out->offset_bits - out->index_bits;
  out->index_field_present = (config.organization != "fully_associative");
  out->max_address = (config.address_width_bits == 64)
                         ? 0xFFFFFFFFFFFFFFFFULL
                         : ((1ULL << config.address_width_bits) - 1ULL);
  return true;
}

json geometry_to_json(const Geometry& geometry, const Config& config) {
  json j;
  j["capacity_bytes"] = config.capacity_bytes;
  j["block_size_bytes"] = config.block_size_bytes;
  j["organization"] = config.organization;
  j["associativity"] = (config.organization == "set_associative")
                           ? json(config.associativity)
                           : json(nullptr);
  j["address_width_bits"] = config.address_width_bits;
  j["lines"] = geometry.lines;
  j["sets"] = geometry.sets;
  j["offset_bits"] = geometry.offset_bits;
  j["index_bits"] = geometry.index_bits;
  j["tag_bits"] = geometry.tag_bits;
  j["index_field_present"] = geometry.index_field_present;
  j["max_address"] = geometry.max_address;
  return j;
}

json issues_to_json(const std::vector<ValidationIssue>& issues) {
  json arr = json::array();
  for (const auto& issue : issues) {
    arr.push_back(
        json{{"field", issue.field}, {"problem", issue.problem},
             {"received", issue.received}});
  }
  return arr;
}

}  // namespace engine
