#pragma once

// Summary statistics (architecture.md 6.6): counts, full-precision rates,
// the AMAT modeling assumption, replacement_meta, and the trace digest.

#include <cstdint>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "cache.hpp"
#include "config.hpp"

namespace engine {

// SHA-256 over the canonical trace string "addresses:" + comma-joined
// decimal addresses (architecture.md 6.6). Lowercase hex. The underlying
// sha256_hex is exported for the standard test vectors.
std::string trace_sha256(const std::vector<std::uint64_t>& addresses);
std::string sha256_hex(const std::string& data);

// Builds the complete summary object: counts, rates (null on an empty
// trace), amat (null unless both timing inputs were supplied; for an empty
// trace the modeled miss rate is 0, so the value degenerates to hit_time —
// decision D-19), replacement_meta (RANDOM: policy+seed+rng_draws;
// LRU/FIFO: policy; omitted for direct-mapped), and trace_sha256.
nlohmann::json build_summary(const Config& config, const SimulateCounts& counts,
                             std::uint64_t rng_draws,
                             const std::vector<std::uint64_t>& addresses);

}  // namespace engine
