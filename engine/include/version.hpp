#pragma once

// Engine identity, embedded in every envelope and report
// (architecture.md §6.2). Any change to simulation semantics bumps the
// version and is recorded in memory.md (decision D-10).

namespace engine {

constexpr const char* kName = "cache_sim";
constexpr const char* kVersion = "0.1.0";

}  // namespace engine
