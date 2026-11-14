# AGENTS.md

Instructions for AI coding agents, and a short version for anyone working here. [CONTRIBUTING.md](CONTRIBUTING.md) is the full process.

## What this repository is

hello-galaxy-grant-encryption is a walkthrough of grant-keyed encryption: a data owner encrypts a stream to a key, wraps that key to each authorized reader, and takes access away by changing the key. `lib/grant_enc.py` is a readable reference implementation; `bin/fetch-sdk.sh` switches the scenarios to the grant-crypto SDK built from goatcore.

It is one of the Hello Galaxy demonstrations: small, runnable examples, each showing one part of [goat](https://github.com/USAREUR-AF/goatcore). It holds no goat source code.

## Layout

| Path | What |
|---|---|
| `scenarios/` | one directory per scenario: `README.md` and `run.py` |
| `bin/grant-enc` | the runner: one scenario or `all`; `--fabric` sends scenario 03 over a local router |
| `bin/fetch-sdk.sh` | fetches and builds the SDK from goatcore |
| `lib/` | the reference implementation and the scenario helpers |
| `tests/cross_compat.py` | checks that the reference and the SDK read each other's output |
| `local-fabric/` | a local Zenoh router in Docker Compose |
| `report/`, `notebooks/`, `docs/` | the HTML report, a notebook walkthrough, background |

## Before you push

CI (`.github/workflows/ci.yml`) runs these. The first block needs Python 3 and `cryptography` only.

```bash
shellcheck -x bin/grant-enc lib/gehg.sh bin/fetch-sdk.sh
pip install cryptography
NO_COLOR=1 ./bin/grant-enc all
```

On the SDK:

```bash
./bin/fetch-sdk.sh
NO_COLOR=1 ./bin/grant-enc all        # prints 'backend: grant-crypto SDK'
python3 tests/cross_compat.py
```

Over a local router (needs Docker and `pip install eclipse-zenoh==1.9.0`):

```bash
docker compose -f local-fabric/docker-compose.yml up -d
NO_COLOR=1 ./bin/grant-enc 03 --fabric
```

## Rules

1. **Nothing from a real deployment.** No hostname, domain, address, key or person of a real goatnet goes into a file or a commit message. Use made-up names, documentation addresses (RFC 5737) and `example.org` mail.
2. **Commits.** Conventional Commits subject of 100 characters or fewer, with a scope (`fix(<component>): …`). Every commit is signed off (`git commit -s`, the DCO) and signed with a key GitHub verifies. The organization's required check `verified-commits` refuses a pull request that holds an unverified commit.
3. **One logical change per pull request.**
4. **Vulnerabilities** go through [SECURITY.md](SECURITY.md), never a public issue.

The contribution guide for goat as a whole is [goatcore CONTRIBUTING.md](https://github.com/USAREUR-AF/goatcore/blob/main/CONTRIBUTING.md).
