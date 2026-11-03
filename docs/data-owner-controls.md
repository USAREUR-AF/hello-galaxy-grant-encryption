# Who decides: the data owner, not a platform admin

The crypto ([envelope-and-keys.md](envelope-and-keys.md)) makes "who holds the key" mean "who can read." This page is the other half: **who decides who holds the key.** The answer is the point of the whole design — it puts the decision with the data's owner.

## Organizations own the sharing decision

Data ownership is **organizational**. A survey company's sensor feed is that company's; a partner organisation's track data is that partner's. The organization is the unit that owns the decision to release its data — not a central administrator, and not "whoever is running the platform."

The people and machines are the **actors**: they produce data, they encrypt it, they decrypt it. But the *authority* to say "share this stream with org A" belongs to the owning organization.

## The data-governance admin

An organization exercises its ownership through one or more **data-governance admins** it nominates — people authorized to grant and revoke sharing on the org's behalf. This is a role in the same access-role grammar the rest of the platform uses (`data.govern.org:<O>`), derived from the registry, not a bolted-on second system.

- **Bootstrap.** Every member of an org starts able to govern its own org's data, so the capability is usable from day one. An org then *narrows* that to its nominated admins as it matures — it self-administers who its admins are.
- **Proxy stewardship.** If an owning organisation hasn't yet stood up its own admins, the platform operator can hold that authority for it — explicitly, recorded, and time-limited — so the organisation's data can come onto the fabric without waiting, and the authority is handed back the moment the organisation operates its own.

### How an org nominates its admins

The nomination surface is three portal calls, gated **at-most-own-scope** — only someone who *currently* governs the org (a member while it's in bootstrap, a nominated admin after, or a platform operator) may use them:

```
GET  /api/access/govern-admins?org=<O>       # who administers O, and which mode it's in:
                                             #   "bootstrap" (every member governs) or
                                             #   "nominated" (narrowed to the admins listed)
POST /api/access/govern-admins               # {"org": <O>, "email" or "identity_id": <who>, "justification": ...}
POST /api/access/govern-admins/{id}/remove   # end-dates a nomination (never deleted — audit history stays)
```

Three properties worth knowing before you use it:

- **The first nomination narrows the org** — from that moment only nominated admins carry `data.govern.org:<O>`, on *both* planes: the access-language surfaces (`goat access show/can`) stop deriving it for other members (with an honest note saying why), and a producer machine in the org loses org-wide grant authority (it always keeps custody of its *own* stream).
- **The nominee must already be a member of the org** — an org administers its own people; it cannot appoint outsiders.
- **Narrowing is one-way by design.** Removing the last active admin is refused — an org never silently falls open back to everyone-governs. If an org locks itself out, the recovery is operator proxy stewardship, deliberately and on the record.


## The owner's authority is not second-guessed

A producer defines **whatever release-set it chooses**. If it holds the data, it has the authority to release it. There is no eligibility gate the system enforces against the owner's decision — coalition standing and releasability lanes are *advisory context*, never a hard block on a grant.

The accountability model is **audit, not prevention**: every grant and revoke is a recorded action, attributable to the admin who made it. The platform records the decision; it does not adjudicate it. This matches the standing principle that over-restriction of releasable data is usually a labeling mistake, not a feature — so the friction is deliberately one-sided (sharing is free; restricting is deliberate and logged).

## Two dials, both the owner's

The owner sets two independent things:

- **Reach** — *where* a stream is published (which channel / release-set) — decides who **receives** the bytes.
- **Readability** — *who holds the key* — decides who can **open** them.

They combine freely. You can broadcast widely but restrict readability to a subset by key possession, or narrow the reach and share readability with everyone who receives it. Scenario 05 shows this split.

## From a grant to a key bundle

Here is the whole chain the owner sets in motion with one action:

```
  owner (data-governance admin)          key service                    the fabric
  ─────────────────────────────          ───────────                    ──────────
  goat access grant K org:A     ──▶  GET /api/access/audience(K)
                                     = derive members from the grant
                                       + the org roster:
                                         · org A → its member anchors
                                         · producer K itself (as member)
                                         · a browser-only person → noted,
                                           NOT a wrap target
                                     mint DEK, wrap to each, sign     ──▶  keys/K/<gen>
```

**Where the members' keys come from:** the wrap step needs each member's public key, and nobody stages it by hand. The portal *is* the issuer of every member's enrollment cert, so at mint (and at every rotation) it keeps the **public** half in a by-anchor store and serves it at `GET /api/access/recipient-cert?anchor=<member>`; the key service fetches it on demand and **re-validates it before trusting it** (chain to the CA root, the name bound into the cert must match the member, and the key must be the decryptable type) — so a compromised or misconfigured portal cannot redirect a wrap to the wrong key. A credential minted before this store existed simply fails closed with the remedy in the error: rotate it once, and the next sweep heals itself.

The audience is a **derived projection** of the grant rows and the org roster — never a hand-kept list that can drift. Add a member to org A, or revoke the grant, and the *next* derivation reflects it automatically. Scenario 02 runs this derivation; the honesty matrix records that the roster here is in-memory while on a goatnet it is the portal endpoint over its grant store.

## Two planes, one set of grants

A person reading in a browser goes through a **governed application** that checks permissions per request against the grant rows — and can therefore apply fine-grained (field/row) rules, because the app holds plaintext at read time. A cert-holding process (a machine, or a person running a client) reads on the **machine plane** by holding a key — coarser (topic granularity) but brokerless.

The load-bearing rule: **both planes read the same grants.** There is exactly one authoritative store of who-may-read-what; the human app, the machine key distribution, and any transport carve-out all consult it. A second store, a mapping table, or a sync job between them is forbidden — that's how the two planes stay honest with each other.

See [`the-philosophy.md`](the-philosophy.md) for why the shape is drawn this way.
