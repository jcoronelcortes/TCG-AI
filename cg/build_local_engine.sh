#!/usr/bin/env bash
# Builds the LOCAL measurement engine from the competition's C++ source.
#
# Phase B of docs/engine-source-plan-2026-08-12.md. The shipped cg/libcg.* throw
# the seed away (ApiBattleStart sets deviceRand = true, which routes every
# shuffle and both coin paths to a fresh std::random_device). This build applies
# engine_patches/0001-seeded-battle-start.patch, which adds a BattleStartSeeded
# entry point and honours GameConfig::seed -- so a game can be replayed exactly.
#
# WHAT IS AND IS NOT VERSIONED
#   versioned:     this script, and engine_patches/*.patch (a few dozen lines)
#   NOT versioned: the engine source (ptcg_engine/, competition-use-only, must
#                  not be redistributed) and the binary this produces (cg/build/)
# The submission always uses the shipped cg/libcg.* -- never this. See rule R11
# of utils/lint_architecture.py, which enforces that the agent cannot reach it.
#
# Usage:
#   cg/build_local_engine.sh                     # default source location
#   PTCG_ENGINE_SRC=/path/to/src cg/build_local_engine.sh
#   cg/build_local_engine.sh --verify            # build, then check it matches
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
SRC="${PTCG_ENGINE_SRC:-$ROOT/ptcg_engine/ptcgProgram 22}"
BUILD="$HERE/build"
PATCH="$HERE/engine_patches/0001-seeded-battle-start.patch"

case "$(uname -s)" in
  Darwin) EXT="dylib" ;;
  Linux)  EXT="so" ;;
  *)      echo "unsupported platform: $(uname -s)" >&2; exit 1 ;;
esac
OUT="$BUILD/libcg_local.$EXT"

if [ ! -d "$SRC" ]; then
  cat >&2 <<EOF
The engine source is not at:
  $SRC
It is competition-use-only and deliberately NOT in this repository. Put the
package there, or point PTCG_ENGINE_SRC at it.
EOF
  exit 1
fi

echo "==> source:  $SRC"
rm -rf "$BUILD/src"
mkdir -p "$BUILD/src"
cp "$SRC"/*.h "$SRC"/Export.cpp "$BUILD/src/"

echo "==> patch:   $(basename "$PATCH")"
# --binary keeps CRLF intact; the engine sources are CRLF with a BOM and a
# patch applied in text mode would silently corrupt every line it touches.
patch --binary -p1 -d "$BUILD/src" -i "$PATCH" --quiet

echo "==> compile: $OUT"
CXX="${CXX:-clang++}"
command -v "$CXX" >/dev/null || CXX=g++
"$CXX" -std=c++20 -O2 -shared -fPIC -fvisibility=hidden -DNDEBUG \
  -o "$OUT" "$BUILD/src/Export.cpp" -I"$BUILD/src" 2>&1 \
  | grep -vE "warning: case value not in enumerated type" || true

[ -f "$OUT" ] || { echo "build produced no library" >&2; exit 1; }
echo "==> built:   $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"

if [ "${1:-}" = "--verify" ]; then
  echo "==> verify"
  PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
  "$PY" -c "import sys; sys.path.insert(0, '$ROOT'); import utils.local_engine" 2>/dev/null \
    || PYTHONPATH="$ROOT:$ROOT/utils" "$PY" -m local_engine --verify
fi
