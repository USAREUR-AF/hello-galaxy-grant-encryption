# The one mechanism: envelope encryption + a signed key bundle

Understand this page and the rest of the repo is obvious. Everything else — grants, audiences, revocation, the two planes — is *policy about who gets a key*. This is the crypto that makes "who holds the key" mean "who can read."

The reference implementation is [`lib/grant_enc.py`](../lib/grant_enc.py) (~250 readable lines). This page is its narrated companion. Production producers and consumers use the **grant-crypto SDK** (the audited Rust core behind a versioned C ABI; ADR 1106) — the same construction and the same wire format, which is why the scenarios can run on either (see the README's "Running on the production SDK"). Read the reference here to learn the mechanism; ship on the SDK.

## Why encryption at all, on a mesh?

A brokerless pub/sub fabric routes messages peer-to-peer. There is deliberately **no central component in the read path** — nothing that could hold plaintext and decide, per request, whether you may see it. That is a feature (it survives being cut off; it can't be a bottleneck or a single point of failure), but it means the router cannot enforce *reads*: any enrolled peer can subscribe to any topic.

So we move the decision off the router and into the data: **encrypt the stream, and control who holds the key.** The router keeps doing the one thing it's good at — moving bytes it cannot read.

## Two layers (that's what "envelope" means)

Encrypting a whole stream separately to each of N recipients would be N encryptions per message. Instead:

- **Layer 1 — the payload.** One symmetric **data key (DEK)** — AES-256-GCM — encrypts every message on the stream. One key, one seal per message, **cost independent of audience size**. There is one DEK per *(release-set, generation)* (more on generations below).
- **Layer 2 — the key.** That 32-byte DEK is encrypted ("wrapped") separately to each authorized member's **public key**. N members → N small wrapped copies. This is the only per-recipient work, and it happens **per rotation, not per message**.

This is standard hybrid encryption — the same shape as TLS, `age`, or PGP-to-many. The only fabric-specific choice is that the wrapped-key bundle travels as ordinary pub/sub.

```
                       ┌───────────────────────────── one DEK ─────────────────────────────┐
   plaintext message ──┤  AES-256-GCM(DEK, msg, AAD)  →  ciphertext on data/<rs>/<topic>    │
                       └────────────────────────────────────────────────────────────────────┘
                       ┌── wrap(DEK → Alice's pubkey) ──┐
        the DEK   ─────┼── wrap(DEK → Bravo's pubkey) ──┼──►  bundle on keys/<rs>/<gen>
                       └── wrap(DEK → …            ) ────┘
```

## The envelope, precisely

`seal_envelope(dek, rs, gen, plaintext, keyexpr)` produces an `Envelope{suite, rs, gen, nonce, ct}`. The ciphertext is `AES-256-GCM(dek, nonce, plaintext, aad)` where the **additional authenticated data** binds the whole context:

```
AAD = len8(suite) ‖ suite ‖ len8(rs) ‖ rs ‖ be64(gen) ‖ keyexpr
```

Because the suite, release-set, generation, and *topic* are authenticated (not encrypted, but tamper-evident and bound), a message **can only be opened for exactly what it was sealed for**. A stale-generation key fails. A message replayed onto a different topic fails. That binding is the quiet workhorse of the whole design — it's what makes "wrong key / wrong generation / wrong topic" all resolve to the same clean *reject*.

## Wrapping the DEK to one member

`wrap_dek(dek, recipient_pub)`:

1. Generate an **ephemeral** P-256 keypair.
2. **ECDH**: ephemeral-private × recipient-public → a shared secret (only the recipient can recompute it, with recipient-private × ephemeral-public).
3. **HKDF-SHA256** the shared secret → a 32-byte key-encryption key (KEK), with a fixed `info` label so this KEK is domain-separated from any other use of the same ECDH.
4. **AES-256-GCM(KEK, DEK)** with the suite and *both* public keys bound as AAD (so a wrapped slot can't be lifted and replayed against a different recipient).

The recipient reverses it with its own private key. This is ephemeral-static ECIES — forward-ish per rotation, and it needs no shared state: the recipient's key is its **enrollment certificate keypair**, issued at onboarding *before any DEK exists*. That's the root that stops the chicken-and-egg regress — there is never a "key to get the first key" problem.

## The bundle, and why it's signed

The wrapped copies are collected into a `KeyBundle{suite, rs, gen, members: {id → WrappedDek}, signer, sig}` and published on `keys/<rs>/<gen>`. Everyone on the mesh receives it; only a member can unwrap its own slot; non-members hold ciphertext they can't open — safe to broadcast.

But confidentiality of the *contents* is not authenticity of the *wrapper*. Anyone able to publish on the key topic could otherwise publish a bundle wrapping an attacker-chosen DEK. So the key service **signs every bundle** (ECDSA-P256/SHA-256 over a canonical, length-prefixed transcript of every field), and a member **verifies before it unwraps anything**. Defence in depth: the fabric's write-ACL also restricts who may publish on `keys/**` to the key-service identity — but the signature holds even if that ACL is ever misconfigured or the setup is multi-writer.

The read path, in the required order (`consume(...)`):

```
verify bundle signature  →  find my slot  →  unwrap my DEK  →  open the message
        │                        │                                    │
   not the key service?     not in the audience?              wrong gen/topic?
        └── reject                └── reject                          └── reject
```

An outsider fails at "find my slot" — **denied by the crypto, not by the router.**

## Generations, and revocation without a flag-day

The `gen` in every topic and every message is the revocation lever. To remove a member you don't delete a key — you mint the **next generation**: a fresh DEK wrapped to everyone *except* the removed party. Each message carries its generation, so readers switch lazily as they encounter new-generation traffic; there is no synchronized cutover. The removed member keeps whatever generations it already held (bytes can't be clawed back) but receives nothing new. See [scenario 04](../scenarios/04-revocation-is-rotation/).

## Crypto-agility and the post-quantum path

Every structure carries a `suite` id, bound into the AAD so a suite can't be silently downgraded, and distinct suites can coexist across generations. The suite here is `v1-ecdh-p256` (classical). The migration path is a **hybrid KEM** on the wrap step (X25519 + ML-KEM-768, combined so confidentiality holds if *either* stays unbroken) — a change to layer 2 only, invisible to the payload layer. The KEM is the urgent piece (harvest-now-decrypt-later hits confidentiality); PQC signatures can follow. That is why the format is built suite-first even though this demo ships the classical suite.

## What to read next

- [`data-owner-controls.md`](data-owner-controls.md) — who decides which members go in the bundle.
- [`honesty-matrix.md`](honesty-matrix.md) — how faithfully this reference matches the production core.
- The [scenarios](../scenarios/) — the same mechanism, shown running.
