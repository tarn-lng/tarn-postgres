#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${TARN:=../../tarn/target/debug/tarn}"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT
"$TARN" build scram_test.tarn -o "$TEST_DIR/scram"
"$TEST_DIR/scram"
"$TARN" build protocol_test.tarn -o "$TEST_DIR/protocol"
python3 tests/protocol.py "$TEST_DIR/protocol"
TARN=$(realpath "$TARN") python3 tests/integration.py
