#!/bin/sh
# Host tests for the X1 machine firmware (SPEC F4), no hardware.
#  1. Checks that the sketch's copies of the shared headers match their sources.
#  2. Builds control_logic_test.cpp with the logic core and runs it, with the address and
#     undefined-behaviour sanitizers. Uses g++ (or $CXX) if present, else Docker (gcc:14,
#     override with X1_TEST_IMAGE). The binary goes to ${TMPDIR:-/tmp}/x1fw-test, not the repo.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
fw=$(dirname "$here")
board=$(dirname "$fw")/main_board
src="$fw/x1_main/src"

check_same() {
  if ! cmp -s "$1" "$2"; then
    echo "FAIL: $2 differs from $1; $3"
    exit 1
  fi
}
check_same "$board/x1_main_pins.h" "$src/x1_main_pins.h" "run 'python3 pinmap.py' in main_board/source"
check_same "$fw/common/x1_link.h" "$src/x1_link.h" "run firmware/sync_headers.sh"
echo "headers: x1_main/src copies match main_board/x1_main_pins.h and common/x1_link.h"

out="${TMPDIR:-/tmp}/x1fw-test"
mkdir -p "$out"
flags="-std=c++17 -O1 -g -Wall -Wextra -Wpedantic -Werror -fsanitize=address,undefined -fno-sanitize-recover=all"
cxx="${CXX:-g++}"
if command -v "$cxx" >/dev/null 2>&1; then
  # shellcheck disable=SC2086
  "$cxx" $flags -I"$src" "$here/control_logic_test.cpp" "$src/control_logic.cpp" -o "$out/control_logic_test"
  ASAN_OPTIONS=detect_leaks=0 "$out/control_logic_test"
else
  echo "no $cxx here; building in Docker (${X1_TEST_IMAGE:-gcc:14})"
  docker run --rm --network none --user "$(id -u):$(id -g)" \
    -v "$fw:/fw:ro" -v "$out:/out" -w /out "${X1_TEST_IMAGE:-gcc:14}" \
    sh -c "g++ $flags -I/fw/x1_main/src /fw/test/control_logic_test.cpp /fw/x1_main/src/control_logic.cpp \
           -o /out/control_logic_test && ASAN_OPTIONS=detect_leaks=0 /out/control_logic_test"
fi
