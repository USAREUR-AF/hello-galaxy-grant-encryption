#!/usr/bin/env python3
"""Scenario 02 — the audience comes from a grant, not a config file.

This is what makes it *data-owner driven*. The owner records one grant ("share
producer K with org A"); the key service DERIVES the audience from that grant and
the org roster — never a hand-kept member list. The producer is always its own
member, so it can pull its own DEK.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import grant_enc as g          # noqa: E402
import demo as d               # noqa: E402
import narrate as n            # noqa: E402


def main() -> None:
    n.banner("02 — Audience from a grant", "the owner grants; the key service derives who gets a key")

    n.step("A roster: org 'acme-sensors' owns producer K; org 'northwind' has two machine members; a person has none.")
    roster = d.Roster()
    K = roster.add_machine("acme-sensors", g.Identity("acme-sensors/sensor-k")).member_id
    nw_station = roster.add_machine("northwind", g.Identity("northwind/station")).member_id
    nw_dashboard = roster.add_machine("northwind", g.Identity("northwind/dashboard")).member_id
    roster.add_human("495e7900-28ef-469c-887d-0a63adbfead1")   # a browser-only person
    n.say(f"producer K = {K}")
    n.say(f"northwind members = [{nw_station}, {nw_dashboard}]")

    n.step("The data owner records ONE grant: 'acme-sensors/sensor-k may be read by org northwind'.")
    grants = [d.Grant(producer=K, grantee_kind="org", grantee_id="northwind",
                      justification="shared weather picture")]
    n.say("grant: org:northwind -> producer acme-sensors/sensor-k  (status active)")

    n.step("The key service DERIVES the audience from that grant + the roster.")
    audience, notes = d.derive_audience(K, grants, roster)
    for mid in sorted(audience):
        tag = "producer-as-member" if mid == K else "from the org grant"
        n.say(f"  wrap DEK to {mid}   ({tag})")
    for note in notes:
        n.honest(note)

    n.step("Now add a PRINCIPAL grant to the browser-only person — watch it NOT become a wrap target.")
    grants.append(d.Grant(producer=K, grantee_kind="principal",
                          grantee_id="495e7900-28ef-469c-887d-0a63adbfead1"))
    audience2, notes2 = d.derive_audience(K, grants, roster)
    for note in notes2:
        n.honest(note)
    n.say("the browser-only person reads through the mediated human-plane surface — it holds no wrapping key.")

    n.step("The key service wraps + signs one bundle for the derived audience.")
    ks = d.KeyService(g.Identity("site-a/key-service"))
    bus = d.InProcessBus()
    gen = ks.rotate(bus, K, audience2)
    n.say(f"published keys/{K}/{gen} — {len(audience2)} wrapped slots, signed by {ks.identity.member_id!r}.")

    n.step("What it proves.")
    n.say("• The audience is a DERIVED projection of grant rows + the roster — no second list to keep in sync.")
    n.say("• An org grant expands to that org's machine members (its anchors); the producer is always included.")
    n.say("• A person with no machine key is a browser-only reader — correctly NOT a machine-plane wrap target.")
    n.honest("The roster here is in-memory; on a goatnet it is the portal's GET /api/access/audience over the same grant rows.")

    ok = (set(audience2) == {K, nw_station, nw_dashboard}) and len(notes2) == 1
    n.result(ok, "one grant, plus the roster, derived exactly the right set of key-holders.")


if __name__ == "__main__":
    main()
