# The goat CLI way — the same mechanism, one operator binary

This repo shows grant-keyed encryption three ways, and they are **three views of one
wire-compatible mechanism**, not three implementations:

1. **The readable reference** — [`lib/grant_enc.py`](../lib/grant_enc.py), ~250 lines you can
   study top to bottom. This is how you *learn* the mechanism.
2. **The production SDK** — the audited Rust core behind a versioned C ABI (ADR 1106). Run
   [`bin/fetch-sdk.sh`](../bin/fetch-sdk.sh) and the scenarios' endpoint crypto runs on it. This is what
   production producers and consumers actually *ship on* (see the README's
   [Running on the production SDK](../README.md#running-on-the-production-sdk)).
3. **The `goat` CLI** — the operator's one binary. `goat pub --sealed` / `goat sub --open` /
   `goat access …` are a **thin convenience layer over that same SDK**. This is how an operator with a
   shell *does* the thing without writing any code.

The load-bearing point: path 3 adds **no new crypto**. The goat-cli docs put it plainly — the CLI
"holds no crypto of its own"; `--sealed`/`--open` "delegate straight to the frozen grant-crypto SDK
core," which makes goat-cli "the reference **convenience consumer** of the SDK … a convenience path,
not the only path" ([ADR 1106](https://github.com/usareur-af/goatcore/blob/main/docs/adr/1106-grant-crypto-sdk-and-endpoint-forward-secrecy.md); the CLI source is goatcore's
[`crates/goat-cli`](https://github.com/usareur-af/goatcore/tree/main/crates/goat-cli), with
`--sealed`/`--open` in `src/cmd/sealed.rs` and the `access` verbs in `src/cmd/access.rs`). So a byte
sealed by `grant_enc`, by a Rust producer on the SDK, or by
`goat pub --sealed` is the same byte, openable by any of the three. The reference teaches it, the SDK
ships it, the CLI drives it — one mechanism, three altitudes.

> **Read this as a narrated transcript, not a runnable scenario.** Unlike the reference path
> (`./bin/grant-enc all`, zero infrastructure) and the SDK path (`./bin/fetch-sdk.sh`, a toolchain and
> a download), the `goat` path needs a **live goatnet**: an enrolled profile (`goat profile init`), a
> reachable key service and portal, and a SPIRE trust root to verify bundle signers against. None of
> that exists in a bare clone or in this repo's CI, so **nothing below is run here** — the commands are
> real `goat` surface (as goatcore's `crates/goat-cli` implements it), shown as an annotated sequence.
> The goatnet can be a goatlite you stand up yourself (goatcore's
> `docs/tutorials/00-goatlite.md`), or another goatnet you have access to. Where a scenario's crypto is genuinely exercised, that happens on the reference or the SDK,
> not here.

---

## Scenario by scenario, in `goat`

Each scenario in this repo isolates one crypto moment. Here is the same moment as the operator command
that drives it — the SDK is doing the identical work underneath in every case.

| Scenario | The crypto moment | The `goat` command(s) |
|---|---|---|
| [02 — audience from a grant](../scenarios/02-audience-from-a-grant/) | the owner grants; the audience is *derived*, never hand-kept | `goat access grant <producer> <org>` · `goat access audience <producer>` |
| [03 — read and deny](../scenarios/03-read-and-deny/) | producer seals; a member opens; an outsider gets the same bytes and can't | `goat pub --sealed` · `goat sub --open` |
| [04 — revocation is rotation](../scenarios/04-revocation-is-rotation/) | remove a member by minting the next generation without it | `goat access revoke <producer> <org>` (the key service rotates the generation) |
| [05 — per-individual keys](../scenarios/05-per-individual-keys/) | the key is per person/machine; the org is only the grouping | `goat access audience <producer>` (one wrap slot per member) · `goat access key --anchor <member>` |

Two rotations, kept distinct on purpose: **scenario 04's rotation is the key service minting a new
*generation*** (a fresh DEK wrapped to everyone still granted) — an operator triggers it with
`goat access revoke`. That is different from **`goat access key rotate`, which rotates a *member's own
leaf key*** (below). Generation rotation removes *someone else*; leaf rotation refreshes *your own*
unwrap key. They compose, but they are not the same act.

---

## Scenario 03 as `goat pub --sealed` / `goat sub --open`

Scenario 03 is the whole apparatus end to end: the producer unwraps its own bundle slot for the DEK,
seals a message, publishes ciphertext; a granted member opens it; an outsider handed the identical
bytes is denied. Here is that same flow as three operators at three shells.

**The producer seals and publishes** (it is a member of its own release-set, so it opens its own slot
to get the DEK — no separate key channel):

```console
# requires an enrolled goat profile on a live goatnet — not run here
$ goat pub acme-sensors/obs/v1 --sealed \
    --key-service-bundle spire-root.pem \
    --trust-domain my-goatnet.example < reading.pb
sealed 1 sample -> acme-sensors/obs/v1  (gen 3, backend: grant-crypto SDK)
```

`--sealed` fetches the release-set's key bundles off `keys/<rs>/**`, **verifies each signer's SVID
against the SPIRE trust bundle** (fail-closed — an unverifiable signer is refused, never used), unwraps
your OWN slot with your profile's enrollment key to get the DEK, then publishes the self-describing
sealed envelope. If you hold no slot, or no verified bundle exists, it refuses rather than publish
plaintext. The key you publish under must be your own producer anchor — the design's producer-as-member
rule, exactly as scenario 03 shows it.

**A granted member subscribes and opens** with the key it already holds — its enrollment identity *is*
its recipient identity, so there is no new trust surface:

```console
# requires an enrolled goat profile on a live goatnet — not run here
$ goat sub 'acme-sensors/obs/**' --open --follow \
    --key-service-bundle spire-root.pem \
    --trust-domain my-goatnet.example
acme-sensors/obs/v1  gen 3  STATION 7: wind 040 at 12 kt
```

**The outsider — a fully enrolled fabric identity that is simply not in the audience** — runs the
identical subscribe and receives the identical bytes, and the crypto denies it:

```console
# an enrolled-but-ungranted profile on the same fabric — not run here
$ goat sub 'acme-sensors/obs/**' --open --follow \
    --key-service-bundle spire-root.pem \
    --trust-domain my-goatnet.example
acme-sensors/obs/v1  gen 3  DENIED
```

`--open` fetches + verifies the bundle the same way, admits every slot it can open, then
query-history-then-subscribes and prints each opened plaintext. **A sample it holds no key for prints
`DENIED` — the read cut is the crypto, not the router**, the whole point of scenario 03. Enrollment
lets you receive the ciphertext; it does not give you a key.

Companion reads, both operator-facing:

```console
$ goat access audience acme-sensors     # who can read this stream — the wrap set + honesty notes
$ goat access key                  # is my OWN decrypt key published to the recipient store?
$ goat access who <identity>       # the data-access view for one identity
```

---

## Scenario 02 as `goat access grant` / `goat access audience`

Scenario 02's lesson is that the audience is a **derived projection of the grant rows and the org
roster**, never a list someone keeps by hand. The operator makes exactly one decision — the grant —
and everything downstream derives from it:

```console
# as your org's data-governance admin — not run here
$ goat access grant acme-sensors northwind
recorded grant: acme-sensors -> org:northwind

$ goat access audience acme-sensors
release-set acme-sensors  gen 3  wraps to 4 members:
  acme-sensors/prod        (producer, as member)
  northwind/alice        (org northwind)
  northwind/bravo        (org northwind)
  northwind/console      (org northwind)
note: 1 browser-only person in northwind is governed on the human plane — not a wrap target
```

(The `goat access grant <producer> <org>` spelling matches this repo's own
[data-owner-controls.md](data-owner-controls.md); goatcore's `crates/goat-cli/src/cmd/access.rs` carries the `grant` /
`revoke` / `audience` verbs under `goat access`.) Add a member to `northwind`, or revoke the grant, and the
*next* `goat access audience` reflects it — the CLI reads the same derived audience the key service
wraps to, so it cannot show a stale hand-kept list. On a live goatnet this is the portal's
`GET /api/access/audience` over the real grant store; in this repo the derivation logic runs in
`demo.derive_audience` with an in-memory roster (see the [honesty matrix](honesty-matrix.md)).

Governance of *who may grant* is the same surface one level up:

```console
$ goat access govern list --org northwind          # bootstrap (every member) or narrowed to nominated admins?
$ goat access govern nominate --org northwind --email admin@northwind.example
$ goat access govern remove   --org northwind --id <nomination-id>
```

The first nomination **narrows** the org from everyone-governs to the nominated admins, on both planes,
and removing the last admin is refused so an org never silently falls open — the properties
[data-owner-controls.md](data-owner-controls.md) describes, exercised through the CLI instead of raw
portal calls.

---

## Scenario 04 as `goat access revoke`

Scenario 04 shows revocation *is* rotation: to remove a member you mint the next generation without it,
and the generation tag carries the cut. The operator does not "delete a key"; they revoke, and the key
service rotates:

```console
# the data owner revokes; the key service mints gen N+1 without the revoked audience — not run here
$ goat access revoke acme-sensors northwind
revoked grant: acme-sensors -> org:northwind
key service will exclude org:northwind from the next generation

$ goat access audience acme-sensors
release-set acme-sensors  gen 4  wraps to 1 member:
  acme-sensors/prod        (producer, as member)
```

From here, a new `goat pub --sealed` seals under gen 4, which the revoked member has no slot for; its
earlier gen-3 reads still stand, because bytes already delivered are not clawed back. That is exactly
scenario 04's model — and its honest caveat carries over unchanged: this construction does **not** give
forward secrecy across prior generations; the strategic path for that is a key tree (MLS/TreeKEM),
noted in [envelope-and-keys.md](envelope-and-keys.md), not implemented on either the reference, the
SDK, or the CLI.

---

## `goat access key rotate` — rotating your own leaf key (an honest nuance)

This verb is not one of the five scenarios, but it is the operator-facing member-lifecycle piece the
CLI adds over the SDK, and it carries a subtlety worth stating plainly. It rotates the **member leaf
key** you use to unwrap grant-encryption DEKs — backed 1:1 by the SDK's rotate verb (ADR 1106):

```console
# full forward secrecy (default): retire the old key, re-wrap nothing — not run here
$ goat access key rotate --out new-leaf.key.pem \
    --key-service-bundle spire-root.pem --trust-domain my-goatnet.example
RotationReceipt: new leaf key written to new-leaf.key.pem (destroy mode)
install it via the CA-coupled leaf re-issue (goat admin rotate) so your cert continues to match

# keep reading pre-rotation generations (REDUCES forward secrecy)
$ goat access key rotate --keep-access --out new-leaf.key.pem \
    --key-service-bundle spire-root.pem --trust-domain my-goatnet.example
RotationReceipt: re-wrap sidecar written to new-leaf.key.pem.rewrap.json
```

The nuance the docs are careful about, and this repo should be too:

- **A member's grant-encryption leaf key *is* its mTLS profile key** (CA-signed). So `rotate`
  **never overwrites your profile** — it *emits* the freshly generated key to `--out`. You then install
  it through the CA-coupled leaf re-issue (`goat admin rotate`, ADR 1044), and only once that re-issue
  **retires the old key** does the forward-secrecy benefit of `--destroy` actually land. Until then your
  live identity is unchanged.
- **`--destroy` (the default)** re-wraps nothing, so a future theft of the new key reveals nothing
  sealed to the old one. **`--keep-access`** locally re-wraps your still-live DEKs to the new key —
  which *reduces* forward secrecy for those generations — and writes the re-wrap material to a **local
  sidecar** (`<out>.rewrap.json`), never to the shared `keys/**` bundle tree (that tree carries only
  key-service-signed bundles).

---

## Getting `goat` in the first place

Kept deliberately light — this repo is about the crypto, not CLI install. An operator gets the `goat`
binary from their goatnet's mesh download surface, then establishes a profile from their enrollment
bundle:

```console
$ goat profile init <bundle.cbor>   # verify the offline-CA-signed bundle, write the context, run goat doctor
$ goat doctor                        # am I on the mesh, is the router + portal reachable, is my cert accepted?
```

The mesh download and the enrollment bundle come from the goatnet's **onboarding** — a sibling Hello
Galaxy repo — which is also where you get the NetBird enrollment that puts you on the mesh in the first
place. Everything on this page assumes that has already happened.

---

## What this path proves, and what it stands in for

Consistent with the [honesty matrix](honesty-matrix.md):

- **The mechanism is real and identical** to the other two paths — `goat pub --sealed` / `sub --open`
  delegate to the same grant-crypto SDK the scenarios run on with `bin/fetch-sdk.sh`, so there is no new
  crypto to trust here. That claim is **structural**: it follows from goat-cli holding no crypto of its
  own (ADR 1106), not from a run in this repo.
- **Nothing on this page is executed by this repo or its CI.** The commands are the real `goat` surface
  shown as an annotated transcript, because the path needs a live goatnet, an enrolled profile, and a
  SPIRE trust root. Where you want to *see the crypto actually run*, use the reference
  (`./bin/grant-enc all`) or the SDK (`./bin/fetch-sdk.sh` then `./bin/grant-enc all`) — both of which
  this repo does run and gate in CI.
- **This is the operator convenience view, deliberately.** If you are writing a producer or consumer,
  you link the SDK directly (Rust/Go/Python/C). If you are an operator at a shell on a live goatnet, you
  reach for `goat`. Same bytes on the wire either way.

## What to read next

- [`envelope-and-keys.md`](envelope-and-keys.md) — the one mechanism these commands drive.
- [`data-owner-controls.md`](data-owner-controls.md) — who decides, and the grant/govern surface `goat access` fronts.
- [Running on the production SDK](../README.md#running-on-the-production-sdk) — the path this CLI is a convenience layer over.
- [`honesty-matrix.md`](honesty-matrix.md) — every claim in this repo, graded live-vs-represented.
