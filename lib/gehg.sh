# gehg.sh — shared shell harness for the grant-encryption Hello Galaxy demo.
# Sourced by bin/grant-enc. Presentation + preflight only; the scenario logic and
# every assertion live in the Python drivers (scenarios/NN/run.py).
# shellcheck shell=bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_CYAN=$'\033[36m'; C_BOLD=$'\033[1;37m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RESET=$'\033[0m'
else
  C_CYAN=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RESET=""
fi

banner() { printf '%s\n%s  %s%s\n%s\n' "${C_CYAN}════════════════════════════════════════════════════════════${C_RESET}" \
  "${C_BOLD}" "$1" "${C_RESET}" "${C_CYAN}════════════════════════════════════════════════════════════${C_RESET}"; }

# The scenario list — the ONLY place the ordering is defined.
scenarios() {
  cat <<'EOF'
01-the-envelope|one DEK seals the stream; the DEK is wrapped to each member
02-audience-from-a-grant|the owner grants; the key service DERIVES who gets a key
03-read-and-deny|producer seals -> member opens -> outsider denied, over the bus
04-revocation-is-rotation|remove a member -> the next generation excludes it
05-per-individual-keys|why keys are per-individual and the org is only the grouping
06-who-could-decrypt-this|the producer's pre-publish check, and why a zero is not one answer
EOF
}

preflight() {
  command -v python3 >/dev/null 2>&1 || { echo "need python3" >&2; return 1; }
  python3 - <<'PY' 2>/dev/null || { echo "${C_YELLOW}need the 'cryptography' package: pip install cryptography${C_RESET}" >&2; return 1; }
import cryptography  # noqa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa
from cryptography.hazmat.primitives.asymmetric import ec  # noqa
PY
}

resolve() {  # accept "03" or "03-read-and-deny" or "read-and-deny"
  local want="$1" name
  while IFS='|' read -r name _; do
    case "$name" in "$want"|"${want}-"*|*"-$want"|"$want"*) echo "$name"; return 0;; esac
  done < <(scenarios)
  return 1
}

run_one() {
  local name; name="$(resolve "$1")" || { echo "unknown scenario: $1" >&2; list; return 2; }
  python3 "$ROOT/scenarios/$name/run.py" "${@:2}"
}

run_all() { local name _; while IFS='|' read -r name _; do run_one "$name"; echo; done < <(scenarios); }

list() {
  echo "${C_BOLD}scenarios:${C_RESET}"
  local name desc; while IFS='|' read -r name desc; do printf '  %s%-26s%s %s\n' "$C_GREEN" "$name" "$C_RESET" "$desc"; done < <(scenarios)
}
