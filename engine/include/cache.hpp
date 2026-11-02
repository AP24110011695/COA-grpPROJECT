#pragma once

// Cache line/set storage, replacement-policy strategy, and state-level
// checks (architecture.md 8). Read-only simulator: no dirty bits or write
// state anywhere.

#include <cstddef>
#include <cstdint>
#include <vector>

#include "config.hpp"
#include "rng.hpp"

namespace engine {

// Replacement policy for a run (architecture.md 8.3). Direct-mapped caches
// have no selectable policy (kNone: single-way forced eviction).
enum class Policy { kNone, kLru, kFifo, kRandom };

struct CacheLine {
  bool valid = false;
  std::uint64_t tag = 0;
  std::uint64_t block = 0;
  std::uint64_t stamp_used = 0;    // updated on every hit and fill (LRU)
  std::uint64_t stamp_insert = 0;  // set on fill only (FIFO insertion order)
};

// Flat per-set storage: sets[s] holds ways_per_set lines (architecture.md 12).
struct CacheState {
  std::vector<std::vector<CacheLine>> sets;
};

struct SimulateCounts {
  std::uint64_t accesses = 0;
  std::uint64_t hits = 0;
  std::uint64_t misses = 0;
  std::uint64_t evictions = 0;
};

Policy policy_from_config(const Config& config);

// Selects the victim way in a set whose ways are ALL valid (the caller
// guarantees it — an invalid way is always filled first, architecture.md
// 8.2). kNone returns way 0 (forced); kLru/kFifo scan stamps; kRandom
// consumes exactly one RNG draw and returns draw % ways_in_set, where
// ways_in_set is the geometry-derived way count of the set.
std::size_t select_victim(Policy policy,
                          const std::vector<CacheLine>& ways,
                          SeededRandom* rng);

// Internal consistency checks (architecture.md 9). Returns false on any
// violation — that is an engine bug, never a user error.
bool verify_invariants(const CacheState& state, const SimulateCounts& counts);

}  // namespace engine
