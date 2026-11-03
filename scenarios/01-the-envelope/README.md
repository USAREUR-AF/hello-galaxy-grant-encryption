# 01 — The envelope

One symmetric data key seals a stream once; that key is wrapped to each member individually, so the encryption cost never depends on how large the audience is.

## The problem

You have a stream to protect and an audience that will change over time. The naive move — re-encrypt the payload separately for every reader — makes each message cost scale with the audience, and re-encrypting a whole feed every time someone joins is a non-starter at fabric rates. You want to pay the encryption cost once, per message, and pay a tiny separate cost per member only when the membership actually changes.

## What you'll see

1. The key service mints **one** AES-256 data key (the DEK) for release-set `weather-feed`, generation 1. It holds that key only long enough to wrap it.
2. Two members, `alice` and `bravo`, each hold their **own** keypair. The DEK is wrapped once to each member's public key — N members, N small wrapped copies — and the resulting bundle (`keys/weather-feed/1`) is signed by the key service.
3. A producer seals a message with the DEK. The ciphertext is one AES-GCM seal on topic `data/weather-feed/obs`, and its size is independent of how many members can read it.
4. A member (`bravo`) verifies the bundle's signature, finds its own slot, unwraps the DEK, and opens the message — printing the plaintext back out.

## What it proves — and why it matters

- **Encrypt-once, cost independent of audience size.** The payload is sealed a single time with the DEK. Adding a member costs one small wrapped-key copy, not a re-encrypt of the stream — this is the hybrid (symmetric-payload / asymmetric-key) envelope.
- **The bundle is authenticated before it is trusted.** A member verifies the key service's signature over the whole bundle *before* unwrapping anything, so a bundle from anyone but the trusted key service is rejected.
- **The AAD binds the message to its exact context.** Suite, release-set, generation, and topic are all bound as additional authenticated data. A message can only be opened for exactly the stream, generation, and topic it was sealed for — a stale generation or a cross-topic replay fails cleanly.

## The honest caveat

This scenario is pure crypto — there is no fabric yet, no pub/sub, no roster. Everyone is constructed in-process and handed to each other directly. The construction here (ECDH-P256 → HKDF-SHA256 → AES-256-GCM) mirrors the production Rust `grant-crypto` core closely enough to teach every moving part, but it is a pedagogical reimplementation, not the byte-for-byte production library. Scenario 03 carries these same bytes over a real router.

## Run it

The script is the proof companion to this README, not the lesson — read the recipe first, then run:

```
./bin/grant-enc 01
```
