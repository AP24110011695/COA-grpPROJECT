// Summary statistics (architecture.md 6.6): AMAT modeling, trace digest
// (FIPS 180-4 SHA-256, verified against the standard test vectors), and the
// complete summary object. Full precision is kept in the engine; display
// rounding happens only in the UI (prd.md 7).

#include "stats.hpp"

#include <cstring>
#include <string>
#include <vector>

#include "textutil.hpp"

using json = nlohmann::json;

namespace engine {
namespace {

// Minimal FIPS 180-4 SHA-256. The algorithm is fully specified by the
// standard; correctness is pinned by the canonical vectors (empty string,
// "abc") in engine_tests and cross-checked against Python hashlib in pytest.
class Sha256 {
 public:
  Sha256() { reset(); }

  void reset() {
    h_[0] = 0x6a09e667; h_[1] = 0xbb67ae85; h_[2] = 0x3c6ef372;
    h_[3] = 0xa54ff53a; h_[4] = 0x510e527f; h_[5] = 0x9b05688c;
    h_[6] = 0x1f83d9ab; h_[7] = 0x5be0cd19;
    len_ = 0;
    buf_len_ = 0;
  }

  void update(const unsigned char* data, std::size_t n) {
    len_ += n;
    while (n > 0) {
      const std::size_t take = (64 - buf_len_) < n ? (64 - buf_len_) : n;
      std::memcpy(buf_ + buf_len_, data, take);
      buf_len_ += take;
      data += take;
      n -= take;
      if (buf_len_ == 64) {
        compress(buf_);
        buf_len_ = 0;
      }
    }
  }

  std::string hex() {
    const std::uint64_t bit_len = len_ * 8;
    const unsigned char one = 0x80;
    const unsigned char zero = 0x00;
    update(&one, 1);
    while (buf_len_ != 56) update(&zero, 1);
    unsigned char len_bytes[8];
    for (int i = 0; i < 8; ++i) {
      len_bytes[i] =
          static_cast<unsigned char>((bit_len >> (56 - 8 * i)) & 0xff);
    }
    update(len_bytes, 8);
    static const char* kHex = "0123456789abcdef";
    std::string out;
    out.reserve(64);
    for (int i = 0; i < 8; ++i) {
      for (int j = 28; j >= 0; j -= 4) {
        out += kHex[(h_[i] >> j) & 0xf];
      }
    }
    return out;
  }

 private:
  static std::uint32_t rotr(std::uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
  }

  void compress(const unsigned char* p) {
    static const std::uint32_t k[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b,
        0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
        0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7,
        0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152,
        0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
        0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
        0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
        0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f,
        0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
    std::uint32_t w[64];
    for (int i = 0; i < 16; ++i) {
      w[i] = (static_cast<std::uint32_t>(p[4 * i]) << 24) |
             (static_cast<std::uint32_t>(p[4 * i + 1]) << 16) |
             (static_cast<std::uint32_t>(p[4 * i + 2]) << 8) |
             static_cast<std::uint32_t>(p[4 * i + 3]);
    }
    for (int i = 16; i < 64; ++i) {
      const std::uint32_t s0 =
          rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
      const std::uint32_t s1 =
          rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
      w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    std::uint32_t a = h_[0], b = h_[1], c = h_[2], d = h_[3];
    std::uint32_t e = h_[4], f = h_[5], g = h_[6], h = h_[7];
    for (int i = 0; i < 64; ++i) {
      const std::uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const std::uint32_t ch = (e & f) ^ (~e & g);
      const std::uint32_t t1 = h + S1 + ch + k[i] + w[i];
      const std::uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
      const std::uint32_t t2 = S0 + maj;
      h = g; g = f; f = e;
      e = d + t1;
      d = c; c = b; b = a;
      a = t1 + t2;
    }
    h_[0] += a; h_[1] += b; h_[2] += c; h_[3] += d;
    h_[4] += e; h_[5] += f; h_[6] += g; h_[7] += h;
  }

  std::uint32_t h_[8];
  unsigned char buf_[64];
  std::size_t buf_len_;
  std::uint64_t len_;
};

}  // namespace

std::string sha256_hex(const std::string& data) {
  Sha256 s;
  s.update(reinterpret_cast<const unsigned char*>(data.data()), data.size());
  return s.hex();
}

std::string trace_sha256(const std::vector<std::uint64_t>& addresses) {
  // Canonical string "addresses:" + comma-joined decimals. Built with
  // in-place appends (no per-address temporaries — see textutil.hpp).
  std::string canonical;
  canonical.reserve(10 + addresses.size() * 11);
  canonical += "addresses:";
  for (std::size_t i = 0; i < addresses.size(); ++i) {
    if (i != 0) canonical += ",";
    append_u64(canonical, addresses[i]);
  }
  return sha256_hex(canonical);
}

json build_summary(const Config& config, const SimulateCounts& counts,
                   std::uint64_t rng_draws,
                   const std::vector<std::uint64_t>& addresses) {
  json s;
  s["accesses"] = counts.accesses;
  s["hits"] = counts.hits;
  s["misses"] = counts.misses;
  s["evictions"] = counts.evictions;
  if (counts.accesses == 0) {
    s["hit_rate"] = nullptr;  // empty trace: rates are null, never 0/1
    s["miss_rate"] = nullptr;
  } else {
    const double total = static_cast<double>(counts.accesses);
    s["hit_rate"] = static_cast<double>(counts.hits) / total;
    s["miss_rate"] = static_cast<double>(counts.misses) / total;
  }
  if (config.has_hit_time && config.has_miss_penalty) {
    // AMAT = hit_time + miss_rate x miss_penalty (prd.md 7). For an empty
    // trace the modeled miss rate is 0, so the value degenerates to
    // hit_time (decision D-19).
    const double miss_rate =
        counts.accesses == 0
            ? 0.0
            : static_cast<double>(counts.misses) /
                  static_cast<double>(counts.accesses);
    s["amat"] = json{{"hit_time", config.hit_time},
                     {"miss_penalty", config.miss_penalty},
                     {"value", config.hit_time + miss_rate * config.miss_penalty},
                     {"unit", "cycles"}};
  }
  // No timing inputs: `amat` is omitted entirely — never emitted as null
  // (AC-P4.4, architecture.md 6.6).
  if (!config.has_policy) {
    // direct-mapped: no policy to report (architecture.md 6.6)
  } else if (config.policy == "RANDOM") {
    s["replacement_meta"] = json{{"policy", "RANDOM"},
                                 {"seed", config.seed},
                                 {"rng_draws", rng_draws}};
  } else {
    s["replacement_meta"] = json{{"policy", config.policy}};
  }
  s["trace_sha256"] = trace_sha256(addresses);
  return s;
}

}  // namespace engine
