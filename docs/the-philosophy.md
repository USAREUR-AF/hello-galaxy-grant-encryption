# The philosophy — why the shape is what it is

Every choice in this design falls out of a few commitments. If you disagree with the mechanism, disagree with these first.

## 1. The read path must have nothing in it that can decrypt

A tactical mesh has to keep working when it is cut off from everything else. The moment a *read* depends on reaching a central service — a policy server, a decrypting proxy, a broker — that service becomes a single point of failure and a bottleneck, and the "island" stops working. So the rule is absolute: **no component in the read path holds plaintext or makes a per-read decision.**

That rule has a price and a payoff. The payoff: island-survival, no bottleneck, no broker to attack. The price: the router cannot enforce reads, so we can only reach **topic granularity** — you encrypt a whole stream to an audience, not individual fields. We pay that price on the machine plane deliberately, and put field/row control on the human plane where an app already holds plaintext at read time. **Coarse-but-brokerless is a choice, not a limitation we're hiding.**

## 2. Control travels with the data

Because the router won't enforce reads, the enforcement moves *into the data*: the stream is encrypted, and the key is the access token. Protection is "at source" — it holds wherever the bytes travel, through caches, replay, cold storage, and across a federation, with no perimeter to depend on. Revoking access is changing the key, not reaching a gatekeeper.

## 3. The owner decides; the platform records

The organization that owns data decides who reads it. The platform's job is not to adjudicate that decision but to **record** it — an audit trail, attributable to a named admin. This inverts the usual instinct to gate: we make *restriction* the deliberate, logged act and *sharing* the frictionless default, because the documented failure mode of classification systems is over-restriction, not over-sharing. An owner who holds data has the authority to release it; the system's contribution is honesty about who released what.

## 4. Keys are per-individual; the organization is only the grouping

It is tempting to give each organization one key and copy it to its members — small bundles, simple mental model. It is the wrong trade. A shared key can't exclude one holder, so removing one person means re-keying the whole org; a copied private key is a distributed secret with no per-member attribution. So each individual and machine holds **its own** key, and the organization is the unit of *authority and addressing* — who may grant, and how we enumerate an audience — never a shared secret. When a flat audience eventually grows too large to wrap one-by-one, the answer is a **key tree** (MLS/TreeKEM) — the group-key idea done properly, with forward secrecy — not a static shared key.

## 5. One set of rules, both planes

Humans read through apps; machines read by holding keys. These are two enforcement mechanisms, but they must not become two *policies*. There is exactly one authoritative store of grants; the human app and the machine key-distribution both derive from it. The audience a key bundle wraps to is a **derived projection** of those grants, never a hand-kept list — so it can't drift out of sync with what a person sees in their browser. "Same policy source, coarser machine projection" — never a claim that the two planes enforce identically, and never a second store to reconcile.

## 6. Honesty about the seams

A demo — and a system — earns trust by marking exactly what it proves versus what it stands in for. That is why this repo ships an [honesty matrix](honesty-matrix.md) that grades every claim, why a scenario that can't reach a real router *says so* instead of pretending, and why an empty result is never dressed up as a denial. The discipline is the point: a mechanism you can only trust when you can see its edges.

---

*These are the load-bearing commitments. The crypto ([envelope-and-keys.md](envelope-and-keys.md)) and the authority model ([data-owner-controls.md](data-owner-controls.md)) are just these principles made concrete.*
