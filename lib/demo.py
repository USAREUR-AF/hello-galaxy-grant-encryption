"""demo — the apparatus wired together, the way it works on the real fabric.

grant_enc.py is the crypto. This is the *system*: the four roles and the one
transport they share, mirroring the production shape (design: grant-keyed
encryption + ADR 1102) so a scenario reads like the real thing.

  KeyService    off the data path. On a grant/audience change it mints a fresh
                DEK, wraps it to every member, SIGNS the bundle, and PUBLISHES it
                on keys/<rs>/<gen>. It is NOT in the read path — its absence
                blocks new rotations, never ongoing reads (so it is not a broker).
  derive_audience   the audience is DERIVED from grant rows, never a stored list:
                org grantees expand to the producer anchors under them; the
                producer is always its own member (producer-as-member).
  Producer      a MEMBER of its own release-set: it fetches the bundle, unwraps
                ITS OWN slot for the DEK, seals each message, and publishes
                ciphertext on the data topic. No new key channel.
  Consumer      keeps the bundles it can open; per message it unwraps its slot and
                opens the payload. An outsider has no slot -> denied by the crypto.

The Transport is a seam with two implementations: an in-process bus (default,
zero dependencies, models Zenoh pub/sub incl. the key-retention store so a late
reader can fetch the current bundle) and an optional real eclipse/zenoh router
(scenario 03 / --fabric). Both carry the SAME bytes; the crypto is identical.

The endpoint crypto is a second seam. Producer.seal and Consumer.verify/admit/open
run on the PRODUCTION grant-crypto SDK when it is present under ./sdk/ (run
bin/fetch-sdk.sh); otherwise they run on the readable reference (grant_enc) so a
bare clone still works. Either way the bytes on the wire are identical — the SDK
and grant_enc are wire-compatible (tests/cross_compat.py). The KeyService below
stays on grant_enc in both modes: it mirrors the real `grant-keyd` daemon, and the
SDK deliberately exposes no key-authority surface (a producer is not a key
authority). So even in SDK mode, a grant_enc-signed bundle is what the SDK
verifies, admits, and opens.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grant_enc as g  # noqa: E402
import sdk_bridge as sdk  # noqa: E402  (endpoint-crypto seam: SDK when present, else grant_enc)


# ---- the transport seam -------------------------------------------------------

class InProcessBus:
    """A faithful stand-in for brokerless Zenoh pub/sub: publishing a bundle on a
    key topic RETAINS it (the keys/** storage, so a late reader can fetch it), and
    every subscriber to a data topic receives the identical bytes — including an
    outsider, exactly as the router routes ciphertext it cannot read."""

    def __init__(self) -> None:
        self._retained: dict[str, bytes] = {}          # key topic -> latest bundle bytes
        self._subs: dict[str, list[Callable]] = {}     # data topic prefix -> callbacks

    def put_key(self, topic: str, payload: bytes) -> None:
        self._retained[topic] = payload                # retained (history-key storage)

    def get_keys(self, prefix: str) -> list[tuple[str, bytes]]:
        return [(t, p) for t, p in sorted(self._retained.items()) if t.startswith(prefix)]

    def subscribe_data(self, prefix: str, cb: Callable[[str, bytes], None]) -> None:
        self._subs.setdefault(prefix, []).append(cb)

    def put_data(self, topic: str, payload: bytes) -> None:
        for prefix, cbs in self._subs.items():
            if topic.startswith(prefix):
                for cb in cbs:
                    cb(topic, payload)


# ---- the four roles -----------------------------------------------------------

@dataclass
class KeyService:
    """The per-site key-distribution service. Holds its signing identity and the
    current generation per release-set; never retains a DEK."""
    identity: g.Identity
    generations: dict = field(default_factory=dict)

    @property
    def verifying_key(self):
        return self.identity.key.public_key()

    @property
    def verifying_key_spki(self) -> bytes:
        """The verifying key as SPKI DER — the form the SDK consumer authenticates
        the bundle against (grant_enc verifies against the key object directly)."""
        return sdk.spki_der(self.verifying_key)

    def rotate(self, bus, rs: str, audience: dict) -> int:
        """Mint the next generation's DEK, wrap to every member, sign, publish.
        `audience` is member_id -> public key. Returns the new generation."""
        gen = self.generations.get(rs, 0) + 1
        dek = g.new_dek()
        bundle = g.new_bundle(rs, gen, dek, audience)
        g.sign_bundle(bundle, self.identity.member_id, self.identity.key)
        import json
        bus.put_key(g_bundle_topic(rs, gen), json.dumps(bundle.to_dict()).encode())
        self.generations[rs] = gen
        return gen


def g_bundle_topic(rs: str, gen: int) -> str:
    return f"keys/{rs}/{gen}"


def derive_audience(producer: str, grants: list, roster: "Roster") -> tuple[dict, list]:
    """The audience projection (mirrors GET /api/access/audience): from `producer`'s
    in-effect grant rows, return {member_anchor: public_key} plus notes. Org grantees
    expand to the anchors under them; a principal grantee with a machine anchor joins;
    a principal with none is a browser-only reader (noted, not wrapped); the producer
    is always its own member. DERIVED, never a stored list."""
    members: dict = {}
    notes: list = []
    members[producer] = roster.key_of(producer)      # producer-as-member
    for grant in grants:
        if grant.producer != producer or grant.status != "active":
            continue
        if grant.grantee_kind == "org":
            for anchor in roster.anchors_under_org(grant.grantee_id):
                members[anchor] = roster.key_of(anchor)
        elif grant.grantee_kind == "principal":
            if roster.is_machine_anchor(grant.grantee_id):
                members[grant.grantee_id] = roster.key_of(grant.grantee_id)
            else:
                notes.append(f"principal {grant.grantee_id} has no machine anchor — "
                             "a browser-only reader (human plane), not a wrap target")
    return members, notes


@dataclass
class Producer:
    """A producer that is a member of its own release-set. On `.publish` it acquires
    its own DEK from the key bundle and seals — on the SDK when present, else on the
    reference. Producer-as-member: no separate key channel, it opens its own slot."""
    identity: g.Identity
    rs: str
    _sdk: Optional[object] = field(default=None, init=False)

    def __post_init__(self):
        if sdk.available():
            self._sdk = sdk.SdkProducer(self.identity, self.rs)

    def _bundles(self, bus) -> list[dict]:
        return [json.loads(payload) for _, payload in bus.get_keys(f"keys/{self.rs}/")]

    def acquire_dek(self, bus) -> tuple[int, bytes]:
        """Fetch keys/<rs>/**, pick the highest generation we have a slot in, and
        unwrap our own slot -> DEK (the producer-as-member DEK handoff). The
        reference path; the SDK does the same inside StreamKey.acquire."""
        best = None
        for _, payload in bus.get_keys(f"keys/{self.rs}/"):
            b = g.KeyBundle.from_dict(json.loads(payload))
            if self.identity.member_id in b.members and (best is None or b.gen > best.gen):
                best = b
        if best is None:
            raise g.DeniedError(f"no bundle wraps a slot for producer {self.identity.member_id!r}")
        return best.gen, g.unwrap_dek(best.members[self.identity.member_id], self.identity.key)

    def publish(self, bus, keyexpr: str, plaintext: bytes) -> int:
        if self._sdk is not None:
            gen, env_json = self._sdk.seal(self._bundles(bus), keyexpr, plaintext)
            bus.put_data(keyexpr, env_json)
            return gen
        gen, dek = self.acquire_dek(bus)
        env = g.seal_envelope(dek, self.rs, gen, plaintext, keyexpr)
        bus.put_data(keyexpr, json.dumps(env.to_dict()).encode())
        return gen


@dataclass
class Consumer:
    """A member (or outsider) reading the stream. Verifies + admits each bundle,
    then opens each message with the held key — or is denied by the crypto if it
    has no slot. Runs on the SDK (verify_bundle -> KeyStore.admit/open) when present,
    else on the reference. `_deks` tracks the held (rs, gen) so len() reads out how
    many slots we hold in either mode."""
    identity: g.Identity
    rs: str
    ks_verifying_key: object
    _deks: dict = field(default_factory=dict)   # (rs, gen) -> dek (ref) | True (sdk)
    opened: list = field(default_factory=list)
    denied: list = field(default_factory=list)
    _sdk: Optional[object] = field(default=None, init=False)

    def __post_init__(self):
        if sdk.available():
            self._sdk = sdk.SdkConsumer(self.identity, sdk.spki_der(self.ks_verifying_key))

    def refresh_keys(self, bus) -> int:
        """Fetch + verify + admit every bundle we can open. Returns how many slots
        we hold (0 for an outsider)."""
        for _, payload in bus.get_keys(f"keys/{self.rs}/"):
            b = json.loads(payload)
            if self._sdk is not None:
                if self._sdk.admit(b):                     # verify + unwrap our slot
                    self._deks[(b["rs"], b["gen"])] = True
                continue
            bundle = g.KeyBundle.from_dict(b)
            g.verify_bundle(bundle, self.ks_verifying_key)  # authenticity before unwrap
            if self.identity.member_id in bundle.members:
                self._deks[(bundle.rs, bundle.gen)] = g.unwrap_dek(
                    bundle.members[self.identity.member_id], self.identity.key)
        return len(self._deks)

    def on_message(self, topic: str, payload: bytes) -> None:
        env_dict = json.loads(payload)
        gen = int(env_dict["gen"])
        if self._sdk is not None:
            try:
                self.opened.append((topic, gen, self._sdk.open(topic, env_dict)))
            except g.DeniedError:
                self.denied.append((topic, gen))
            return
        env = g.Envelope.from_dict(env_dict)
        dek = self._deks.get((env.rs, env.gen))
        if dek is None:
            self.denied.append((topic, env.gen))
            return
        try:
            self.opened.append((topic, env.gen, g.open_envelope(dek, env, topic)))
        except g.DeniedError:
            self.denied.append((topic, env.gen))


# ---- a tiny roster (the registry projection the audience is derived from) -----

@dataclass
class Grant:
    producer: str
    grantee_kind: str          # "org" | "principal"
    grantee_id: str
    status: str = "active"     # "active" | "revoked"
    justification: str = ""


class Roster:
    """The declared registry projection: orgs -> member anchors, and each anchor's
    public key. Mirrors the portal roster the audience endpoint reads. Human
    principals (no machine anchor) are recorded so the audience can note them."""

    def __init__(self) -> None:
        self._org_anchors: dict[str, list[str]] = {}
        self._keys: dict[str, object] = {}
        self._humans: set[str] = set()
        # ADR 1171: two facts, neither derived from the other. An ORG has an
        # owning nation and a composition; a PERSON has their own nationality.
        # Absent means UNDECLARED — never "same as the org", which is the
        # inference the whole model exists to delete.
        self._org_nation: dict[str, str] = {}
        self._org_composition: dict[str, str] = {}
        self._anchor_nationality: dict[str, str] = {}

    def declare_org(self, org: str, nation: str = "", composition: str = "") -> None:
        """Declare what the ORGANISATION is. Called separately from adding
        members, because it is a different fact about a different subject."""
        if nation:
            self._org_nation[org] = nation
        if composition:
            self._org_composition[org] = composition

    def add_machine(self, org: str, identity: g.Identity, nationality: str = "") -> g.Identity:
        self._org_anchors.setdefault(org, []).append(identity.member_id)
        self._keys[identity.member_id] = identity.public
        if nationality:
            self._anchor_nationality[identity.member_id] = nationality
        return identity

    def org_nationality(self, org: str) -> tuple[str, str, bool]:
        nation = self._org_nation.get(org, "")
        return nation, self._org_composition.get(org, ""), bool(nation)

    def anchor_nationality(self, anchor: str) -> tuple[str, bool]:
        n = self._anchor_nationality.get(anchor, "")
        return n, bool(n)

    def add_human(self, uuid: str) -> None:
        self._humans.add(uuid)

    def anchors_under_org(self, org: str) -> list[str]:
        return list(self._org_anchors.get(org, []))

    def is_machine_anchor(self, anchor: str) -> bool:
        return anchor in self._keys

    def key_of(self, anchor: str) -> object:
        return self._keys[anchor]


# ---------------------------------------------------------------------------
# The nationality intersection, and the preview a producer sees before
# publishing. Mirrors goat's access.DataRoster.ClassifyOrgMaterial
# and access.BuildAudiencePreview — the SAME rule the wrap runs, which is the
# point: a preview computed from a second copy of the rule would drift from the
# thing it predicts and then be confidently wrong exactly where they disagreed.
# ---------------------------------------------------------------------------

#: The smallest breakdown cell this surface will show. "1 holder, ARD,
#: ardenia-ops" names a person to anyone who knows that org, so cells below the
#: floor are folded away — and when the TOTAL is below it, the whole breakdown
#: goes, because suppressing rows while the total stands still names the group.
#: Not a caller's choice: a caller who has to pick a floor picks 1.
K_ANONYMITY_FLOOR = 5

ADMITTED = "admitted"
EXCLUDED = "nationality_excluded"
ORG_NATION_UNDECLARED = "org_nation_undeclared"
HOLDER_NATIONALITY_UNDECLARED = "holder_nationality_undeclared"


def classify_org_material(anchor: str, org: str, roster: "Roster",
                          framework_members: set | None = None) -> tuple[bool, str, str]:
    """Does the holder of `anchor` earn a wrap slot for material addressed to
    `org`? Returns (admitted, reason_code, sentence).

    THE RULE (ADR 1171): membership in the org AND
    the holder's own nationality being one of the nations that own it. For a
    `national` org that is the owning nation; for a `multinational` one it is
    membership of the body the org is constituted from.

    `affiliation.relationship` is deliberately NOT consulted. A Borealian at an
    Ardenian-owned org is excluded because BOR is not ARD, and an Ardenian at the
    same desk is included for the same reason — testing the relationship field
    instead would exclude the American too, and empty the organisation.

    FAIL-CLOSED ON ABSENCE, both directions: absence is not a match, and a guess
    here is a silent disclosure."""
    nation, composition, declared = roster.org_nationality(org)
    if not declared:
        return False, ORG_NATION_UNDECLARED, \
            "the organisation declares no owning nation, so no holder can be matched against it"
    held, has = roster.anchor_nationality(anchor)
    if not has:
        return False, HOLDER_NATIONALITY_UNDECLARED, \
            "the holder declares no nationality — undeclared is not a match"
    if composition == "multinational":
        if held in (framework_members or set()):
            return True, ADMITTED, ""
        return False, EXCLUDED, f"{held} is not a member of {nation}"
    if held == nation:
        return True, ADMITTED, ""
    return False, EXCLUDED, f"{held} is not {nation}"


def preview_audience(producer: str, grants: list, roster: "Roster",
                     framework_members: set | None = None) -> dict:
    """What a producer is shown before encrypting: how many holders would
    receive a wrap slot, by nationality and by organisation — and never a
    handle, an anchor or an email.

    The load-bearing field is `evaluable`. EXCLUDED and UNDECLARED both produce
    a zero and they mean opposite things: the first is the restriction holding,
    the second is a registry nobody has filled in. A producer who reads an
    undeclared zero as an excluded one concludes the restriction is tight when
    the question was never answerable — wrong, in the unsafe direction."""
    admitted: dict[str, str] = {}          # anchor -> nationality
    admitted_org: dict[str, str] = {}      # anchor -> org
    refused: dict[str, str] = {}           # anchor -> reason code
    encrypted = False

    for grant in grants:
        if grant.producer != producer or grant.status != "active":
            continue
        encrypted = True
        if grant.grantee_kind != "org":
            continue
        for anchor in roster.anchors_under_org(grant.grantee_id):
            ok_, why, _ = classify_org_material(anchor, grant.grantee_id, roster, framework_members)
            if ok_:
                admitted[anchor] = roster.anchor_nationality(anchor)[0]
                admitted_org[anchor] = grant.grantee_id
            elif anchor not in refused:
                refused[anchor] = why

    counts = {ADMITTED: 0, EXCLUDED: 0, ORG_NATION_UNDECLARED: 0,
              HOLDER_NATIONALITY_UNDECLARED: 0}
    for anchor, why in refused.items():
        if anchor not in admitted:         # admitted anywhere is not refused
            counts[why] = counts.get(why, 0) + 1

    total = len(admitted)
    by_nat, by_org = {}, {}
    for a, nat in admitted.items():
        by_nat[nat] = by_nat.get(nat, 0) + 1
        by_org[admitted_org[a]] = by_org.get(admitted_org[a], 0) + 1

    return {
        "encrypted": encrypted,
        "holders": total,
        "by_nationality": _fold_cells(by_nat, total),
        "by_org": _fold_cells(by_org, total),
        "refused": counts,
        "refused_total": sum(counts[k] for k in counts if k != ADMITTED),
        # The rule reached a verdict on somebody: it admitted a holder, or it
        # refused one on facts BOTH sides declared.
        "evaluable": total > 0 or counts[EXCLUDED] > 0,
    }


def _fold_cells(counts: dict, total: int) -> list:
    """Largest first, with every cell below the floor folded into one withheld
    row. Below the floor the whole breakdown goes; the TOTAL always stays exact,
    because a total is not identifying and hiding it would defeat the only
    question the surface exists to answer."""
    if not counts:
        return []
    if total < K_ANONYMITY_FLOOR:
        return [{"value": None, "holders": sum(counts.values()),
                 "withheld": True, "cells": len(counts)}]
    out = [{"value": v, "holders": n} for v, n in counts.items() if n >= K_ANONYMITY_FLOOR]
    out.sort(key=lambda c: (-c["holders"], c["value"]))
    small = {v: n for v, n in counts.items() if n < K_ANONYMITY_FLOOR}
    if small:
        out.append({"value": None, "holders": sum(small.values()),
                    "withheld": True, "cells": len(small)})
    return out
