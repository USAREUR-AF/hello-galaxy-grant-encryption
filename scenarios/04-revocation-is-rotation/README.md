# 04 — Revocation is rotation

There is no "delete the key" step: to remove a member you mint the next generation without it, and the generation label carries the cut.

## The problem

Revoking read access sounds like it should mean reaching out and destroying a key somewhere. But you cannot claw back bytes a reader already received and decrypted, and you do not want a flag-day where the whole audience re-encrypts in lockstep. What you actually need is a clean way to say "from here forward, this member reads nothing new" without touching anyone else's keys and without a coordinated ceremony.

## What you'll see

1. Generation 1 has audience `{prod, a, b}`. The producer publishes a gen-1 message; both `a` and `b` open it.
2. The data owner revokes `b`. The key service rotates to generation 2 with audience `{prod, a}` — a fresh DEK wrapped to everyone still in the set, `b` simply absent.
3. Readers refresh: `a` admits gen 2 and now holds two generations; `b` finds no gen-2 slot and still holds only gen 1.
4. The producer publishes a generation-2 message. `a` opens it; `b` is denied gen 2 for lack of a slot — while `b`'s earlier gen-1 read still stands, because bytes already delivered are not clawed back.

## What it proves — and why it matters

- **Revocation is a new generation that omits the member.** No key is deleted and no flag-day is coordinated; the removed member just gets nothing new. The next generation wraps the next DEK to everyone else.
- **The generation tag routes each message to the right key.** Every message carries its generation, so readers switch lazily to whatever generation they hold — a rotation does not require any synchronized cutover.
- **The instant hard cut lives one layer down.** Revoking the member's cert takes it off the fabric in seconds. This scenario is the finer case: the identity stays on the fabric but loses this particular stream going forward.

## The honest caveat

Forward secrecy for prior generations is out of scope here — a member that held gen 1 keeps its gen-1 reads, and this construction does not try to retroactively protect already-delivered generations. The strategic path for that property is a key tree (MLS/TreeKEM), noted in the docs; this scenario deliberately shows the simpler generation-rotation model rather than overclaiming forward secrecy.

## Run it

The script is the proof companion to this README, not the lesson — read the recipe first, then run:

```
./bin/grant-enc 04
```
