# 06 — Who could decrypt this?

The question a producer asks at the moment of publishing. Not *who is the
audience* as a list of anchors — that is scenario 02 — but **is my restriction
set right**, answered fast enough to be a gut check rather than a review step.

```
bin/grant-enc run 06
```

## What it shows

**The rule is an intersection.** Being a member of the grantee org is not
enough: the holder's own nationality must also be one of the nations that own
that org ([ADR 1171](https://github.com/usareur-af/goatcore/blob/main/docs/adr/1171-person-nationality-and-org-ownership-are-two-facts.md)).
An Ardenian and a Borealian at the same desk in the same Ardenian-owned
organisation get different answers, and nothing but citizenship separates them.
(The nations here — Ardenia, Borealia, Calvaria, Dovania, Fenmark — and the
alliance that owns the multinational org, the Compact, are invented.)

`affiliation.relationship` is deliberately not an input. Testing it instead
would exclude the Ardenian too — the model marks them both `assigned` — and
empty the organisation.

**A zero is not one answer.** *Excluded* and *undeclared* both produce zero
holders and they mean opposite things: the restriction holding, versus a
registry nobody has filled in. The preview carries `evaluable` so the two
cannot be confused. This is the whole reason the surface exists, not an edge
case: in a registry where organisations have not yet declared an owning nation,
every one of them yields this zero.

**It names nobody.** Counts by nationality and by organisation, never a handle,
an anchor or an email — and cells below a k-anonymity floor of 5 are withheld,
because "1 holder, ARD, ardenia-ops" is a name to anyone who knows that org.
Below the floor the whole breakdown goes; the total stays exact, since a total
is not identifying and hiding it would defeat the only question being asked.

**A multinational org admits its body's member nations.** A person's
nationality can never equal the marker `COMPACT`, so testing the marker as a
nation would admit nobody and empty every multinational org. An ownership class
whose audience is always empty is a defect rather than a policy.

## The seam this scenario is about

Access and decryption disagree here **by design**. The excluded members hold
their organisation's read access: they can see the stream exists and cannot
open its payload. That is the point of encrypting to an audience — but
unannounced it is indistinguishable from a fault, which is this fabric's
existing silent-denial problem. The preview is where the split becomes
visible before it becomes a support ticket.

## Honesty

The rule and the aggregation here mirror the shipped implementation
(`access.DataRoster.ClassifyOrgMaterial`, `access.BuildAudiencePreview`), and
the roster is in-memory, as everywhere else in this repo.

On a goatnet the same preview is served by the portal at
`GET /api/access/audience/preview`. It shares one code path with the real wrap
— a preview computed from a second copy of the rule would drift from the thing
it predicts and then be confidently wrong exactly where the two disagreed. A
grant to a *principal* rather than an org runs no org expansion, so the
endpoint reports `evaluable: false` for it rather than presenting the zero as
an answer.
