// Simulation core (architecture.md 8): exact fill/eviction semantics for
// LRU, FIFO, and seeded RANDOM (plus direct-mapped forced eviction),
// decomposition, per-access events, final state, and serialization.
// Summary statistics live in stats.cpp (build_summary).

#include "simulator.hpp"

#include <algorithm>
#include <string>
#include <vector>

#include "textutil.hpp"

using json = nlohmann::json;

namespace engine {
namespace {

constexpr std::uint64_t kMaxTraceAddresses = 100000;
constexpr std::size_t kMaxCollectedAddressIssues = 10;
constexpr const char* kKnownTraceFields[] = {"name", "addresses"};

// Decimal formatting for (cold) validation messages. The hot simulation
// loop uses engine::append_u64 instead (textutil.hpp) — see D-20.
std::string num(std::uint64_t v) { return std::to_string(v); }

}  // namespace

TraceValidation validate_trace(const json& trace, std::uint64_t max_address) {
  TraceValidation r;
  if (!trace.is_object()) {
    add_issue(&r.issues, "trace", "must be a JSON object", trace);
    return r;
  }
  for (auto it = trace.begin(); it != trace.end(); ++it) {
    bool known = false;
    for (const char* k : kKnownTraceFields) {
      if (it.key() == k) {
        known = true;
        break;
      }
    }
    if (!known) {
      add_issue(&r.issues, it.key(), "unknown field (typo or unsupported)",
                *it);
    }
  }
  const auto name_it = trace.find("name");
  if (name_it == trace.end() || !name_it->is_string() ||
      name_it->get<std::string>().empty()) {
    add_issue(&r.issues, "name", "must be a non-empty string",
              name_it == trace.end() ? json(nullptr) : *name_it);
  } else {
    r.trace.name = name_it->get<std::string>();
  }
  const auto addr_it = trace.find("addresses");
  if (addr_it == trace.end() || !addr_it->is_array()) {
    add_issue(&r.issues, "addresses", "must be an array of integers",
              addr_it == trace.end() ? json(nullptr) : *addr_it);
    return r;
  }
  if (addr_it->size() > kMaxTraceAddresses) {
    add_issue(&r.issues, "addresses",
              "trace length " + num(addr_it->size()) +
                  " exceeds the 100000-address limit",
              addr_it->size());
    ++r.limit_problems;
  }
  std::size_t collected = 0;
  std::size_t total_bad = 0;
  for (std::size_t i = 0; i < addr_it->size(); ++i) {
    const json& a = (*addr_it)[i];
    std::uint64_t v = 0;
    if (!get_non_negative_int(a, &v) || v > max_address) {
      ++total_bad;
      if (collected < kMaxCollectedAddressIssues) {
        add_issue(&r.issues, "addresses[" + num(i) + "]",
                  "must be an integer between 0 and max_address (" +
                      num(max_address) + ")",
                  a);
        ++collected;
      }
    } else {
      r.trace.addresses.push_back(v);
    }
  }
  if (total_bad > collected) {
    add_issue(&r.issues, "addresses",
              "further address problems truncated (" +
                  num(total_bad - collected) + " more)",
              nullptr);
  }
  r.ok = r.issues.empty();
  return r;
}

bool simulate(const Config& config, const Geometry& geometry,
              const std::vector<std::uint64_t>& addresses,
              bool include_state_after_each, SimulateResult* out) {
  const std::uint64_t block_size = config.block_size_bytes;
  const std::uint64_t sets = geometry.sets;
  const std::uint64_t ways =
      config.organization == "direct"
          ? 1ULL
          : (config.organization == "set_associative" ? config.associativity
                                                      : geometry.lines);
  const bool is_direct = config.organization == "direct";
  const Policy policy = policy_from_config(config);
  // One RNG per run, seeded once; consumed only by RANDOM evictions.
  SeededRandom rng(config.has_seed ? config.seed : 0u);

  out->final_state.sets.assign(
      static_cast<std::size_t>(sets), std::vector<CacheLine>(
          static_cast<std::size_t>(ways)));
  CacheState& st = out->final_state;
  out->counts.accesses = addresses.size();
  out->events.reserve(addresses.size());
  out->snapshots = json::array();
  std::uint64_t stamp = 0;

  for (std::uint64_t i = 0; i < addresses.size(); ++i) {
    SimulateEvent e;
    e.n = i + 1;
    e.address = addresses[i];
    e.offset = e.address & (block_size - 1);
    const std::uint64_t block = e.address >> geometry.offset_bits;
    e.block = block;
    e.set = block & (sets - 1);  // sets = 1 yields 0 (architecture.md 7)
    e.tag = block >> geometry.index_bits;
    e.has_index = config.organization != "fully_associative";
    e.index = e.set;

    std::vector<CacheLine>& lines = st.sets[static_cast<std::size_t>(e.set)];
    std::size_t hit_way = lines.size();
    for (std::size_t w = 0; w < lines.size(); ++w) {
      if (lines[w].valid && lines[w].tag == e.tag) {
        hit_way = w;
        break;
      }
    }

    if (hit_way < lines.size()) {
      e.hit = true;
      e.way = hit_way;
      lines[hit_way].stamp_used = ++stamp;
      e.explanation.reserve(80);
      e.explanation += "Hit: block ";
      append_u64(e.explanation, e.block);
      e.explanation += " found in set ";
      append_u64(e.explanation, e.set);
      e.explanation += " way ";
      append_u64(e.explanation, hit_way);
      e.explanation += " (tag ";
      append_u64(e.explanation, e.tag);
      e.explanation += ").";
      ++out->counts.hits;
    } else {
      e.loaded = true;
      // Fill the lowest-indexed invalid way before any eviction
      // (architecture.md 8.2).
      std::size_t fill_way = lines.size();
      for (std::size_t w = 0; w < lines.size(); ++w) {
        if (!lines[w].valid) {
          fill_way = w;
          break;
        }
      }
      if (fill_way < lines.size()) {
        CacheLine& line = lines[fill_way];
        line.valid = true;
        line.tag = e.tag;
        line.block = block;
        line.stamp_used = ++stamp;
        line.stamp_insert = line.stamp_used;
        e.way = fill_way;
        e.explanation.reserve(80);
        e.explanation += "Miss: block ";
        append_u64(e.explanation, e.block);
        e.explanation += " loaded into set ";
        append_u64(e.explanation, e.set);
        e.explanation += " way ";
        append_u64(e.explanation, fill_way);
        e.explanation += " (empty line).";
      } else {
        // All ways valid: victim selection (architecture.md 8.3) — forced
        // way 0 for direct-mapped, LRU/FIFO stamps, or one RANDOM draw.
        const std::size_t victim = select_victim(policy, lines, &rng);
        CacheLine& line = lines[victim];
        e.evicted_valid = true;
        e.evicted_block = line.block;
        e.evicted_tag = line.tag;
        e.evicted_way = victim;
        line.tag = e.tag;
        line.block = block;
        line.stamp_used = ++stamp;
        line.stamp_insert = line.stamp_used;
        e.way = victim;
        const char* why = is_direct ? "direct"
                                    : (policy == Policy::kFifo
                                           ? "FIFO"
                                           : (policy == Policy::kRandom
                                                  ? "Random"
                                                  : "LRU"));
        e.explanation.reserve(96);
        e.explanation += "Miss: block ";
        append_u64(e.explanation, e.block);
        e.explanation += " loaded into set ";
        append_u64(e.explanation, e.set);
        e.explanation += " way ";
        append_u64(e.explanation, victim);
        e.explanation += ", evicting block ";
        append_u64(e.explanation, e.evicted_block);
        e.explanation += " (";
        e.explanation += why;
        e.explanation += ").";
        ++out->counts.evictions;
      }
      ++out->counts.misses;
    }
    out->events.push_back(e);
    if (include_state_after_each) {
      json snap;
      snap["n"] = e.n;
      snap["sets"] = state_to_json(st, json::array(), policy, false)["sets"];
      out->snapshots.push_back(snap);
    }
  }
  out->rng_draws = rng.draws_used();
  out->snapshots_requested = include_state_after_each;
  return verify_invariants(st, out->counts);
}

json event_to_json(const SimulateEvent& e, const Config& config) {
  json ev;
  ev["n"] = e.n;
  ev["address"] = e.address;
  ev["block"] = e.block;
  ev["tag"] = e.tag;
  ev["index"] = e.has_index ? json(e.index) : json(nullptr);
  ev["offset"] = e.offset;
  ev["set"] = e.set;
  ev["way"] = e.way;
  ev["result"] = e.hit ? "hit" : "miss";
  ev["loaded"] = e.loaded;
  if (e.evicted_valid) {
    ev["evicted"] = json{{"block", e.evicted_block},
                         {"tag", e.evicted_tag},
                         {"way", e.evicted_way}};
  } else {
    ev["evicted"] = nullptr;
  }
  const bool is_direct = config.organization == "direct";
  json meta;
  meta["policy"] = is_direct ? json(nullptr) : json(config.policy);
  const char* selection = "none";
  if (e.evicted_valid) {
    selection = is_direct
                    ? "forced"
                    : (config.policy == "FIFO"
                           ? "fifo_oldest"
                           : (config.policy == "RANDOM" ? "random" : "lru"));
  }
  meta["victim_selection"] = selection;
  if (e.evicted_valid && !is_direct && config.policy == "RANDOM") {
    meta["seed"] = config.seed;  // RANDOM evictions record the seed
  }
  ev["policy_meta"] = meta;
  ev["explanation"] = e.explanation;
  return ev;
}

json state_to_json(const CacheState& state, const json& snapshots,
                   Policy policy, bool snapshots_requested) {
  json sets = json::array();
  for (const auto& lines : state.sets) {
    // Ranks among the valid lines of this set (architecture.md 6.7):
    // LRU (and direct-mapped) report last_used_rank (1 = most recent);
    // FIFO reports insert_order_rank (1 = oldest inserted); RANDOM reports
    // neither.
    const bool emit_used = policy == Policy::kLru || policy == Policy::kNone;
    const bool emit_insert = policy == Policy::kFifo;
    std::vector<std::pair<std::uint64_t, std::size_t>> used;
    std::vector<std::pair<std::uint64_t, std::size_t>> inserted;
    for (std::size_t w = 0; w < lines.size(); ++w) {
      if (!lines[w].valid) continue;
      if (emit_used) used.emplace_back(lines[w].stamp_used, w);
      if (emit_insert) inserted.emplace_back(lines[w].stamp_insert, w);
    }
    std::sort(used.begin(), used.end(),
              [](const auto& a, const auto& b) { return a.first > b.first; });
    std::sort(inserted.begin(), inserted.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });
    std::vector<std::uint64_t> used_rank(lines.size(), 0);
    for (std::size_t r = 0; r < used.size(); ++r) {
      used_rank[used[r].second] = r + 1;
    }
    std::vector<std::uint64_t> insert_rank(lines.size(), 0);
    for (std::size_t r = 0; r < inserted.size(); ++r) {
      insert_rank[inserted[r].second] = r + 1;
    }
    json ways_json = json::array();
    for (std::size_t w = 0; w < lines.size(); ++w) {
      const CacheLine& line = lines[w];
      json l;
      l["way"] = w;
      l["valid"] = line.valid;
      l["tag"] = line.valid ? json(line.tag) : json(nullptr);
      l["block"] = line.valid ? json(line.block) : json(nullptr);
      l["last_used_rank"] =
          (line.valid && emit_used) ? json(used_rank[w]) : json(nullptr);
      l["insert_order_rank"] =
          (line.valid && emit_insert) ? json(insert_rank[w]) : json(nullptr);
      ways_json.push_back(l);
    }
    sets.push_back(ways_json);
  }
  json s;
  s["sets"] = sets;
  // snapshots semantics (architecture.md 6.7): an empty array means the
  // option was requested and zero snapshots were captured (empty trace);
  // null would wrongly tell consumers that snapshots were not requested.
  s["snapshots"] = snapshots_requested ? snapshots : json(nullptr);
  return s;
}

}  // namespace engine
