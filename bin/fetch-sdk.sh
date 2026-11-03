#!/usr/bin/env bash
# fetch-sdk.sh — obtain the grant-crypto SDK into ./sdk/ so this repo can run its
# scenarios on the PRODUCTION library, not just the readable reference.
#
# The demo is self-contained: with only the `cryptography` package it runs on the
# in-repo reference implementation (lib/grant_enc.py). Run this script and the
# same scenarios run on the real grant-crypto SDK (Rust core + a stdlib-only
# Python binding over its C ABI) — the library production producers and consumers
# actually use. Its source is public, in goatcore at ops/grant-crypto/sdk/.
# ./sdk/ is gitignored; this script is how you (re-)materialize it.
#
#   bin/fetch-sdk.sh                       # mode A: sparse-clone goatcore (default)
#   bin/fetch-sdk.sh --local <path>        # mode B: copy from a goatcore checkout
#   GOATCORE_REF=<tag|branch> bin/fetch-sdk.sh   # mode A at a given ref (default: main)
#
# What it does, either mode: lands the SDK source under ./sdk/, checks the Rust
# toolchain, builds the C ABI cdylib (`cargo build -p grant-crypto-capi`), and
# tells you how the scenarios pick it up. The Python binding is pure stdlib, so
# no pip step is required — the demo adds ./sdk/bindings/python to sys.path.
#
# Exit codes: 0 ok · 2 usage · 3 SDK source not obtainable · 4 toolchain/build failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_DIR="$ROOT/sdk"
GOATCORE_URL="${GOATCORE_URL:-https://github.com/usareur-af/goatcore.git}"
GOATCORE_REF="${GOATCORE_REF:-main}"
SDK_SUBDIR="ops/grant-crypto/sdk"

RUST_MIN_MAJOR=1
RUST_MIN_MINOR=77

say()  { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die()  { printf 'error: %s\n' "$1" >&2; exit "${2:-1}"; }

usage() {
  sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-2}"
}

mode="git"
local_path=""
while [ $# -gt 0 ]; do
  case "$1" in
    --local) mode="local"; local_path="${2:-}"; shift 2 || die "--local needs a path" 2 ;;
    -h|--help) usage 0 ;;
    *) die "unknown argument: $1 (see --help)" 2 ;;
  esac
done

check_rust() {
  step "Checking the Rust toolchain (need >= ${RUST_MIN_MAJOR}.${RUST_MIN_MINOR})"
  command -v cargo >/dev/null 2>&1 || die "cargo not found — install Rust >= ${RUST_MIN_MAJOR}.${RUST_MIN_MINOR} from https://rustup.rs" 4
  local v major minor
  v="$(rustc --version | awk '{print $2}')"
  major="${v%%.*}"; minor="${v#*.}"; minor="${minor%%.*}"
  if [ "$major" -lt "$RUST_MIN_MAJOR" ] || { [ "$major" -eq "$RUST_MIN_MAJOR" ] && [ "$minor" -lt "$RUST_MIN_MINOR" ]; }; then
    die "rustc $v is too old — the SDK C ABI needs Rust >= ${RUST_MIN_MAJOR}.${RUST_MIN_MINOR} (C-string literals)" 4
  fi
  say "rustc $v — ok"
}

fetch_git() {
  step "Sparse-cloning ${SDK_SUBDIR} from ${GOATCORE_URL} (${GOATCORE_REF})"
  command -v git >/dev/null 2>&1 || die "git not found" 4
  local tmp; tmp="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand $tmp now, at trap-set time
  trap "rm -rf '$tmp'" EXIT
  git clone --quiet --depth 1 --filter=blob:none --sparse --branch "$GOATCORE_REF" \
      "$GOATCORE_URL" "$tmp/goatcore" \
    || die "could not clone ${GOATCORE_URL} at ${GOATCORE_REF}" 3
  git -C "$tmp/goatcore" sparse-checkout set "$SDK_SUBDIR" \
    || die "could not check out ${SDK_SUBDIR}" 3
  local_path="$tmp/goatcore"
  fetch_local
}

fetch_local() {
  step "Copying the SDK from a checkout: ${local_path}"
  [ -n "$local_path" ] || die "--local needs a path to a goatcore checkout" 2
  # Accept either the checkout root or a direct path to the sdk/ subtree.
  local src=""
  for cand in \
    "$local_path/ops/grant-crypto/sdk" \
    "$local_path/sdk" \
    "$local_path"; do
    if [ -d "$cand/capi" ] && [ -d "$cand/bindings/python" ]; then src="$cand"; break; fi
  done
  [ -n "$src" ] || die "could not find the SDK (looked for capi/ + bindings/python/ under $local_path)" 2
  say "source: $src"
  rm -rf "$SDK_DIR"; mkdir -p "$SDK_DIR"
  # Copy the source tree only; skip any pre-existing build output.
  (cd "$src" && tar --exclude='./target' -cf - .) | (cd "$SDK_DIR" && tar -xf -)
}

build_capi() {
  step "Building the C ABI cdylib (cargo build -p grant-crypto-capi)"
  ( cd "$SDK_DIR" && cargo build -p grant-crypto-capi ) || die "cargo build failed" 4
  local lib
  case "$(uname -s)" in
    Darwin) lib="libgrant_crypto_capi.dylib" ;;
    *)      lib="libgrant_crypto_capi.so" ;;
  esac
  local built="$SDK_DIR/target/debug/$lib"
  [ -f "$built" ] || die "build reported success but $built is missing" 4
  say "built: $built"
}

case "$mode" in
  git)      check_rust; fetch_git ;;
  local)    check_rust; fetch_local ;;
esac
build_capi

cat <<EOF

SDK ready under ./sdk/  (gitignored).

Run the walkthrough on the production SDK:
    ./bin/grant-enc all

The scenarios auto-detect ./sdk/bindings/python and the built C ABI; you'll see
"backend: grant-crypto SDK" in the narration. Cross-library wire proof:
    python3 tests/cross_compat.py
EOF
