# Contributing

Thank you for working on goat. This page is the whole process; nothing else is required reading before your first pull request.

## The short version

1. Fork, or branch from `main` if you have write access. Branch names: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
2. Make the change. Run the gates that apply (below). Add or update the design document in the same change when behaviour or topology changes.
3. Commit with a [Conventional Commits](https://www.conventionalcommits.org/) subject and a DCO sign-off: `git commit -s -m "fix(zenoh): …"`.
4. Open a pull request against `main`. Fill the template. One approving review from a code owner merges it, by squash.

## Commits

- **Conventional Commits.** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, with a scope in parentheses naming the component (`feat(goatbuilder): …`). The subject is ≤ 100 characters and says what changed, in the imperative.
- **DCO sign-off on every commit** (`git commit -s`). By signing off you certify the [Developer Certificate of Origin 1.1](https://developercertificate.org/): you wrote the change or have the right to submit it under this project's licence. There is no CLA.
- **Signed commits** are required on `main`; set up [SSH or GPG commit signing](https://docs.github.com/en/authentication/managing-commit-signature-verification) once.
- One logical change per pull request. Refactors and behaviour changes are separate pull requests.

## Gates

| Change touches | Run |
|---|---|
| the shell harness | `shellcheck -x bin/grant-enc lib/gehg.sh bin/fetch-sdk.sh` |
| the crypto, the apparatus or a scenario | `pip install cryptography && NO_COLOR=1 ./bin/grant-enc all` — every scenario ends in `PASS` |
| the SDK seam (`lib/sdk_bridge.py`) | `./bin/fetch-sdk.sh && ./bin/grant-enc all && python3 tests/cross_compat.py` (needs Rust ≥ 1.77) |
| the `--fabric` transport (`lib/zenoh_bus.py`, `local-fabric/`) | `docker compose -f local-fabric/docker-compose.yml up -d && pip install eclipse-zenoh && ./bin/grant-enc 03 --fabric` |

CI runs the first three. The reference here mirrors the grant-crypto SDK in [`goatcore`](https://github.com/usareur-af/goatcore) (`ops/grant-crypto/`); a change to the wire format starts there.

## Review

Reviewers look for: the change does what its subject says and nothing else; the gates pass; the design document moved with the code; status words are honest; no identifier of a real deployment (an address, a hostname, a key, a person) entered the tree. Review comments are about the change, not the author.

## Reporting a bug or proposing a feature

Open an issue with the template. For a vulnerability, **do not open an issue** — follow [SECURITY.md](SECURITY.md).

## Licence

By contributing you agree that your contribution is licensed under the [Apache License 2.0](LICENSE) that covers this project.
