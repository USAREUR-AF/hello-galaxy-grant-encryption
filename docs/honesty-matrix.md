# Honesty matrix

The most important doc in the repo. Every Hello Galaxy demo states plainly **what it proves live** versus **what it models or stands in for**, so nothing here reads as a stronger claim than it is. A demo that hides its seams teaches the wrong thing.

## The crypto

| Claim | Grade | The honest detail |
|---|---|---|
| AES-256-GCM payload seal, per-(release-set, generation) DEK | **Live** | Real `cryptography` (OpenSSL) AEAD in `lib/grant_enc.py`. Run the scenarios and it actually encrypts/decrypts. |
| DEK wrapped per member (ephemeral-static ECDH P-256 → HKDF-SHA256 → AES-256-GCM) | **Live** | Real ECDH + HKDF + AEAD. An outsider's key genuinely cannot unwrap a member's slot. |
| Bundle signed (ECDSA-P256/SHA-256) and verified before unwrap | **Live** | Real signature over a canonical length-prefixed transcript; a forged-signer bundle is genuinely rejected (scenario 03/05 exercise both directions). |
| The AAD binds suite+release-set+generation+topic | **Live** | Wrong generation and wrong topic genuinely fail to open (scenario 01 asserts the topic bind). |
| `lib/grant_enc.py` is the **production** crypto library | **Represented** | No — and it says so in its own header. It is a *readable reference* of the same construction, kept deliberately as a teaching artifact (ADR 1106). The production library is the grant-crypto SDK (Rust core + a versioned C ABI + thin bindings), conformance-tested against shared cross-language vectors. |
| The scenarios run on the **production SDK** | **Live, on demand** | Run `bin/fetch-sdk.sh` and the endpoint crypto in the scenarios — the producer's `seal` and the consumer's `verify → admit → open` (`demo.Producer` / `demo.Consumer`, used by scenarios 03/04/05) — runs on the real grant-crypto SDK via its stdlib-only Python binding. The narration prints `endpoint crypto backend: grant-crypto SDK`. Without the SDK a bare clone falls back to the reference and says so, rather than pretending. The **key service** (mint/wrap/sign) stays on `grant_enc` in both modes — mirroring the real `grant-keyd` daemon; the SDK deliberately exposes no key-authority surface. |
| The reference and the SDK are **wire-compatible** | **Live, on demand** | With the SDK present, bytes sealed by `grant_enc` open under the SDK and vice versa — both directions, plus an outsider denied fail-closed — proven by `tests/cross_compat.py` and a step inside scenario 01. This holds because both implement the one WIRE-FORMAT the shared conformance vectors pin. |

## The transport

| Claim | Grade | The honest detail |
|---|---|---|
| A member reads the stream; an outsider gets the same bytes and can't open them | **Live (crypto) / modeled (transport, default)** | The read cut is real crypto either way. By default the pub/sub is an in-process bus (`InProcessBus`) that faithfully models Zenoh semantics: publishing a bundle *retains* it (the keys/** storage), and every subscriber — member and outsider — receives the identical bytes. |
| The same bytes survive a real router | **Live, on demand** | Scenario 03 with `--fabric` carries the identical envelope + bundle over a real `eclipse/zenoh:1.9.0` router (see `local-fabric/`). Needs docker + `pip install eclipse-zenoh`; if either is absent the scenario says so and falls back to the in-process bus rather than pretending. |
| Brokerless / no decryptor in the read path | **Structural** | True by construction: nothing in either transport decrypts; the router (real or modeled) only moves ciphertext. This is a property of the design, not something a demo can "prove" by itself. |

## The system around the crypto

| Claim | Grade | The honest detail |
|---|---|---|
| The audience is DERIVED from grant rows, not a hand-kept list | **Live (logic) / modeled (source)** | `demo.derive_audience` is the real projection logic (org grant → member anchors, producer-as-member, browser-only person noted-not-wrapped). Its inputs — the grant rows and the org roster — are in-memory here. On a goatnet the same projection is served by the portal's `GET /api/access/audience` over its grant store. |
| A member of the grantee org is wrapped only if their OWN nationality is one that owns the org | **Live (logic) / modeled (source)** | `demo.classify_org_material` mirrors the shipped `access.DataRoster.ClassifyOrgMaterial` (ADR 1171): `national` matches the owning nation, `multinational` matches the body's member nations, and absence refuses on BOTH sides. `affiliation.relationship` is deliberately not an input. Scenario 06 exercises all three outcomes; the roster is in-memory, as everywhere else here. |
| A producer can ask "who could decrypt this?" BEFORE publishing | **Live (logic) / modeled (source)** | `demo.preview_audience` mirrors `access.BuildAudiencePreview`. On a goatnet the endpoint is `GET /api/access/audience/preview`, which shares one code path with the real wrap so the preview cannot drift from what it predicts; for a release-set whose grant is to a principal rather than an org it returns `holders: 0` with `evaluable: false`, reporting the zero as unanswerable rather than as an answer. Scenario 06. |
| A zero audience means "nobody qualifies" | **False, and the surface says so** | Zero can equally mean *nobody has declared*. The two are opposite — the restriction holding versus a registry nobody filled in — so the preview carries `evaluable`. Not an edge case: every organisation that has not declared an owning nation yields this zero. |
| Revocation = rotation | **Live** | Scenario 04 genuinely rotates generations; the revoked member genuinely cannot open the new generation and genuinely keeps the old one. |
| Forward secrecy across prior generations | **Not claimed** | A revoked member keeps generations it already held. This is the accepted launch posture; MLS/TreeKEM is the documented strategic path to forward secrecy, not implemented here. |
| Keys are per-individual; a shared org key is worse | **Live (demonstration)** | Scenario 05 runs the per-individual path for real; the shared-org-key downside is *argued* (its failure — whole-org re-key to remove one member — is described, not enacted, because we don't ship the bad design). |
| Identity, enrollment, SPIRE/SVID validation | **Represented** | Members here are freshly-generated P-256 keypairs with string ids. On the real fabric, a member's key is its enrollment/SVID certificate key, and the key service validates each member's SVID against the SPIRE trust root before wrapping. That PKI is out of scope for this repo (it needs a goatnet); the ids here stand in for the write-anchor/CN the production system keys on. |
| "Your enrollment cert is the key you unwrap with" holds on a goatnet | **Requires a goatnet** | On a goatnet the portal mints each member's enrollment certificate with an ECDSA-P256 key, so the same key that authenticates the member unwraps its slot; the key service fetches the member's public certificate from the portal and re-validates it before wrapping. This repo does not exercise that path; [`goat-cli-path.md`](goat-cli-path.md) walks it as an annotated transcript. |

## The one-line summary

**The cryptography is real and runs — on the production grant-crypto SDK when you fetch it (`bin/fetch-sdk.sh`), and on the readable reference otherwise, the two proven wire-compatible. The transport is real on demand (`--fabric`) and faithfully modeled by default. The identity/PKI and the live grant source are represented, and clearly marked as such.** Nothing in the scenarios asserts a property the code did not actually exercise.
