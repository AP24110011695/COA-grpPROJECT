// cache_sim — COA cache simulator engine.
//
// Phase 3: all three modes (version / geometry / simulate) are implemented.
// simulate runs LRU wherever a policy exists (direct-mapped has none);
// FIFO/RANDOM, AMAT, and the trace digest arrive in Phase 4.
//
// Contract (architecture.md 5): stdout carries only the JSON envelope
// (unless --out is given, in which case stdout stays empty); diagnostics go
// to stderr. Exit codes: 0 ok, 2 usage, 3 validation, 4 internal.
// Filesystem contract (architecture.md 5.1): reads only --in (or stdin),
// writes only --out (or stdout); no other filesystem, network, or
// environment access.

#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "cache.hpp"
#include "config.hpp"
#include "geometry.hpp"
#include "simulator.hpp"
#include "stats.hpp"
#include "version.hpp"

using json = nlohmann::json;

namespace {

constexpr const char* kUsage =
    "usage: cache_sim --mode {simulate|geometry|version} [--in FILE] [--out FILE]";

constexpr int kExitOk = 0;
constexpr int kExitUsage = 2;
constexpr int kExitValidation = 3;
constexpr int kExitInternal = 4;

json engine_meta() {
  return json{{"name", engine::kName}, {"version", engine::kVersion}};
}

json error_envelope(const std::string& code, const std::string& message,
                    json details = json::array()) {
  json env = json::object();
  env["ok"] = false;
  env["engine"] = engine_meta();
  env["error"] = json{{"code", code},
                      {"message", message},
                      {"details", std::move(details)}};
  return env;
}

json success_envelope() {
  json env = json::object();
  env["ok"] = true;
  env["engine"] = engine_meta();
  return env;
}

// Writes the envelope to stdout or to the --out file. Returns false when the
// output file could not be opened (an E_USAGE envelope has then already been
// sent to stdout so the caller never exits without emitting a contract
// envelope).
bool emit(const json& envelope, const std::string& out_path) {
  if (out_path.empty()) {
    std::cout << envelope.dump() << "\n";
    return true;
  }
  std::ofstream out(out_path, std::ios::binary);
  if (!out) {
    std::cerr << "cache_sim: cannot open output file: " << out_path << "\n";
    std::cout << error_envelope("E_USAGE",
                                "cannot open output file: " + out_path)
                     .dump()
              << "\n";
    return false;
  }
  out << envelope.dump() << "\n";
  return out.good();
}

std::string read_all(std::istream& in) {
  return std::string(std::istreambuf_iterator<char>(in),
                     std::istreambuf_iterator<char>());
}

// Reads the --in file (or stdin). Returns false (with an E_USAGE envelope
// already emitted) when the input file cannot be opened.
bool read_input(const std::string& in_path, const std::string& out_path,
                std::string* text) {
  if (in_path.empty()) {
    *text = read_all(std::cin);
    return true;
  }
  std::ifstream in(in_path, std::ios::binary);
  if (!in) {
    emit(error_envelope("E_USAGE", "cannot read input file: " + in_path),
         out_path);
    return false;
  }
  *text = read_all(in);
  return true;
}

struct Options {
  std::string mode;
  std::string in_path;
  std::string out_path;
};

bool parse_args(int argc, char** argv, Options* opts, std::string* error) {
  for (int i = 1; i < argc; ++i) {
    const std::string flag = argv[i];
    std::string* target = nullptr;
    if (flag == "--mode") {
      target = &opts->mode;
    } else if (flag == "--in") {
      target = &opts->in_path;
    } else if (flag == "--out") {
      target = &opts->out_path;
    } else {
      *error = std::string("unknown flag: ") + flag + "; " + kUsage;
      return false;
    }
    if (i + 1 >= argc) {
      *error = std::string("missing value for ") + flag + "; " + kUsage;
      return false;
    }
    const std::string value = argv[++i];
    if (!target->empty()) {
      *error = std::string("duplicate flag: ") + flag + "; " + kUsage;
      return false;
    }
    *target = value;
  }
  return true;
}

// geometry mode: validate the config and report derived geometry
// (architecture.md 5.1, 6.3). Returns the process exit code.
int run_geometry(const Options& opts) {
  std::string text;
  if (!read_input(opts.in_path, opts.out_path, &text)) {
    return kExitUsage;
  }
  const json parsed = json::parse(text, nullptr, false);
  if (parsed.is_discarded()) {
    emit(error_envelope("E_JOB_INVALID", "input is not valid JSON"),
         opts.out_path);
    return kExitValidation;
  }
  std::vector<engine::ValidationIssue> issues;
  engine::Config config;
  if (!engine::parse_and_validate_config(parsed, &config, &issues)) {
    emit(error_envelope("E_CONFIG_INVALID",
                        "configuration validation failed with " +
                            std::to_string(issues.size()) + " problem(s)",
                        engine::issues_to_json(issues)),
         opts.out_path);
    return kExitValidation;
  }
  engine::Geometry geometry;
  if (!engine::derive_geometry(config, &geometry, &issues)) {
    emit(error_envelope("E_CONFIG_INVALID",
                        "configuration validation failed with " +
                            std::to_string(issues.size()) + " problem(s)",
                        engine::issues_to_json(issues)),
         opts.out_path);
    return kExitValidation;
  }
  json envelope = success_envelope();
  envelope["echo"] = parsed;
  envelope["geometry"] = engine::geometry_to_json(geometry, config);
  emit(envelope, opts.out_path);
  return kExitOk;
}

// simulate mode: validate the job (config + trace + options) and run the
// trace through the engine (architecture.md 6.4-6.7). Validation is staged:
// job shape -> config -> geometry -> trace -> options, each reporting all of
// its own problems. Returns the process exit code.
int run_simulate(const Options& opts) {
  std::string text;
  if (!read_input(opts.in_path, opts.out_path, &text)) {
    return kExitUsage;
  }
  const json parsed = json::parse(text, nullptr, false);
  if (parsed.is_discarded()) {
    emit(error_envelope("E_JOB_INVALID", "input is not valid JSON"),
         opts.out_path);
    return kExitValidation;
  }
  if (!parsed.is_object()) {
    emit(error_envelope("E_JOB_INVALID", "job must be a JSON object"),
         opts.out_path);
    return kExitValidation;
  }

  // Stage 1: job shape (unknown keys, required members).
  std::vector<engine::ValidationIssue> issues;
  static const char* const kKnownJobFields[] = {"config", "trace", "options"};
  for (auto it = parsed.begin(); it != parsed.end(); ++it) {
    bool known = false;
    for (const char* k : kKnownJobFields) {
      if (it.key() == k) {
        known = true;
        break;
      }
    }
    if (!known) {
      engine::add_issue(&issues, it.key(), "unknown field (typo or unsupported)",
                        *it);
    }
  }
  const auto cfg_it = parsed.find("config");
  const auto trace_it = parsed.find("trace");
  if (cfg_it == parsed.end()) {
    engine::add_issue(&issues, "config", "is required", nullptr);
  }
  if (trace_it == parsed.end()) {
    engine::add_issue(&issues, "trace", "is required", nullptr);
  }
  const bool options_present = parsed.find("options") != parsed.end();
  if (!issues.empty()) {
    emit(error_envelope("E_JOB_INVALID",
                        "job validation failed with " +
                            std::to_string(issues.size()) + " problem(s)",
                        engine::issues_to_json(issues)),
         opts.out_path);
    return kExitValidation;
  }

  // Stage 2+3: config validation and geometry derivation.
  std::vector<engine::ValidationIssue> config_issues;
  engine::Config config;
  if (!engine::parse_and_validate_config(*cfg_it, &config, &config_issues)) {
    emit(error_envelope("E_CONFIG_INVALID",
                        "configuration validation failed with " +
                            std::to_string(config_issues.size()) +
                            " problem(s)",
                        engine::issues_to_json(config_issues)),
         opts.out_path);
    return kExitValidation;
  }
  engine::Geometry geometry;
  if (!engine::derive_geometry(config, &geometry, &config_issues)) {
    emit(error_envelope("E_CONFIG_INVALID",
                        "configuration validation failed with " +
                            std::to_string(config_issues.size()) +
                            " problem(s)",
                        engine::issues_to_json(config_issues)),
         opts.out_path);
    return kExitValidation;
  }

  // Stage 4: trace validation (E_LIMIT takes precedence over
  // E_TRACE_INVALID when both classes of problem exist).
  std::vector<engine::ValidationIssue> trace_issues;
  engine::TraceValidation tv =
      engine::validate_trace(*trace_it, geometry.max_address);
  if (!tv.ok) {
    const char* code = tv.limit_problems > 0 ? "E_LIMIT" : "E_TRACE_INVALID";
    emit(error_envelope(code,
                        "trace validation failed with " +
                            std::to_string(tv.issues.size()) + " problem(s)",
                        engine::issues_to_json(tv.issues)),
         opts.out_path);
    return kExitValidation;
  }

  // Stage 5: options.
  bool include_state_after_each = false;
  if (options_present) {
    const json& options = parsed["options"];
    if (!options.is_object()) {
      std::vector<engine::ValidationIssue> opt_issues;
      engine::add_issue(&opt_issues, "options", "must be a JSON object",
                        options);
      emit(error_envelope("E_JOB_INVALID", "options must be a JSON object",
                          engine::issues_to_json(opt_issues)),
           opts.out_path);
      return kExitValidation;
    }
    const auto inc = options.find("include_state_after_each");
    if (inc != options.end()) {
      if (!inc->is_boolean()) {
        std::vector<engine::ValidationIssue> opt_issues;
        engine::add_issue(&opt_issues, "options.include_state_after_each",
                          "must be a boolean", *inc);
        emit(error_envelope("E_JOB_INVALID",
                            "options validation failed",
                            engine::issues_to_json(opt_issues)),
             opts.out_path);
        return kExitValidation;
      }
      include_state_after_each = inc->get<bool>();
    }
    // Unknown option keys are ignored (architecture.md 6.4).
  }
  if (include_state_after_each) {
    // Cap: per-access snapshots are allowed only for traces of at most
    // 2,000 addresses (architecture.md 12).
    const std::uint64_t trace_len =
        static_cast<std::uint64_t>(tv.trace.addresses.size());
    if (trace_len > 2000ULL) {
      std::vector<engine::ValidationIssue> lim;
      engine::add_issue(&lim, "options.include_state_after_each",
                        "per-access snapshots are limited to traces of at "
                        "most 2000 addresses (got " +
                            std::to_string(trace_len) + ")",
                        trace_len);
      emit(error_envelope("E_LIMIT",
                          "per-access snapshot trace-length cap exceeded",
                          engine::issues_to_json(lim)),
           opts.out_path);
      return kExitValidation;
    }
    // Snapshot budget: serializing the full state per access is bounded by
    // snapshots x total cache lines (architecture.md 12).
    const std::uint64_t total_lines = geometry.lines;
    const std::uint64_t snapshot_work =
        total_lines * trace_len;
    if (snapshot_work > 2000000ULL) {
      std::vector<engine::ValidationIssue> lim;
      engine::add_issue(&lim, "options.include_state_after_each",
                        "per-access snapshots would serialize " +
                            std::to_string(snapshot_work) +
                            " line states (limit 2000000); shrink the cache "
                            "or disable the option",
                        snapshot_work);
      emit(error_envelope("E_LIMIT", "snapshot serialization budget exceeded",
                          engine::issues_to_json(lim)),
           opts.out_path);
      return kExitValidation;
    }
  }

  // Simulation. Large supported configurations (e.g. a 2^20-line cache with
  // a 100,000-access trace) can legitimately exhaust memory on constrained
  // machines; a standard-library failure must still produce a contract
  // envelope (E_INTERNAL, exit 4) — never an uncaught std::bad_alloc crash
  // with an empty stdout and an undocumented exit code.
  json envelope = success_envelope();
  try {
    engine::SimulateResult result;
    if (!engine::simulate(config, geometry, tv.trace.addresses,
                          include_state_after_each, &result)) {
      emit(error_envelope("E_INTERNAL", "internal invariant violation"),
           opts.out_path);
      return kExitInternal;
    }

    envelope["echo"] = *cfg_it;
    envelope["geometry"] = engine::geometry_to_json(geometry, config);
    json events = json::array();
    for (const auto& e : result.events) {
      events.push_back(engine::event_to_json(e, config));
    }
    envelope["events"] = events;
    envelope["summary"] = engine::build_summary(config, result.counts,
                                                result.rng_draws,
                                                tv.trace.addresses);
    envelope["state"] = engine::state_to_json(result.final_state,
                                              result.snapshots,
                                              engine::policy_from_config(config),
                                              result.snapshots_requested);
    emit(envelope, opts.out_path);
    return kExitOk;
  } catch (const std::bad_alloc&) {
    emit(error_envelope("E_INTERNAL",
                        "the engine ran out of memory producing the result "
                        "for this configuration and trace; use a smaller "
                        "cache or trace", json::array()),
         opts.out_path);
    return kExitInternal;
  } catch (const std::exception& err) {
    emit(error_envelope("E_INTERNAL",
                        std::string("internal error: ") + err.what()),
         opts.out_path);
    return kExitInternal;
  }
}

}  // namespace

int main(int argc, char** argv) {
  Options opts;
  std::string parse_error;
  if (!parse_args(argc, argv, &opts, &parse_error)) {
    emit(error_envelope("E_USAGE", parse_error), std::string());
    return kExitUsage;
  }

  // --mode version takes no input; --in/--out are honored but --in is unused.
  if (opts.mode == "version") {
    emit(success_envelope(), opts.out_path);
    return kExitOk;
  }

  if (opts.mode == "geometry") {
    return run_geometry(opts);
  }

  if (opts.mode == "simulate") {
    return run_simulate(opts);
  }

  if (opts.mode.empty()) {
    emit(error_envelope("E_USAGE", std::string("missing --mode; ") + kUsage),
         opts.out_path);
  } else {
    emit(error_envelope("E_USAGE",
                        "unknown mode: " + opts.mode + "; " + kUsage),
         opts.out_path);
  }
  return kExitUsage;
}
