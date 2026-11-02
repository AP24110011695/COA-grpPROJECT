// Cache storage helpers: replacement-policy strategy (architecture.md 8.3)
// and internal invariant verification (architecture.md 9).

#include "cache.hpp"

namespace engine {

Policy policy_from_config(const Config& config) {
  if (config.organization == "direct" || !config.has_policy) {
    return Policy::kNone;
  }
  if (config.policy == "FIFO") return Policy::kFifo;
  if (config.policy == "RANDOM") return Policy::kRandom;
  return Policy::kLru;
}

std::size_t select_victim(Policy policy,
                          const std::vector<CacheLine>& ways,
                          SeededRandom* rng) {
  switch (policy) {
    case Policy::kRandom: {
      // One draw per valid-line eviction; victim = draw % ways_in_set.
      const std::uint32_t draw = rng->draw();
      return static_cast<std::size_t>(draw % ways.size());
    }
    case Policy::kFifo: {
      // Oldest insertion wins; hits never touch stamp_insert, so this is
      // pure FIFO regardless of recency.
      std::size_t victim = 0;
      for (std::size_t w = 1; w < ways.size(); ++w) {
        if (ways[w].stamp_insert < ways[victim].stamp_insert) victim = w;
      }
      return victim;
    }
    case Policy::kLru: {
      // Least recently used; stamps are unique so there are no ties.
      std::size_t victim = 0;
      for (std::size_t w = 1; w < ways.size(); ++w) {
        if (ways[w].stamp_used < ways[victim].stamp_used) victim = w;
      }
      return victim;
    }
    case Policy::kNone:
    default:
      return 0;  // direct-mapped: single-way forced eviction
  }
}

bool verify_invariants(const CacheState& state, const SimulateCounts& counts) {
  if (counts.hits + counts.misses != counts.accesses) return false;
  if (counts.evictions > counts.misses) return false;
  for (const auto& set : state.sets) {
    std::uint64_t valid_count = 0;
    for (std::size_t i = 0; i < set.size(); ++i) {
      if (!set[i].valid) continue;
      ++valid_count;
      for (std::size_t j = i + 1; j < set.size(); ++j) {
        if (!set[j].valid) continue;
        // Two valid lines in one set must never hold the same tag.
        if (set[j].tag == set[i].tag) return false;
        // architecture.md 9 (5): stamps come from one strictly increasing
        // counter, so valid lines must have distinct stamps — ties would
        // make LRU/FIFO victim selection ambiguous.
        if (set[j].stamp_used == set[i].stamp_used) return false;
        if (set[j].stamp_insert == set[i].stamp_insert) return false;
      }
    }
    if (valid_count > set.size()) return false;
  }
  return true;
}

}  // namespace engine
