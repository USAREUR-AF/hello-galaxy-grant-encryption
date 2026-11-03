# 02 — Audience from a grant

The set of key-holders is not a list someone maintains; it is derived on demand from the data owner's grant rows plus the current roster.

## The problem

If the audience for an encrypted stream is a hand-kept list, it drifts. Someone joins an org but never gets added; someone leaves but stays on the list; two operators disagree about who the "current" readers are. You want the data owner to state intent **once** — "share this producer with that org" — and have the exact set of key-holders fall out of that intent and the registry, with nothing to keep in sync by hand.

## What you'll see

1. A roster is set up: org `acme-sensors` owns producer `sensor-k`; org `northwind` has two machine members (`station`, `dashboard`); and one person is recorded who has no machine anchor — a browser-only reader.
2. The data owner records **one** grant: `acme-sensors/sensor-k may be read by org northwind` (status active). That is the entire declaration of intent.
3. The key service **derives** the audience from that grant plus the roster. The org grant expands to `northwind`'s two machine anchors, and the producer is added as its own member (producer-as-member) — printed as `wrap DEK to <member> (from the org grant / producer-as-member)`.
4. A **principal** grant is then added, naming the browser-only person directly. Watch it *not* become a wrap target: the person has no machine key, so the derivation notes them as a human-plane reader rather than adding a slot.
5. The key service wraps the DEK to the derived audience, signs one bundle, and publishes `keys/<producer>/1` with exactly the right number of slots.

## What it proves — and why it matters

- **The audience is a derived projection, never a stored list.** It is computed from in-effect grant rows and the roster every time, so there is no second list to keep in sync with the first.
- **An org grant expands to that org's machine anchors.** The org is the addressing unit; the anchors under it are the actual wrap targets, and the producer is always included so it can pull its own DEK.
- **A person with no machine key is correctly not a wrap target.** A browser-only principal reads through the mediated human-plane surface — encrypting a machine-plane DEK to someone who holds no wrapping key would be meaningless, so the derivation notes them instead of wrapping to them.

## The honest caveat

The roster here is in-memory: a small object standing in for the registry. On a goatnet this projection is the portal's `GET /api/access/audience`, computed over the same grant rows against its registry. The derivation logic shown mirrors that endpoint's shape, but the data source and the surface around it are modeled, not live.

## Run it

The script is the proof companion to this README, not the lesson — read the recipe first, then run:

```
./bin/grant-enc 02
```
