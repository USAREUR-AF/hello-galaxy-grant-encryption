# 05 — Per-individual keys

Each member holds its own keypair and the organization is only the grouping and addressing unit — never a shared secret copied around.

## The problem

There is a tempting shortcut: one keypair per organization, copied to every member of it. It makes bundles smaller and feels simpler. But it quietly trades away the things that matter most when membership changes or when something leaks, and the failure only shows up on the operation you least want to be expensive — removing one member. This scenario puts the two designs head to head on exactly that operation.

## What you'll see

1. **The shortcut, walked through.** With one org keypair copied to every member, a removed member still holds the org's private key. To actually cut them off you must mint a new org keypair, redistribute it to every remaining member, and re-wrap — one departure triggers an org-wide key ceremony. And because everyone is cryptographically identical, a leak cannot be traced to a person.
2. **The design.** Each member holds its own keypair; the org is only how members are grouped and addressed. Generation 1 wraps the DEK to `{prod, a, b, c}` — four independent keys, none shared.
3. **Remove `c`.** The key service mints generation 2 to `{prod, a, b}`. Reader `a` still holds current keys (two generations) and nobody re-keyed `a`, `b`, or the producer; reader `c` holds only gen 1 and is simply absent from gen 2.
4. **Two dials.** The owner sets *reach* (which channel the stream is published on — who receives the bytes) and *readability* (who holds the key — who can open them) separately, and they combine freely.

## What it proves — and why it matters

- **Granular revocation.** Removing one member is dropping one slot in the next generation; no one else is touched and no secret is redistributed.
- **Per-member attribution.** Distinct keys mean a read or a leak can be traced to an individual, which a shared org key makes impossible.
- **No shared secret to distribute.** The org is an authority and addressing unit, not a key — so there is no org-wide private key to guard, rotate, or leak.

## The honest caveat

A shared org key would buy a smaller bundle at the cost of all three properties above — a trade this design refuses. When a flat audience grows past what per-individual wrapping handles comfortably, the scale answer is a key tree (MLS/TreeKEM) — the group-key idea done properly, with forward secrecy — not a static shared key. This scenario contrasts per-individual keys against the shared-key shortcut; it does not implement the key-tree path.

## Run it

The script is the proof companion to this README, not the lesson — read the recipe first, then run:

```
./bin/grant-enc 05
```
