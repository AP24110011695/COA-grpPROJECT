#pragma once

// Tiny string utilities shared by the simulator and the stats module.
// On the verified environment, temporary std::to_string/concatenation
// chains dominate runtime at the 100,000-access scale (NFR-2), so hot paths
// format numbers into a reused buffer and append in place — one
// allocation for the string's capacity, none for the digits.

#include <cstdint>
#include <string>

namespace engine {

// Appends the decimal representation of v to out without allocating.
inline void append_u64(std::string& out, std::uint64_t v) {
  char buf[20];
  int i = 20;
  do {
    buf[--i] = static_cast<char>('0' + (v % 10));
    v /= 10;
  } while (v != 0);
  out.append(buf + i, static_cast<std::size_t>(20 - i));
}

}  // namespace engine
