#pragma once

// Seeded, deterministic RNG (architecture.md 8.3; decisions D-5, D-15):
// a single std::mt19937 seeded once per run with the config seed. Exactly
// one uint32 draw is consumed per valid-line eviction and never otherwise
// (invalid-line fills and hits consume no draws), so identical
// config+trace+seed reproduce identical results.

#include <cstdint>
#include <random>

namespace engine {

class SeededRandom {
 public:
  explicit SeededRandom(std::uint32_t seed) : rng_(seed), draws_(0) {}

  std::uint32_t draw() {
    ++draws_;
    return static_cast<std::uint32_t>(rng_());
  }

  std::uint64_t draws_used() const { return draws_; }

 private:
  std::mt19937 rng_;
  std::uint64_t draws_;
};

}  // namespace engine
