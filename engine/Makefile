# engine/Makefile — build and test the cache_sim engine (decision D-2).
# Targets: all (build/cache_sim.exe), test (build/engine_tests.exe + run),
# clean. Invoked from the project root as: mingw32-make -C engine [target]
#
# Requires Git Bash on PATH (mingw32-make uses sh.exe when present), and
# nlohmann/json vendored at third_party/nlohmann/json.hpp (decision D-3).

CXX      = g++
CXXFLAGS = -std=c++14 -O2 -Wall -Wextra
# -isystem keeps vendored-header warnings out of our zero-warning gate.
INCLUDES = -Iinclude -isystem third_party

BUILD_DIR = ../build
APP       = $(BUILD_DIR)/cache_sim.exe
TESTS     = $(BUILD_DIR)/engine_tests.exe

# Library sources without main(); shared by the app and the test runner.
LIB_SRC  = src/config.cpp src/geometry.cpp src/cache.cpp src/simulator.cpp src/stats.cpp
LIB_HDR  = include/version.hpp include/config.hpp include/geometry.hpp include/cache.hpp include/simulator.hpp include/rng.hpp include/stats.hpp include/textutil.hpp

.PHONY: all test clean

all: $(APP)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(APP): $(LIB_SRC) src/main.cpp $(LIB_HDR) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(LIB_SRC) src/main.cpp -o $(APP)

$(TESTS): tests/engine_tests.cpp $(LIB_SRC) $(LIB_HDR) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) tests/engine_tests.cpp $(LIB_SRC) -o $(TESTS)

test: $(TESTS)
	$(TESTS)

clean:
	rm -rf $(BUILD_DIR)
